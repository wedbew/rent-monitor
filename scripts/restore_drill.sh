#!/usr/bin/env bash
# Restore a dump from backup_db.sh into a scratch database and compare exact table row counts with the live one (#15).
# Never touches the live database. Prints the elapsed time as restore evidence for docs/PRE-DEPLOYMENT.md (gate 6 asks for
# the WAL-G point-in-time restore on a fresh VPS; this proves only that the logical dump restores).
#
#   scripts/restore_drill.sh /var/backups/rentmonitor/rm-20261014T031500Z.dump
set -euo pipefail

DUMP="${1:?usage: restore_drill.sh <dump file>}"
[ -s "$DUMP" ] || { echo "restore_drill: no such dump" >&2; exit 1; }
COMPOSE_FILES="${COMPOSE_FILES:--f deploy/compose.yml -f deploy/compose.prod.yml}"
# shellcheck disable=SC2206
COMPOSE=(docker compose $COMPOSE_FILES)
DB="${POSTGRES_DB:-rentmonitor}"
USER_="${POSTGRES_USER:-rentmonitor}"
SCRATCH="${DB}_restore_drill"
STARTED=$(date +%s)

psql_() { "${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$USER_" "$@"; }
exact() {
  for t in $(psql_ -d "$1" -At -c "SELECT tablename FROM pg_tables WHERE schemaname='app' ORDER BY 1"); do
    echo "$t=$(psql_ -d "$1" -At -c "SELECT count(*) FROM app.\"$t\"")"
  done
}

psql_ -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH\"" -c "CREATE DATABASE \"$SCRATCH\"" > /dev/null
trap 'psql_ -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH\"" > /dev/null 2>&1 || true' EXIT
"${COMPOSE[@]}" exec -T postgres pg_restore -U "$USER_" -d "$SCRATCH" --no-owner --exit-on-error < "$DUMP"
ELAPSED=$(( $(date +%s) - STARTED ))
LIVE="$(exact "$DB")"
RESTORED="$(exact "$SCRATCH")"
if [ "$LIVE" = "$RESTORED" ]; then
  echo "restore_drill: OK in ${ELAPSED}s, $(echo "$RESTORED" | wc -l | tr -d ' ') tables identical to live (dump: $(basename "$DUMP"))"
else
  echo "restore_drill: MISMATCH (rows differ; expected if the app wrote since the dump)" >&2
  diff <(echo "$LIVE") <(echo "$RESTORED") >&2 || true
  exit 2
fi
