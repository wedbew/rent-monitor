#!/usr/bin/env bash
# Local backup/restore drill against the dev Postgres: dump -> restore into a scratch DB -> compare row counts.
# Proves the dump/restore path works on a developer machine; it is NOT the WAL-G point-in-time drill (release gate 6).
set -euo pipefail

COMPOSE=(docker compose -f deploy/compose.yml)
DB="${POSTGRES_DB:-rentmonitor}"
USER_="${POSTGRES_USER:-rentmonitor}"
SCRATCH="${DB}_drill"
STARTED=$(date +%s)

psql_() { "${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$USER_" "$@"; }

counts() {
  psql_ -d "$1" -At -c "SELECT string_agg(relname || '=' || n_live_tup, ',' ORDER BY relname) FROM pg_stat_user_tables WHERE schemaname='app'"
}
exact() {
  for t in $(psql_ -d "$1" -At -c "SELECT tablename FROM pg_tables WHERE schemaname='app' ORDER BY 1"); do
    echo "$t=$(psql_ -d "$1" -At -c "SELECT count(*) FROM app.\"$t\"")"
  done
}

psql_ -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH\"" -c "CREATE DATABASE \"$SCRATCH\""
"${COMPOSE[@]}" exec -T postgres pg_dump -U "$USER_" -d "$DB" --format=custom --no-owner \
  | "${COMPOSE[@]}" exec -T postgres pg_restore -U "$USER_" -d "$SCRATCH" --no-owner --exit-on-error

if diff <(exact "$DB") <(exact "$SCRATCH") >/dev/null; then
  echo "backup-drill: OK ($(( $(date +%s) - STARTED )) s) tables: $(exact "$DB" | wc -l | tr -d ' ')"
  psql_ -d postgres -c "DROP DATABASE \"$SCRATCH\"" >/dev/null
else
  echo "backup-drill: MISMATCH between $DB and $SCRATCH" >&2
  diff <(exact "$DB") <(exact "$SCRATCH") >&2 || true
  exit 1
fi
