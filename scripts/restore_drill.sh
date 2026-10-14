#!/usr/bin/env bash
# Restore drill for a logical dump made by scripts/backup_db.sh: verify checksum, restore into a scratch database,
# compare exact row counts per app table with the live database, report the elapsed time, drop the scratch database.
# Evidence for the logical path only; the WAL-G point-in-time drill is release gate 6 (RM-15).
#
#   ./scripts/restore_drill.sh backups/rentmonitor-<stamp>.dump
# An encrypted dump (.age) needs AGE_IDENTITY (path to the private key file, kept off the host in production).
set -euo pipefail

DUMP="${1:?usage: restore_drill.sh <dump file>}"
DB="${POSTGRES_DB:-rentmonitor}"
USER_="${POSTGRES_USER:-rentmonitor}"
SCRATCH="${DB}_restore_drill"
read -r -a FILES <<<"${COMPOSE_FILES:--f deploy/compose.yml}"
COMPOSE=(docker compose "${FILES[@]}")
STARTED=$(date +%s)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

[ -f "$DUMP" ] || { echo "restore_drill: $DUMP not found" >&2; exit 1; }
if [ -f "$DUMP.sha256" ]; then
  (cd "$(dirname "$DUMP")" && sha256sum --check --quiet "$(basename "$DUMP").sha256") ||
    { echo "restore_drill: CHECKSUM MISMATCH" >&2; exit 1; }
else
  echo "restore_drill: no .sha256 beside the dump, skipping checksum" >&2
fi

SRC="$DUMP"
if [ "${DUMP##*.}" = age ]; then
  : "${AGE_IDENTITY:?encrypted dump: set AGE_IDENTITY to the private key file}"
  age -d -i "$AGE_IDENTITY" -o "$TMP/plain.dump" "$DUMP"
  SRC="$TMP/plain.dump"
fi

psql_() { "${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$USER_" "$@"; }
exact() {
  for t in $(psql_ -d "$1" -At -c "SELECT tablename FROM pg_tables WHERE schemaname='app' ORDER BY 1"); do
    echo "$t=$(psql_ -d "$1" -At -c "SELECT count(*) FROM app.\"$t\"")"
  done
}

psql_ -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH\"" -c "CREATE DATABASE \"$SCRATCH\"" >/dev/null
"${COMPOSE[@]}" exec -T postgres pg_restore -U "$USER_" -d "$SCRATCH" --no-owner --exit-on-error <"$SRC"

exact "$DB" >"$TMP/live.txt"
exact "$SCRATCH" >"$TMP/restored.txt"
psql_ -d postgres -c "DROP DATABASE \"$SCRATCH\"" >/dev/null
SECONDS_TAKEN=$(($(date +%s) - STARTED))

# Rows written after the dump legitimately differ on a busy database; a drill on a quiet one must match exactly.
if diff "$TMP/live.txt" "$TMP/restored.txt" >/dev/null; then
  echo "restore_drill: OK in ${SECONDS_TAKEN} s, $(wc -l <"$TMP/live.txt" | tr -d ' ') tables identical"
else
  echo "restore_drill: row counts differ from the live database (writes since the dump, or a failed restore):" >&2
  diff "$TMP/live.txt" "$TMP/restored.txt" >&2 || true
  exit 1
fi
