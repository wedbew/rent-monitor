#!/usr/bin/env bash
# Run the whole stack for manual testing: API + Postgres + workers (Docker, fake providers) and the built SPA.
#
#   scripts/dev_stack.sh up      start everything, seed a user and a listing, serve the SPA (Ctrl+C stops the SPA)
#   scripts/dev_stack.sh seed    only seed another user and listing into the running stack
#   scripts/dev_stack.sh down    stop the containers (keeps the database; add --wipe to delete it)
#
# Evidence class: fake provider data (planted listing, test risk-free rate, no OpenRouter key). Not provider evidence.
# Override: API_PORT (default: first free of 8001..8010), POSTGRES_PORT (first free of 5432..5442), WEB_PORT (default 4173; must match compose.e2e.yml).
set -euo pipefail

cd "$(dirname "$0")/.."
WEB_PORT="${WEB_PORT:-4173}"
COMPOSE=(docker compose -f deploy/compose.yml -f deploy/compose.e2e.yml)
SEED=("${COMPOSE[@]}" exec -T api python scripts/e2e_session.py)

die() { echo "error: $*" >&2; exit 1; }

port_free() { ! lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# pick_port <preferred override> <first> <last>: the override if set, else the first free port in the range.
pick_port() {
  if [ -n "$1" ]; then echo "$1"; return; fi
  local p
  for p in $(seq "$2" "$3"); do
    if port_free "$p"; then echo "$p"; return; fi
  done
  die "no free port in $2..$3"
}

use_node_24() {
  local want major; want="$(tr -d '[:space:]' < frontend/.node-version)"; major="${want%%.*}"
  node_ok() { node -v 2>/dev/null | grep -q "^v${major}\."; }
  if node_ok; then return; fi
  # nvm reads .nvmrc, not .node-version, so pass the version explicitly; it must run in this shell to change PATH
  # (and nvm is not written for `set -u`).
  if [ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]; then
    set +u
    # shellcheck disable=SC1091
    . "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
    nvm use "$want" >/dev/null 2>&1 || nvm use "$major" >/dev/null 2>&1 || true
    set -u
  fi
  node_ok || die "Node ${major} needed (frontend/.node-version is ${want}); run: nvm install ${want}"
}

seed() {
  echo "== seeding (synthetic user with 5 credits, one sale listing, one rental listing)"
  "${SEED[@]}" create --credits 5
  echo "-- put the printed session token in the browser as cookie 'rm_session' for http://localhost:${WEB_PORT}"
  echo "-- listing refs to paste into 'new analysis':"
  "${SEED[@]}" plant-listing --kind sale
  "${SEED[@]}" plant-listing --kind rent
}

cmd_up() {
  command -v docker >/dev/null || die "docker not found"
  docker info >/dev/null 2>&1 || die "docker is not running"
  command -v pnpm >/dev/null || { command -v corepack >/dev/null && corepack enable; }
  use_node_24
  [ -f .env ] || { cp .env.example .env; echo "created .env from .env.example (defaults, no secrets)"; }
  port_free "$WEB_PORT" || die "port ${WEB_PORT} is in use; the API's PUBLIC_APP_URL is http://localhost:4173, so stop what uses it"

  export API_PORT; API_PORT="$(pick_port "${API_PORT:-}" 8001 8010)"
  # Host port for Postgres (compose publishes 127.0.0.1:$POSTGRES_PORT); containers reach it by service name.
  export POSTGRES_PORT; POSTGRES_PORT="$(pick_port "${POSTGRES_PORT:-}" 5432 5442)"
  # Apple Silicon: the images are amd64-only (L-021).
  if [ "$(uname -m)" = "arm64" ]; then export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM:-linux/amd64}"; fi

  echo "== starting API (127.0.0.1:${API_PORT}), Postgres (127.0.0.1:${POSTGRES_PORT}) and workers"
  "${COMPOSE[@]}" up -d --build --wait api worker-audit worker-ops

  local title
  title="$(curl -fsS -m 5 "http://127.0.0.1:${API_PORT}/api/openapi.json" 2>/dev/null \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["info"]["title"])' 2>/dev/null)" \
    || die "port ${API_PORT} did not answer /api/openapi.json (is APP_ENV=production in .env? it hides the docs)"
  [ "$title" = "Renti API" ] || die "port ${API_PORT} is '${title}', not RentMonitor; set API_PORT to a free port"
  echo "backend identity: ${title}"

  seed

  echo "== building and serving the SPA"
  export API_ORIGIN="http://127.0.0.1:${API_PORT}"
  (cd frontend && pnpm install --frozen-lockfile && pnpm build)
  echo
  echo "Open http://localhost:${WEB_PORT}   (API ${API_ORIGIN}; stop the SPA with Ctrl+C, containers with: $0 down)"
  cd frontend && exec pnpm preview --port "$WEB_PORT" --strictPort
}

case "${1:-}" in
  up) cmd_up ;;
  seed) export API_PORT="${API_PORT:-8001}"; seed ;;
  down)
    if [ "${2:-}" = "--wipe" ]; then "${COMPOSE[@]}" down -v; else "${COMPOSE[@]}" down; fi ;;
  *) echo "usage: $0 up | seed | down [--wipe]"; exit 2 ;;
esac
