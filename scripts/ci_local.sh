#!/usr/bin/env bash
# Runs the same checks as the GitHub pipeline (.github/workflows/{ci,security,pr-title}.yml) on your machine,
# so a push does not waste CI minutes. Needs: uv, Docker (integration tests, Testcontainers), network (security stages).
#
#   scripts/ci_local.sh --fast          commits, lint, types, unit tests            (about 1 min, used by the pre-push hook)
#   scripts/ci_local.sh                 everything CI runs, including integration tests, migrations, security
#   scripts/ci_local.sh --full          the above plus the Docker smoke test (`make smoke`)
#   scripts/ci_local.sh --only lint,types   run chosen stages only
#
# Every stage runs even if an earlier one fails, then a summary is printed. A stage whose tool is missing is reported as
# SKIPPED with the reason (never as a pass). Exit code is non-zero if any stage failed.
set -uo pipefail
cd "$(dirname "$0")/.."

MODE=normal ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --fast) MODE=fast ;;
    --full) MODE=full ;;
    --only) ONLY="$2"; shift ;;
    -h|--help) sed -n 2,13p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

BASE="origin/staging"
git rev-parse --verify -q "$BASE" >/dev/null || BASE="staging"
RESULTS=()
FAILED=0

want() { # stage name, tiers it belongs to (fast normal full)
  local name="$1"; shift
  [ -n "$ONLY" ] && { case ",$ONLY," in *",$name,"*) return 0 ;; *) return 1 ;; esac; }
  for tier in "$@"; do [ "$tier" = "$MODE" ] && return 0; done
  [ "$MODE" = full ] && return 0
  return 1
}

stage() { # name, command...
  local name="$1"; shift
  local start; start=$(date +%s)
  echo; echo "=== $name ==="
  if "$@"; then RESULTS+=("PASS     $name ($(( $(date +%s) - start ))s)")
  else RESULTS+=("FAIL     $name ($(( $(date +%s) - start ))s)"); FAILED=1; fi
}
skip() { echo; echo "=== $1: skipped ($2) ==="; RESULTS+=("SKIPPED  $1: $2"); }

have() { command -v "$1" >/dev/null 2>&1; }

st_commits() { python3 scripts/check_commit_msg.py --range "$BASE..HEAD"; }
st_lint() { uv run ruff check . && uv run ruff format --check .; } # SPA finance guard: ESLint in `frontend` (eslint.money.mjs)
st_types() { uv run pyright; }
st_types_ty() { uvx ty check packages services; }
st_unit() { uv run pytest -m "not e2e and not integration" -q; }
st_test() { uv run pytest -m "not e2e" --cov --cov-report=term-missing -q; }
st_invariants() { uv run pytest -m invariant -q -rs --junitxml=/tmp/rm-invariants.xml && python3 scripts/check_invariants.py /tmp/rm-invariants.xml; }
st_migrations() {
  uv run pytest tests/migrations -q || return 1
  env -u DATABASE_URL uv run alembic upgrade head --sql > /tmp/rm-migrations.sql || return 1
  npx --yes squawk-cli@2.68.0 /tmp/rm-migrations.sql
}
st_semgrep() {
  uvx semgrep==1.180.0 --test --metrics=off --config .semgrep/rentmonitor.yml .semgrep/rentmonitor.py \
    && uvx semgrep==1.180.0 scan --error --config p/python --config p/secrets --config .semgrep/ --metrics=off --quiet
}
# --disable-pip --no-deps: the export is fully pinned, and this avoids building a temporary virtualenv, which aborts
# (ensurepip) on some macOS Pythons. Same vulnerability database and strictness as CI.
st_audit() {
  uv export --all-packages --no-hashes --no-emit-workspace -o /tmp/rm-req.txt \
    && uvx pip-audit==2.10.1 -r /tmp/rm-req.txt --strict --disable-pip --no-deps
}
st_gitleaks() {
  if have gitleaks; then gitleaks git --redact --exit-code 1 --log-opts="$BASE..HEAD" .
  else docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 git --redact --exit-code 1 --log-opts="$BASE..HEAD" /repo; fi
}
st_actions() {
  uvx zizmor==1.30.1 --min-severity medium .github/workflows || return 1
  if have actionlint; then actionlint -color
  else docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12 -color; fi
}
st_smoke() { ./scripts/smoke_docker.sh; }
# The SPA's own gate: frozen install, then `pnpm check` (api drift, types, lint, css, format, unit tests, build).
st_frontend() { pnpm --dir frontend install --frozen-lockfile && pnpm --dir frontend check; }
# The browser lanes: Chromium against the built SPA with the mocked API, the interaction-coverage gate, axe.
# A free port of its own: Playwright reuses whatever already answers on its default port (4173, also used by
# scripts/dev_stack.sh and by a preview left behind), and then a run would test a build made without the test tokens.
st_frontend_e2e() {
  local port="${E2E_PORT:-}"
  [ -n "$port" ] || port=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
  E2E_PORT="$port" pnpm --dir frontend test:e2e
}
e2e_skip_reason() { # empty when Playwright's headless Chromium is installed
  local path; path=$(cd frontend && pnpm exec playwright install --dry-run chromium 2>/dev/null | awk '/Headless Shell/{f=1} f&&/Install location/{print $3; exit}')
  [ -n "$path" ] && [ -d "$path" ] || echo "Chromium for Playwright is not installed (cd frontend && pnpm exec playwright install chromium)"
}
frontend_skip_reason() { # empty when the pinned Node and pnpm are available
  have node || { echo "Node is not installed"; return; }
  have pnpm || { echo "pnpm is not installed (corepack enable)"; return; }
  local want have_v; want=$(cut -d. -f1 frontend/.node-version); have_v=$(node -p 'process.versions.node.split(".")[0]')
  [ "$want" = "$have_v" ] || echo "Node $have_v active, frontend/.node-version wants $want"
}

