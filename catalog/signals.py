"""
Signal handlers for the catalog app.

The single non-trivial responsibility right now is the worked-example
version ledger: every time the content of an `Example` row changes,
the *prior* state is snapshotted into `ExampleVersion` before the new
state is persisted. This gives us append-only edit history and
point-in-time recovery without changing how authors save.

Status-only transitions (admin approve/reject) are intentionally not
tracked here — those are already recorded in the admin AuditEntry log.

Connected from `CatalogConfig.ready()`.
"""

from __future__ import annotations

import logging
import threading

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Example, ExampleVersion

logger = logging.getLogger(__name__)

# Fields whose change should write a ledger row. Everything else (status,
# rejection_reason, preview_*, timestamps) is excluded so admin moderation
# and build-system bookkeeping don't churn the ledger.
_TRACKED_FIELDS = (
    "statement_tex",
    "solution_tex",
    "difficulty",
    "primary_chapter_id",
    "slug",
)

# Per-thread "current user" stash so the ledger row can record who made
# the edit. Views that mutate examples push the request user into this
# slot; absence of a user is fine (logged as null).
_local = threading.local()


def set_current_user(user) -> None:
    """Associate subsequent saves on this thread with `user`. Safe to
    call with None to clear."""
    _local.user = user


def _current_user():
    return getattr(_local, "user", None)


def _build_snapshot(old: Example) -> dict:
    """Capture the prior state. Chapter rows might later be deleted, so
    we store chabbrs (string keys) instead of FK ids."""
    primary = (
        old.primary_chapter.chabbr
        if old.primary_chapter_id and old.primary_chapter
        else None
    )
    return {
        "statement_tex": old.statement_tex,
        "solution_tex": old.solution_tex,
        "difficulty": old.difficulty,
        "primary_chapter_chabbr": primary,
        "chapters_chabbrs": list(
            old.chapters.values_list("chabbr", flat=True)
        ),
        "status": old.status,
        "slug": old.slug,
    }


@receiver(pre_save, sender=Example)
def snapshot_example_on_content_change(sender, instance: Example, **kwargs):
    # New rows: nothing to snapshot, the create *is* version 1's
    # successor state.
    if instance.pk is None:
        return

    try:
        old = Example.objects.select_related("primary_chapter").get(pk=instance.pk)
    except Example.DoesNotExist:
        # Save with explicit pk on a row that doesn't exist yet — treat
        # as create.
        return

    if not any(
        getattr(old, f) != getattr(instance, f) for f in _TRACKED_FIELDS
    ):
        return

    last_no = (
        ExampleVersion.objects
        .filter(example_id=old.pk)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
    ) or 0

    try:
        ExampleVersion.objects.create(
            example_id=old.pk,
            version_no=last_no + 1,
            snapshot=_build_snapshot(old),
            created_by=_current_user(),
        )
    except Exception:
        # Never let a ledger failure break the user-visible save.
        logger.exception("Failed to write ExampleVersion for Example #%s", old.pk)
