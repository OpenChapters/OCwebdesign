from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read .env file if present (local dev without Docker).
# In Docker, env vars are injected via docker-compose env_file.
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    # Project apps
    "users",
    "catalog",
    "books",
    "admin_api",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ocweb.urls"
WSGI_APPLICATION = "ocweb.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "auth": "10/hour",
    },
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://ocweb:ocweb@rabbitmq:5672//")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="rpc://")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ── External services ─────────────────────────────────────────────────────────
GITHUB_TOKEN = env("GITHUB_TOKEN", default="")
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")

# Cloudflare Turnstile (bot protection on registration)
# Test keys: always pass in dev. Replace with real keys for production.
# https://developers.cloudflare.com/turnstile/troubleshooting/testing/
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="1x00000000000000000000AA")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="1x0000000000000000000000000000000AA")

# Email delivery
FROM_EMAIL = env("FROM_EMAIL", default="noreply@openchapters.org")
SITE_URL = env("SITE_URL", default="http://localhost:5173")
PDF_LINK_EXPIRY_DAYS = env.int("PDF_LINK_EXPIRY_DAYS", default=7)

# ── Celery Beat schedule ──────────────────────────────────────────────────────
CELERY_BEAT_SCHEDULE = {
    "sync-chapters-nightly": {
        "task": "catalog.sync_chapters",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC every day
    },
}

# ── Build pipeline ────────────────────────────────────────────────────────────
# Absolute path to the Build/ directory containing .sty template files
# and the scripts/ subdirectory.
BUILD_TEMPLATE_DIR = BASE_DIR / "Build" / "template"
BUILD_SCRIPTS_DIR = BASE_DIR / "Build" / "scripts"

# Local directory where generated PDFs are stored in dev.
# In production this will be replaced by S3 upload logic in build_book.
BUILD_OUTPUT_DIR = env.path("BUILD_OUTPUT_DIR", default=str(BASE_DIR / "media" / "pdfs"))

# Path to a local clone of the OpenChapters monorepo.
# When set, "Update Thumbnails" also writes cover.png to the monorepo.
OPENCHAPTERS_MONOREPO_PATH = env("OPENCHAPTERS_MONOREPO_PATH", default="")
