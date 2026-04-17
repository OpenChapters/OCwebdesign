"""
Celery tasks for the catalog app.
"""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(name="catalog.sync_chapters")
def sync_chapters_task():
    """
    Run the sync_chapters management command as a Celery task.

    Scheduled nightly via CELERY_BEAT_SCHEDULE in settings.
    Can also be triggered manually::

        from catalog.tasks import sync_chapters_task
        sync_chapters_task.delay()

    If HTML_BUILD_ENABLED is set, also dispatches HTML rebuilds for
    chapters whose source has been updated since the last HTML build.
    """
    logger.info("Starting nightly chapter catalog sync …")
    call_command("sync_chapters")
    logger.info("Chapter catalog sync complete.")

    from django.conf import settings as django_settings
    if getattr(django_settings, "HTML_BUILD_ENABLED", False):
        dispatch_stale_html_builds.delay()


@shared_task(
    name="catalog.dispatch_stale_html_builds",
    time_limit=60,
)
def dispatch_stale_html_builds():
    """Find chapters whose source is newer than their HTML build, and
    dispatch a build task for each. Celery worker concurrency handles
    parallelism."""
    from catalog.models import Chapter
    from django.db.models import F, Q

    stale = Chapter.objects.filter(
        published=True,
    ).exclude(chabbr="").filter(
        Q(html_built_at__isnull=True)
        | Q(last_updated__gt=F("html_built_at"))
    )

    count = 0
    for ch in stale:
        build_chapter_html_task.delay(chabbr=ch.chabbr)
        count += 1

    logger.info("Dispatched HTML builds for %d stale chapter(s)", count)
    return {"dispatched": count}


@shared_task(
    name="catalog.build_chapter_html",
    time_limit=2400,
    soft_time_limit=1800,
)
def build_chapter_html_task(chabbr=None):
    """Build HTML output for a single chapter (by chabbr) or all published.

    Runs on the worker (which has TeX Live + arara). Delegates to the
    build_chapter_html management command.
    """
    from io import StringIO

    out = StringIO()
    kwargs = {"stdout": out}
    if chabbr:
        kwargs["chabbr"] = chabbr

    call_command("build_chapter_html", **kwargs)
    output = out.getvalue()
    logger.info("build_chapter_html completed:\n%s", output)
    return {"output": output}


@shared_task(
    name="catalog.build_all_chapter_html",
    time_limit=60,
)
def build_all_chapter_html_task():
    """Fan out individual HTML build tasks for each published chapter.

    Dispatches one build_chapter_html_task per chapter to the worker
    queue. Celery's concurrency setting controls how many run in
    parallel (e.g., --concurrency 4 in docker-compose.prod.yml).
    """
    from catalog.models import Chapter

    chapters = Chapter.objects.filter(published=True).exclude(chabbr="")
    count = 0
    for ch in chapters:
        build_chapter_html_task.delay(chabbr=ch.chabbr)
        count += 1

    logger.info("Dispatched HTML build tasks for %d chapters", count)
    return {"dispatched": count}
