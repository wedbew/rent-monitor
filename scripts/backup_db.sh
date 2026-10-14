#!/usr/bin/env bash
# Logical backup of the compose Postgres: pg_dump (custom format) + sha256, optional age encryption, local retention.
# This is NOT the WAL-G point-in-time backup and nothing leaves the host (offsite/R2 and WAL-G stay in RM-15, gate 6).
#
#   ./scripts/backup_db.sh                 # writes backups/rentmonitor-<UTC stamp>.dump[.age] and a .sha256 beside it
# Env: BACKUP_DIR (default backups), BACKUP_AGE_RECIPIENT (age public key; when set the dump is encrypted and the
#      plaintext removed), BACKUP_RETENTION_DAILY (default 14, newest N kept), COMPOSE_FILES (default base file).
# GDPR[retention]: dumps hold personal data; local retention is BACKUP_RETENTION_DAILY copies, erasure requests are
# re-applied after a restore (docs/RUNBOOK-GDPR.md) (RM-224).
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP="${BACKUP_RETENTION_DAILY:-14}"
DB="${POSTGRES_DB:-rentmonitor}"
USER_="${POSTGRES_USER:-rentmonitor}"
read -r -a FILES <<<"${COMPOSE_FILES:--f deploy/compose.yml}"
COMPOSE=(docker compose "${FILES[@]}")
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BACKUP_DIR/rentmonitor-$STAMP.dump"

umask 077
mkdir -p "$BACKUP_DIR"
"${COMPOSE[@]}" exec -T postgres pg_dump -U "$USER_" -d "$DB" --format=custom --no-owner >"$OUT.partial"
[ -s "$OUT.partial" ] || { echo "backup_db: empty dump" >&2; rm -f "$OUT.partial"; exit 1; }
mv "$OUT.partial" "$OUT"

if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
  command -v age >/dev/null || { echo "backup_db: BACKUP_AGE_RECIPIENT set but 'age' is not installed" >&2; exit 1; }
  age -r "$BACKUP_AGE_RECIPIENT" -o "$OUT.age" "$OUT"
  rm -f "$OUT"
  OUT="$OUT.age"
fi
(cd "$BACKUP_DIR" && sha256sum "$(basename "$OUT")" >"$(basename "$OUT").sha256")

# Keep the newest $KEEP dumps (pairs of dump + checksum).
# shellcheck disable=SC2012
ls -1t "$BACKUP_DIR"/rentmonitor-*.dump "$BACKUP_DIR"/rentmonitor-*.dump.age 2>/dev/null | tail -n +"$((KEEP + 1))" |
  while read -r old; do rm -f "$old" "$old.sha256"; done

echo "backup_db: OK $OUT ($(wc -c <"$OUT" | tr -d ' ') bytes, encrypted: $([ "${OUT##*.}" = age ] && echo yes || echo no))"
