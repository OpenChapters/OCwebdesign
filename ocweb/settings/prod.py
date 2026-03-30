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
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Turnstile validation ──────────────────────────────────────────────────────
# Ensure Cloudflare Turnstile test keys are not used in production.
_TURNSTILE_TEST_KEYS = {
    "1x00000000000000000000AA",
    "1x0000000000000000000000000000000AA",
    "2x00000000000000000000AB",
    "3x0000000000000000000000000000000AB",
}
if TURNSTILE_SITE_KEY in _TURNSTILE_TEST_KEYS or TURNSTILE_SECRET_KEY in _TURNSTILE_TEST_KEYS:
    import warnings
    warnings.warn(
        "TURNSTILE_SITE_KEY or TURNSTILE_SECRET_KEY is set to a Cloudflare test key. "
        "Registration CAPTCHA will not protect against bots. "
        "Set real keys in .env.prod for production use.",
        stacklevel=1,
    )
