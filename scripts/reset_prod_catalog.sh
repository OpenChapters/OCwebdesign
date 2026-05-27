#!/usr/bin/env bash
#
# Reset the OpenChapters PRODUCTION catalog to a clean, pre-sync state.
#
# Deletes every chapter, worked example, user-assembled book and frozen
# snapshot (and their on-disk artifacts), then re-syncs the catalog from the
# monorepo. User ACCOUNTS, disciplines, site config and the audit log are
# preserved — see catalog/management/commands/reset_catalog.py for the exact
# tables touched.
#
# Run this ON THE PRODUCTION HOST, from the repo root, AFTER the consolidated
# chapters have been pushed to the OpenChapters monorepo.
#
# It is deliberately interactive and takes a full database backup first.
# Nothing is deleted until you type RESET at the prompt.

set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="db-backup-pre-reset-${STAMP}.sql"

cat <<'BANNER'
================================================================
  PRODUCTION CATALOG RESET
  This PERMANENTLY deletes all chapters, examples, books and
  frozen snapshots (and their files on disk), then re-syncs the
  catalog from the monorepo.
  Preserved: user accounts, disciplines, site settings, audit log.
================================================================
BANNER

read -r -p "Type RESET to continue: " reply
if [[ "${reply}" != "RESET" ]]; then
  echo "Aborted — nothing was changed."
  exit 1
fi

echo
echo "[1/5] Backing up the database to ${BACKUP} ..."
# pg_dump runs inside the db container; POSTGRES_USER/DB come from its env.
${COMPOSE} exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "${BACKUP}"
if [[ ! -s "${BACKUP}" ]]; then
  echo "Backup is empty — aborting before any deletion." >&2
  rm -f "${BACKUP}"
  exit 1
fi
echo "      backup saved ($(du -h "${BACKUP}" | cut -f1))."

echo
echo "[2/5] Previewing the reset (dry run) ..."
${COMPOSE} run --rm web python manage.py reset_catalog --dry-run

echo
echo "[3/5] Deleting catalog/book content and on-disk artifacts ..."
${COMPOSE} run --rm web python manage.py reset_catalog

echo
echo "[4/5] Clearing the warm git clone cache (worker-only volume) ..."
${COMPOSE} run --rm worker-builds sh -c 'rm -rf /app/git-cache/* /app/git-cache/.[!.]* || true'

echo
echo "[5/5] Re-syncing the catalog from the monorepo ..."
${COMPOSE} run --rm web python manage.py sync_chapters

echo
echo "Done. Pre-reset backup retained at: ${BACKUP}"
echo "If HTML builds are enabled, per-chapter HTML/labels regenerate on the"
echo "next nightly sync, or trigger them now from the admin sync action."
