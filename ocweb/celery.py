import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ocweb.settings.dev")

app = Celery("ocweb")

# Read Celery config from Django settings, using the CELERY_ prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps.
app.autodiscover_tasks()
