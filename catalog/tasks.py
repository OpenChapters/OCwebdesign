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
