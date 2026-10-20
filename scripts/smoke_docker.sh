#!/usr/bin/env bash
# Builds and starts the whole app in Docker, checks it answers, then stops it (data volume is kept; `make down -v` drops it).
# Uses spare host ports so it does not collide with a database or API already running locally.
set -euo pipefail
export POSTGRES_PORT="${POSTGRES_PORT:-55433}" API_PORT="${API_PORT:-18000}"
COMPOSE=(docker compose -f deploy/compose.yml)
cleanup() { "${COMPOSE[@]}" --profile web down >/dev/null 2>&1 || true; }
trap cleanup EXIT

"${COMPOSE[@]}" up -d --build --wait api worker-audit worker-ops worker-batch

fail() { echo "smoke: FAIL: $1" >&2; "${COMPOSE[@]}" logs --tail=40 >&2; exit 1; }
curl -fsS "http://127.0.0.1:${API_PORT}/api/health" | grep -q '"ok"' || fail "/api/health"
"${COMPOSE[@]}" exec -T api python -c "import json,urllib.request as u; d=json.load(u.urlopen('http://localhost:8000/readyz')); assert d['status']=='ok', d" || fail "/readyz (db + queue)"
ADDR=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${API_PORT}/nope")
[ "$ADDR" = "404" ] || fail "unknown route should be 404, got $ADDR"
[ "$("${COMPOSE[@]}" ps --status running --services | grep -c worker)" = "2" ] || fail "audit and ops workers not both running"
PLANS=$("${COMPOSE[@]}" exec -T postgres psql -U "${POSTGRES_USER:-rentmonitor}" -d "${POSTGRES_DB:-rentmonitor}" -Atc "select count(*) from app.plan")
[ "$PLANS" = "2" ] || fail "seed did not create the two plans (got $PLANS)"

# ---- the public web image (RM-281): SPA, caching, CSP and /api through Caddy, as served in production.
export WEB_PORT="${WEB_PORT:-18443}"
"${COMPOSE[@]}" --profile web up -d --build --wait web || fail "web image did not start"
WEB="https://localhost:${WEB_PORT}"
get() { curl -sk -o /dev/null -D - "$WEB$1"; }   # headers only; -k: Caddy's internal CA for localhost
body() { curl -sk "$WEB$1"; }
status() { get "$1" | head -1 | awk '{print $2}'; }
header() { get "$1" | tr -d '\r' | awk -F': ' -v h="$(echo "$2" | tr 'A-Z' 'a-z')" 'tolower($1)==h {print $2}'; }

for path in / /app /app/analyses/new /app/analyses/00000000-0000-4000-8000-000000000001 /login; do
  [ "$(status "$path")" = "200" ] || fail "web: $path should be the app (200), got $(status "$path")"
  body "$path" | grep -q '<div id="root">' || fail "web: $path is not index.html"
  [ "$(header "$path" cache-control)" = "no-cache" ] || fail "web: $path must be revalidated (no-cache)"
done
CSP=$(header / content-security-policy)
for part in "default-src 'none'" "script-src 'self' https://accounts.google.com/gsi/client" "frame-ancestors 'none'" "object-src 'none'"; do
  echo "$CSP" | grep -qF "$part" || fail "web: CSP lacks: $part"
done
echo "$CSP" | grep -q "unsafe-inline\|unsafe-eval" && fail "web: CSP must not allow inline or eval"
[ "$(header / strict-transport-security)" = "max-age=31536000" ] || fail "web: HSTS missing"

ASSET=$(body / | grep -o '/assets/index-[A-Za-z0-9_-]*\.js' | head -1)
[ -n "$ASSET" ] || fail "web: no entry script referenced from index.html"
[ "$(status "$ASSET")" = "200" ] || fail "web: $ASSET not served"
header "$ASSET" content-type | grep -q "javascript" || fail "web: $ASSET has the wrong MIME type"
header "$ASSET" cache-control | grep -q "immutable" || fail "web: hashed assets must be immutable"
[ "$(status /assets/index-gone.js)" = "404" ] || fail "web: a missing asset must be 404, never index.html"

[ "$(status /api/health)" = "200" ] || fail "web: /api/health through Caddy"
NOPE=$(curl -sk -D - "$WEB/api/nope" -o /tmp/rm-web-nope.json | tr -d '\r')
echo "$NOPE" | head -1 | grep -q " 404" || fail "web: unknown /api path should be 404"
grep -q '"code"' /tmp/rm-web-nope.json || fail "web: unknown /api path must answer problem JSON, not the app"
[ "$(status /healthz)" = "404" ] || fail "web: internal probes must not be public"

echo "smoke: OK (api, readyz, audit + ops workers, seed; web: deep links, assets, caching, CSP, /api through Caddy)"
