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
    """
    logger.info("Starting nightly chapter catalog sync …")
    call_command("sync_chapters")
    logger.info("Chapter catalog sync complete.")


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
