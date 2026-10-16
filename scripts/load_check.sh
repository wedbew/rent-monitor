#!/usr/bin/env bash
# Bounded synthetic load check for gates 4 and 5 (#35, #36): runs scripts/load_check.py in the api container and
# records the worker cgroups' memory.peak around it. Run it on the host that runs the stack, from the repo root:
#
#   scripts/load_check.sh [AUDITS]        # 1..25, default 5; ramp 5, 10, 20 and look before going up
#
# Evidence class: fake provider data, synthetic load, one run (see load_check.py). Stop conditions, checked before the
# run: no unhealthy core service, at least 15 % free disk and 1.5 GiB available memory. The python side stops itself at
# 70 database connections or its deadline. Nothing is deleted except the rows the run planted (`--cleanup-stale`
# removes leftovers of a killed run). Never run it where real customer data lives.
set -euo pipefail

cd "$(dirname "$0")/.."
AUDITS="${1:-5}"
COMPOSE_FILES="${COMPOSE_FILES:-deploy/compose.yml deploy/compose.prod.yml}"
args=()
for f in $COMPOSE_FILES; do [ -f "$f" ] && args+=(-f "$f"); done
COMPOSE=(docker compose "${args[@]}")

die() { echo "load_check: $*" >&2; exit 2; }
[[ "$AUDITS" =~ ^[0-9]+$ ]] && [ "$AUDITS" -ge 1 ] && [ "$AUDITS" -le 25 ] || die "AUDITS must be 1..25"

# --- stop conditions -------------------------------------------------------------------------------------------
used=$(df -P / | awk 'NR==2{gsub("%","",$5); print $5}')
[ "$used" -le 85 ] || die "disk is ${used}% used (need at least 15% free)"
avail_mb=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 99999)
[ "$avail_mb" -ge 1536 ] || die "only ${avail_mb} MiB memory available (need 1536)"
for svc in postgres api worker-audit; do
  state=$("${COMPOSE[@]}" ps --format '{{.Service}} {{.Health}} {{.State}}' "$svc" 2>/dev/null | head -1 || true)
  case "$state" in *unhealthy*|*exited*|"") die "service $svc is not healthy: '${state}'" ;; esac
done

cgroup() { # <service>: "peak max current" in bytes, or "- - -" when the kernel does not expose them
  "${COMPOSE[@]}" exec -T "$1" sh -c 'p=/sys/fs/cgroup; echo "$(cat $p/memory.peak 2>/dev/null || echo -) $(cat $p/memory.max 2>/dev/null || echo -) $(cat $p/memory.current 2>/dev/null || echo -)"' 2>/dev/null || echo "- - -"
}
before_audit=$(cgroup worker-audit)
before_ops=$(cgroup worker-ops)

# --- the run -----------------------------------------------------------------------------------------------------
# The script is piped in, so the image does not have to contain it (a host on an older commit works too).
report=$("${COMPOSE[@]}" exec -T api python - --audits "$AUDITS" --base-url http://localhost:8000 < scripts/load_check.py) || status=$?
status="${status:-0}"

after_audit=$(cgroup worker-audit)
after_ops=$(cgroup worker-ops)
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
printf '%s' "$report" > "$tmp"
python3 - "$status" "$before_audit" "$after_audit" "$before_ops" "$after_ops" "$tmp" <<'PY'
import json, sys
status, ba, aa, bo, ao, path = sys.argv[1:7]
def mem(line):
    peak, limit, current = line.split()
    num = lambda v: None if v in ("-", "max") else int(v)
    return {"peak": num(peak), "limit": num(limit), "current": num(current)}
def view(before, after):
    b, a = mem(before), mem(after)
    pct = None if a["peak"] is None or not a["limit"] else round(100 * a["peak"] / a["limit"], 1)
    return {"before": b, "after": a, "peak_percent_of_limit": pct,
            "gate4_concurrency_2_allowed": None if pct is None else pct < 60}
text = open(path).read().strip()
try:
    report = json.loads(text)
except ValueError:
    report = {"raw": text}
print(json.dumps({"load": report, "worker_audit": view(ba, aa), "worker_ops": view(bo, ao),
                  "note": "memory.peak is the cgroup high-water mark since the container started unless reset; compare before/after"}, indent=2))
sys.exit(int(status))
PY
