# ─────────────────────────────────────────────────────────────────────────────
# OpenChapters — web / Django image
#
# Used for the web and beat services in docker-compose.
# Build context: repo root (OCwebdesign/)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# libpq-dev + gcc are required to build psycopg (PostgreSQL adapter)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpq-dev \
      gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/dev.txt

# Source code is mounted as a volume in dev; copy here for production builds.
COPY . .

ENV DJANGO_SETTINGS_MODULE=ocweb.settings.dev
