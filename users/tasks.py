"""Celery tasks for the users app."""

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="users.send_reset_email",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=60,
    retry_backoff_max=600,
)
def send_reset_email_task(self, email: str, reset_url: str) -> None:
    """Send a password reset email via SMTP, with automatic retry."""
    if not getattr(settings, "EMAIL_HOST", ""):
        logger.info("Password reset link for %s: %s", email, reset_url)
        return

    from django.core.mail import EmailMultiAlternatives

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")
    text_body = (
        f"Hi,\n\n"
        f"A password reset was requested for your OpenChapters account.\n\n"
        f"Reset your password:\n{reset_url}\n\n"
        f"If you did not request this, you can ignore this email.\n\n"
        f"— OpenChapters"
    )
    html_body = (
        f"<p>Hi,</p>"
        f"<p>A password reset was requested for your OpenChapters account.</p>"
        f'<p><a href="{reset_url}" style="display:inline-block;padding:12px 24px;'
        f"background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;"
        f'font-weight:600;">Reset Password</a></p>'
        f"<p><small>If you did not request this, you can ignore this email.</small></p>"
        f"<p>— OpenChapters</p>"
    )

    msg = EmailMultiAlternatives(
        subject="Reset your OpenChapters password",
        body=text_body,
        from_email=f"OpenChapters <{from_email}>",
        to=[email],
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        msg.send()
        logger.info("Password reset email sent to %s", email)
    except Exception as exc:
        logger.error(
            "Failed to send reset email to %s (attempt %d/%d): %s",
            email, self.request.retries + 1, 3, exc,
        )
        raise  # triggers autoretry


@shared_task(name="users.purge_expired_accounts")
def purge_expired_accounts() -> int:
    """Hard-delete any user whose deletion_scheduled_at is in the past.

    Driven by a daily Celery Beat job (see CELERY_BEAT_SCHEDULE). The
    7-day window between scheduling and purge gives the user time to
    sign in and cancel via /api/auth/profile/cancel-deletion/.

    Returns the number of accounts removed (so the task log line is
    useful for ops review).
    """
    from django.utils import timezone

    from users.models import User

    qs = User.objects.filter(deletion_scheduled_at__lte=timezone.now())
    count = qs.count()
    if count:
        # .delete() cascades to Book / Example / etc. via the existing
        # FK on_delete settings. We log emails before delete so the audit
        # trail isn't blank if ops needs to investigate later.
        emails = list(qs.values_list("email", flat=True))
        logger.warning("Purging %d expired account(s): %s", count, emails)
        qs.delete()
    return count
