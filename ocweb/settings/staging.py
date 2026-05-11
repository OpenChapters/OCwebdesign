"""Staging settings — clone of prod minus the strict TLS posture.

Used by docker-compose.staging.yml. Staging exists to catch
deploy-shaped regressions (the kind that depend on prod's STORAGES
config, gunicorn flags, etc.) BEFORE they hit production, so we keep
everything as close to prod as practical and only relax the bits that
would otherwise require a separate cert or domain (HTTPS-only cookies,
HSTS, SSL redirect).
"""

from .prod import *  # noqa: F401, F403
from .base import env  # noqa: E402

# ── HTTP-only at the edge ─────────────────────────────────────────────────────
# nginx.staging.conf terminates plain HTTP on port 80 (mapped to a host
# port by docker-compose.staging.yml). Forcing the SSL redirect and
# secure-cookie flags would block any session over that path.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ── Email → console ──────────────────────────────────────────────────────────
# Whatever EMAIL_BACKEND prod is configured for, staging should never
# actually send mail. The console backend prints message bodies to the
# `web` container's stdout so the build-success and password-reset
# flows still surface during smoke testing.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Staging-only override so the Sentry environment tag in error reports
# (if VITE_SENTRY_DSN is wired up) makes it obvious where they came from.
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="staging")
