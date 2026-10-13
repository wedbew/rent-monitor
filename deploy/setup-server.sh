#!/usr/bin/env bash
# First-boot host hardening for the OVH VPS (blueprint §4.4 "Production", step 1). Idempotent: safe to re-run.
#
# Run ON the server as a sudo-capable user (the OVH default `ubuntu`):
#   scp deploy/setup-server.sh ubuntu@<ip>:/tmp/ && ssh -t ubuntu@<ip> \
#     'DEPLOY_SSH_PUBKEY="ssh-ed25519 AAAA... you@laptop" sudo -E bash /tmp/setup-server.sh'
#
# What it does: apt upgrade, `deploy` user (docker group, key login), 2 GB swap + vm.swappiness=10, UFW (22/80/443 only),
# fail2ban, unattended security upgrades, Docker Engine + Compose plugin, SSH hardening.
# What it does NOT do: clone the repo, create `.env`, start the stack, touch DNS or OVH resources.
#
# Safety: SSH password login is disabled ONLY when DEPLOY_SSH_PUBKEY was given (so you cannot lock yourself out).
# Keep your current session open and test a second login as `deploy` before closing it.
# No secrets are read, printed or written by this script.

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
SWAP_GB="${SWAP_GB:-2}"
SSH_PORT="${SSH_PORT:-22}"
APP_DIR="${APP_DIR:-/opt/rent-monitor}"
DEPLOY_SSH_PUBKEY="${DEPLOY_SSH_PUBKEY:-}"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root (sudo -E bash $0)"
[[ -r /etc/os-release ]] || die "cannot detect the OS"
# shellcheck disable=SC1091
. /etc/os-release
[[ "${ID}" == "ubuntu" ]] || die "written for Ubuntu, found ${ID}"
if [[ -n "${DEPLOY_SSH_PUBKEY}" && ! "${DEPLOY_SSH_PUBKEY}" =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+)\ [A-Za-z0-9+/=]+ ]]; then
  die "DEPLOY_SSH_PUBKEY is not a public key line"
fi
export DEBIAN_FRONTEND=noninteractive

log "Packages and security updates"
apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg ufw fail2ban unattended-upgrades git make jq htop

log "Unattended security upgrades"
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

log "Deploy user '${DEPLOY_USER}'"
if ! id "${DEPLOY_USER}" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "${DEPLOY_USER}"
fi
install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
if [[ -n "${DEPLOY_SSH_PUBKEY}" ]]; then
  auth="/home/${DEPLOY_USER}/.ssh/authorized_keys"
  touch "${auth}"
  grep -qxF "${DEPLOY_SSH_PUBKEY}" "${auth}" || printf '%s\n' "${DEPLOY_SSH_PUBKEY}" >>"${auth}"
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "${auth}"
  chmod 600 "${auth}"
fi
install -d -m 750 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${APP_DIR}"

log "Swap (${SWAP_GB} GB) and vm.swappiness=10"
if ! swapon --show=NAME --noheadings | grep -q .; then
  fallocate -l "${SWAP_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi
echo 'vm.swappiness=10' >/etc/sysctl.d/99-rentmonitor.conf
sysctl -q --system

log "Docker Engine and Compose plugin (official apt repository)"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch="$(dpkg --print-architecture)"
  codename="${UBUNTU_CODENAME:-${VERSION_CODENAME}}"
  if ! curl -fsSI "https://download.docker.com/linux/ubuntu/dists/${codename}/Release" >/dev/null; then
    die "Docker publishes no apt repo for Ubuntu '${codename}' yet; install Docker manually and re-run"
  fi
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "${DEPLOY_USER}"
install -d -m 755 /etc/docker
cat >/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "live-restore": true
}
EOF
systemctl enable --now docker
systemctl restart docker

log "Firewall: allow ${SSH_PORT}/80/443 only"
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp"
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

log "fail2ban for sshd"
cat >/etc/fail2ban/jail.d/sshd.local <<EOF
[sshd]
enabled = true
port = ${SSH_PORT}
maxretry = 5
bantime = 1h
findtime = 10m
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

log "SSH hardening"
if [[ -n "${DEPLOY_SSH_PUBKEY}" ]]; then
  cat >/etc/ssh/sshd_config.d/99-rentmonitor.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
EOF
  sshd -t
  systemctl reload ssh
  echo "Password login is now DISABLED. Test: ssh ${DEPLOY_USER}@<ip> from a second terminal before closing this one."
else
  echo "DEPLOY_SSH_PUBKEY not given: SSH password login left ON. Re-run with the key to disable it (PRE-DEPLOYMENT §0)."
fi

log "Done"
docker --version
docker compose version
ufw status verbose | head -12
free -m | sed -n '1,3p'
cat <<EOF

Next (manual, see deploy/README.md "Production"):
  1. ssh ${DEPLOY_USER}@<ip>; git clone the repo into ${APP_DIR}; create .env from .env.example with production values.
  2. Do not start the stack publicly until Caddy/TLS, memory limits and backups exist (RM-15).
EOF
