#!/usr/bin/env bash
# Copy selected variables from a LOCAL env file into /opt/rent-monitor/.env on the deploy host, over SSH (#220).
# Only the names you list are sent; values are never printed, logged or put on a command line (they travel on stdin).
# Run it yourself: agents must not read env files (.agent/agents.md section 4).
#
#   scripts/push_env_to_host.sh PADDLE_API_KEY PADDLE_WEBHOOK_SECRET PADDLE_PRICE_REPORTS_1 ...
#   ENV_FILE=.env HOST=deploy@vps-d1af13a5.vps.ovh.net REMOTE_ENV=/opt/rent-monitor/.env scripts/push_env_to_host.sh NAME...
# The host file is copied to <file>.bak once per run, kept at mode 600, and existing names are replaced in place.
# Restart the stack afterwards (docs/RUNBOOK-DEPLOY.md section 1) so containers pick the values up.
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
HOST="${HOST:-deploy@vps-d1af13a5.vps.ovh.net}"
REMOTE_ENV="${REMOTE_ENV:-/opt/rent-monitor/.env}"

[ "$#" -ge 1 ] || { echo "usage: $0 NAME [NAME...]" >&2; exit 2; }
[ -f "$ENV_FILE" ] || { echo "push_env_to_host: $ENV_FILE not found" >&2; exit 2; }
[[ "$REMOTE_ENV" =~ ^/[A-Za-z0-9_./-]+$ ]] || { echo "push_env_to_host: unsafe REMOTE_ENV" >&2; exit 2; }

payload=""
for name in "$@"; do
  [[ "$name" =~ ^[A-Z][A-Z0-9_]*$ ]] || { echo "push_env_to_host: bad name '$name'" >&2; exit 2; }
  line="$(grep -E "^${name}=" "$ENV_FILE" | tail -n 1 || true)"
  [ -n "$line" ] || { echo "push_env_to_host: $name is not set in $ENV_FILE" >&2; exit 1; }
  [ -n "${line#*=}" ] || { echo "push_env_to_host: $name is empty in $ENV_FILE" >&2; exit 1; }
  # Compose reads a trailing "# comment" as part of the value (docs/RUNBOOK-DEPLOY.md section 0).
  case "${line#*=}" in *" #"*) echo "push_env_to_host: $name has an inline comment; remove it" >&2; exit 1 ;; esac
  payload+="${line}"$'\n'
done

# Remote merge: stdin carries NAME=value lines; names present are replaced in place, the rest appended.
remote_script='
set -euo pipefail
umask 077
target="'"$REMOTE_ENV"'"
[ -f "$target" ] || { echo "remote: $target not found" >&2; exit 1; }
incoming="$(mktemp)"; merged="$(mktemp)"
trap "rm -f \"$incoming\" \"$merged\"" EXIT
cat > "$incoming"
cp -p "$target" "$target.bak"
awk -F= "NR==FNR { v[\$1]=\$0; next } (\$1 in v) { print v[\$1]; seen[\$1]=1; next } { print } END { for (k in v) if (!(k in seen)) print v[k] }" "$incoming" "$target" > "$merged"
cat "$merged" > "$target"
chmod 600 "$target"
echo "remote: updated $(wc -l < "$incoming" | tr -d " ") name(s) in $target"
'

printf '%s' "$payload" | ssh "$HOST" "$remote_script"
echo "push_env_to_host: sent $# name(s); values not shown"
