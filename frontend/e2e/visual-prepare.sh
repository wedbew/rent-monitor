#!/usr/bin/env bash
# Source this (". e2e/visual-prepare.sh") inside the pinned Playwright image, from frontend/: it puts the Node that
# `frontend/.node-version` names on PATH and installs the dependencies. `pnpm visual` and the `frontend-visual` CI job
# both use it, so the lane runs on the same Node as everything else instead of whatever the image happens to carry
# (the image's Node is older). Nothing here turns engine enforcement off: a wrong Node fails the check below.
#
# The Node tarball comes from nodejs.org and must match the SHA-256 committed in `e2e/node-linux-x64.sha256`
# (`test/visual-image.test.ts` keeps that file on the `.node-version` release). No npm package runs install scripts
# to fetch it. Strict shell options apply inside the subshell only, so sourcing does not change the caller's shell.
rm_visual_install_node() (
  set -euo pipefail
  want="$(tr -d '[:space:]' < .node-version)"
  [ "$(node -p 'process.versions.node' 2>/dev/null || true)" = "$want" ] && exit 0
  [ -x /opt/pinned-node/bin/node ] && [ "$(/opt/pinned-node/bin/node -p 'process.versions.node')" = "$want" ] && exit 0
  [ "$(uname -m)" = "x86_64" ] || { echo "visual lane: only linux x86_64 is pinned (e2e/node-linux-x64.sha256)" >&2; exit 1; }
  pinned="$(cat e2e/node-linux-x64.sha256)"
  tarball="node-v${want}-linux-x64.tar.gz"
  case "$pinned" in
    *"  ${tarball}") ;;
    *) echo "visual lane: e2e/node-linux-x64.sha256 does not name ${tarball}" >&2; exit 1 ;;
  esac
  work="$(mktemp -d)"
  curl -fsSL --retry 3 --max-time 300 -o "${work}/${tarball}" "https://nodejs.org/dist/v${want}/${tarball}"
  (cd "$work" && printf '%s\n' "$pinned" | sha256sum -c --strict -)
  mkdir -p /opt/pinned-node
  tar -xzf "${work}/${tarball}" -C /opt/pinned-node --strip-components=1
  rm -rf "$work"
)

rm_visual_install_deps() (
  set -euo pipefail
  want="$(tr -d '[:space:]' < .node-version)"
  have="$(node -p 'process.versions.node')"
  if [ "$have" != "$want" ]; then
    echo "visual lane: Node ${have} is active, frontend/.node-version wants ${want}" >&2
    exit 1
  fi
  corepack enable
  pnpm install --frozen-lockfile ${PNPM_STORE_DIR:+--config.store-dir="${PNPM_STORE_DIR}"}
)

if rm_visual_install_node; then
  export PATH="/opt/pinned-node/bin:${PATH}"
  rm_visual_install_deps
else
  false
fi
