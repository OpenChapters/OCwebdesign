from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"

# whitenoise serves static files (Django admin CSS) directly from gunicorn.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ── Security ──────────────────────────────────────────────────────────────────
# nginx terminates SSL and forwards X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
