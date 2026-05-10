#!/usr/bin/env bash
# Daily backup for OpenChapters prod.
#
# Writes two files per run into $BACKUP_DIR:
#   db_<timestamp>.sql.gz     — gzipped pg_dump of the Postgres database
#   media_<timestamp>.tar.gz  — tar of irreplaceable media subdirs:
#                                 - example_figures/  (author uploads)
#                                 - examples/         (snippet preview PDFs,
#                                                      slow to regenerate)
#
# Build artefacts (media/pdfs, media/html, media/html_books, media/pdf_labels)
# are intentionally skipped because they can be rebuilt from source on demand.
#
# Files older than $RETENTION_DAYS are pruned at the end of each run.
#
# Configuration via environment variables (with defaults):
#   BACKUP_DIR        ~/backups/ocweb
#   RETENTION_DAYS    90
#   COMPOSE_FILE      docker-compose.prod.yml
#   POSTGRES_USER     ocweb
#   POSTGRES_DB       ocweb
#
# Usage:
#   ./scripts/backup.sh                  # run ad-hoc
#   See docs/deployment-guide.md for the cron line.

set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/ocweb}"
RETENTION_DAYS="${RETENTION_DAYS:-90}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
POSTGRES_USER="${POSTGRES_USER:-ocweb}"
POSTGRES_DB="${POSTGRES_DB:-ocweb}"

mkdir -p "$BACKUP_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
SQL_FILE="$BACKUP_DIR/db_${TS}.sql.gz"
MEDIA_FILE="$BACKUP_DIR/media_${TS}.tar.gz"

echo "[$(date -Iseconds)] Backup starting → $BACKUP_DIR"

# 1) Postgres dump
docker compose -f "$COMPOSE_FILE" exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
    | gzip > "$SQL_FILE"
echo "  → $(basename "$SQL_FILE") ($(du -h "$SQL_FILE" | awk '{print $1}'))"

# 2) Media tarball
docker compose -f "$COMPOSE_FILE" exec -T web \
    tar -czf - -C /app/media example_figures examples \
    > "$MEDIA_FILE"
echo "  → $(basename "$MEDIA_FILE") ($(du -h "$MEDIA_FILE" | awk '{print $1}'))"

# 3) Prune old files
PRUNED=$(find "$BACKUP_DIR" -maxdepth 1 \
    \( -name 'db_*.sql.gz' -o -name 'media_*.tar.gz' \) \
    -mtime +"$RETENTION_DAYS" -print -delete | wc -l)
if [ "$PRUNED" -gt 0 ]; then
  echo "  pruned $PRUNED file(s) older than ${RETENTION_DAYS}d"
fi

echo "[$(date -Iseconds)] Backup complete"
