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
    time_limit=900,
    soft_time_limit=600,
)
def build_chapter_html_task(chabbr=None):
    """Build HTML output for published chapters using lwarp.

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
