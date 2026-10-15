#!/usr/bin/env bash
# Logical backup of the app database from the running Compose stack (#15). Custom-format pg_dump, mode 600, pruned by age.
# This is the DUMP path only: it is not the WAL-G point-in-time backup of the blueprint, has no offsite copy, and the
# RPO is the interval between runs (L-014). Run it nightly from cron or a systemd timer as the deploy user.
#
#   BACKUP_DIR=/var/backups/rentmonitor BACKUP_KEEP_DAYS=7 scripts/backup_db.sh
#   COMPOSE_FILES="-f deploy/compose.yml -f deploy/compose.prod.yml"   (default)
# Prints the dump path and size, never any credential. Exit status is non-zero if the dump is missing or empty.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/rentmonitor}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
COMPOSE_FILES="${COMPOSE_FILES:--f deploy/compose.yml -f deploy/compose.prod.yml}"
# shellcheck disable=SC2206
COMPOSE=(docker compose $COMPOSE_FILES)
DB="${POSTGRES_DB:-rentmonitor}"
USER_="${POSTGRES_USER:-rentmonitor}"

umask 077
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/rm-$STAMP.dump"
TMP="$OUT.partial"
trap 'rm -f "$TMP"' EXIT

"${COMPOSE[@]}" exec -T postgres pg_dump -U "$USER_" -d "$DB" --format=custom --no-owner > "$TMP"
[ -s "$TMP" ] || { echo "backup_db: empty dump" >&2; exit 1; }
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$TMP" > /dev/null || { echo "backup_db: dump is not readable" >&2; exit 1; }
mv "$TMP" "$OUT"
trap - EXIT
find "$BACKUP_DIR" -name 'rm-*.dump' -type f -mtime "+$BACKUP_KEEP_DAYS" -delete
echo "backup_db: OK $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
if [ -n "${BACKUP_HEARTBEAT_URL:-}" ]; then curl -fsS -m 10 "$BACKUP_HEARTBEAT_URL" > /dev/null || echo "backup_db: heartbeat failed" >&2; fi