have uv || { echo "uv is required (https://docs.astral.sh/uv/)" >&2; exit 2; }
uv sync --all-packages --group dev -q || exit 2

want commits fast normal && stage commits st_commits
want lint fast normal && stage lint st_lint
want types fast normal && stage types st_types
want types-ty normal && stage types-ty st_types_ty
want unit fast && stage unit-tests st_unit
if want test normal; then
  if have docker && docker info >/dev/null 2>&1; then stage test st_test; else skip test "Docker is not running (integration tests need it)"; fi
fi
if want invariants normal; then
  if have docker && docker info >/dev/null 2>&1; then stage invariants st_invariants; else skip invariants "Docker is not running"; fi
fi
if want migrations normal; then
  if have docker && docker info >/dev/null 2>&1 && have npx; then stage migrations st_migrations; else skip migrations "needs Docker and npx"; fi
fi
want semgrep normal && stage semgrep st_semgrep
want audit normal && stage pip-audit st_audit
if want gitleaks normal; then
  if have gitleaks || { have docker && docker info >/dev/null 2>&1; }; then stage gitleaks st_gitleaks; else skip gitleaks "install gitleaks or start Docker"; fi
fi
want actions normal && stage actionlint+zizmor st_actions
if want frontend normal; then
  if [ ! -d frontend ]; then skip frontend "no frontend/ yet"
  elif [ -n "$(frontend_skip_reason)" ]; then skip frontend "$(frontend_skip_reason)"
  else stage frontend st_frontend; fi
fi
if want frontend-e2e normal; then
  if [ ! -d frontend ]; then skip frontend-e2e "no frontend/ yet"
  elif [ -n "$(frontend_skip_reason)" ]; then skip frontend-e2e "$(frontend_skip_reason)"
  elif [ -n "$(e2e_skip_reason)" ]; then skip frontend-e2e "$(e2e_skip_reason)"
  else stage frontend-e2e st_frontend_e2e; fi
fi
if want smoke full; then
  if have docker && docker info >/dev/null 2>&1; then stage docker-smoke st_smoke; else skip docker-smoke "Docker is not running"; fi
fi

echo; echo "================ local CI summary ($MODE) ================"
printf '%s\n' "${RESULTS[@]}"
if [ "$FAILED" -ne 0 ]; then echo "RESULT: FAILED. Fix the failing stages before pushing."; exit 1; fi
echo "RESULT: all executed stages passed."
