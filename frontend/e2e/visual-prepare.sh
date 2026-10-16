#!/usr/bin/env bash
# Source this (". e2e/visual-prepare.sh") inside the pinned Playwright image, from frontend/: it puts the Node that
# `frontend/.node-version` names on PATH and installs the dependencies. `pnpm visual` and the `frontend-visual` CI job
# both use it, so the lane runs on the same Node as everything else instead of whatever the image happens to carry
# (the image's Node is older). Nothing here turns engine enforcement off: a wrong Node fails the check below.
set -euo pipefail

want="$(tr -d '[:space:]' < .node-version)"
if [ "$(node -p 'process.versions.node')" != "$want" ]; then
  npm install --no-fund --no-audit --no-save --prefix /opt/pinned-node "node@${want}"
  export PATH="/opt/pinned-node/node_modules/.bin:${PATH}"
fi
have="$(node -p 'process.versions.node')"
if [ "$have" != "$want" ]; then
  echo "visual lane: Node ${have} is active, frontend/.node-version wants ${want}" >&2
  return 1 2>/dev/null || exit 1
fi
corepack enable
pnpm install --frozen-lockfile ${PNPM_STORE_DIR:+--config.store-dir="${PNPM_STORE_DIR}"}
