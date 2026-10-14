#!/usr/bin/env bash
# Owner-run helper: copy named variables from the LOCAL .env into the host's .env without printing any value.
#
#   bash scripts/push_env_to_host.sh [--restart] NAME [NAME ...]
#   bash scripts/push_env_to_host.sh --restart PADDLE_API_KEY PADDLE_WEBHOOK_SECRET BILLING_PROVIDER
#
# Run it from the repository root. It reads each `NAME=value` line from ./.env, sends the lines over ssh on
# stdin (never in argv or the log), replaces or appends them in the host's .env, keeps mode 600 and prints only
# `set NAME (N chars)`. A missing or empty value is an error. `--restart` then recreates the api and both
# workers on the host's current image and prints the health check.
# Settings: DEPLOY_HOST (default deploy@vps-d1af13a5.vps.ovh.net), REMOTE_ENV (default /opt/rent-monitor/.env).
set -euo pipefail

HOST="${DEPLOY_HOST:-deploy@vps-d1af13a5.vps.ovh.net}"
REMOTE_ENV="${REMOTE_ENV:-/opt/rent-monitor/.env}"
RESTART=0
if [ "${1:-}" = "--restart" ]; then RESTART=1; shift; fi
[ "$#" -ge 1 ] || { echo "usage: $0 [--restart] NAME [NAME ...]" >&2; exit 2; }
[ -f .env ] || { echo "run from the repository root: ./.env not found" >&2; exit 2; }

PATTERN=""
for name in "$@"; do
  [[ "$name" =~ ^[A-Z][A-Z0-9_]*$ ]] || { echo "refusing odd variable name: $name" >&2; exit 2; }
  value="$(grep -E "^${name}=" .env | head -1 | cut -d= -f2- || true)"
  [ -n "$value" ] || { echo "$name is missing or empty in the local .env" >&2; exit 1; }
  PATTERN="${PATTERN:+$PATTERN|}$name"
done

PY='
import os, re, sys
names = sys.argv[1:]
path = os.environ["REMOTE_ENV"]
found = {}
for line in sys.stdin.read().splitlines():
    name, _, value = line.partition("=")
    if name in names and value:
        found[name] = value
missing = [n for n in names if n not in found]
if missing:
    sys.exit("not received: " + ", ".join(missing))
text = open(path).read()
for name, value in found.items():
    line = f"{name}={value}"
    if re.search(rf"(?m)^{name}=", text):
        text = re.sub(rf"(?m)^{name}=.*$", lambda m: line, text)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    print(f"set {name} ({len(value)} chars)")
open(path, "w").write(text)
os.chmod(path, 0o600)
'

grep -E "^(${PATTERN})=" .env | ssh -o BatchMode=yes "$HOST" "REMOTE_ENV='$REMOTE_ENV' python3 -c '$PY' $*"

if [ "$RESTART" = 1 ]; then
  ssh -o BatchMode=yes "$HOST" 'cd /opt/rent-monitor &&
    export IMAGE_TAG=$(grep -E "^IMAGE_TAG=" .env | cut -d= -f2) &&
    dc() { docker compose --env-file .env --profile public -f deploy/compose.yml -f deploy/compose.prod.yml "$@"; }
    dc run --rm --no-deps --entrypoint python api scripts/check_env.py 2>&1 | grep -E "ERROR|WARN|check_env"
    dc up -d --force-recreate --wait api worker-ops worker-audit 2>&1 | tail -3
    curl -sS https://renti.tech/api/health; echo'
fi
