#!/usr/bin/env bash
# Builds and starts the whole app in Docker, checks it answers, then stops it (data volume is kept; `make down -v` drops it).
# Uses spare host ports so it does not collide with a database or API already running locally.
set -euo pipefail
export POSTGRES_PORT="${POSTGRES_PORT:-55433}" API_PORT="${API_PORT:-18000}"
COMPOSE=(docker compose -f deploy/compose.yml)
cleanup() { "${COMPOSE[@]}" down >/dev/null 2>&1 || true; }
trap cleanup EXIT

"${COMPOSE[@]}" up -d --build --wait api worker

fail() { echo "smoke: FAIL: $1" >&2; "${COMPOSE[@]}" logs --tail=40 >&2; exit 1; }
curl -fsS "http://127.0.0.1:${API_PORT}/api/health" | grep -q '"ok"' || fail "/api/health"
"${COMPOSE[@]}" exec -T api python -c "import json,urllib.request as u; d=json.load(u.urlopen('http://localhost:8000/readyz')); assert d['status']=='ok', d" || fail "/readyz (db + queue)"
ADDR=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/nope")
[ "$ADDR" = "404" ] || fail "unknown route should be 404, got $ADDR"
[ "$("${COMPOSE[@]}" ps --status running --services | grep -c worker)" = "1" ] || fail "worker not running"
PLANS=$("${COMPOSE[@]}" exec -T postgres psql -U "${POSTGRES_USER:-rentmonitor}" -d "${POSTGRES_DB:-rentmonitor}" -Atc "select count(*) from app.plan")
[ "$PLANS" = "2" ] || fail "seed did not create the two plans (got $PLANS)"
echo "smoke: OK (api, readyz, worker, seed)"
