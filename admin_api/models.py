from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteSetting(models.Model):
    """
    Key-value store for runtime site configuration.

    Non-sensitive operational settings that can be changed from the admin
    panel without redeploying. Secrets (API keys, passwords) remain in
    environment variables.
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"

    # Default values for all known settings
    DEFAULTS = {
        "site_name": "OpenChapters",
        "welcome_message": "",
        "announcement_banner": "",
        "registration_enabled": True,
        "build_enabled": True,
        "max_chapters_per_book": 30,
        "max_concurrent_builds": 4,
        "pdf_retention_days": 90,
    }

    @classmethod
    def get(cls, key: str):
        """Get a setting value, falling back to the default."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return cls.DEFAULTS.get(key)

    @classmethod
    def get_all(cls) -> dict:
        """Return all settings merged with defaults."""
        result = dict(cls.DEFAULTS)
        for obj in cls.objects.all():
            result[obj.key] = obj.value
        return result


class AuditEntry(models.Model):
    """
    Immutable record of an admin action.

    Created automatically by admin API views when they modify data.
    Cannot be edited or deleted via the API.
    """

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(max_length=100)        # e.g. "user.deactivate"
    target_type = models.CharField(max_length=50)     # e.g. "User", "Chapter"
    target_id = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict)           # before/after or extra info
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "audit entries"

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.user} {self.action} {self.target_type}#{self.target_id}"

    @classmethod
    def log(cls, request, action: str, target_type: str, target_id=None, detail=None):
        """Create an audit entry from a DRF request."""
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR")
        return cls.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
            ip_address=ip,
        )
