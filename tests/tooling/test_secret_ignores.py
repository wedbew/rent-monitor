"""Secrets and credential files must stay out of git (the repository is public)."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.production",
        "deploy/client_secret_123-abc.apps.googleusercontent.com.json",
        "client_secret.json",
        "services/x/client_secret_9.json",
        "deploy/some.apps.googleusercontent.com.json",
        "service-account-prod.json",
        "ovh.conf",
        ".ovh.conf",
        "docs/STRIPE-INTEGRATION.md",
        "docs/GOOGLE-AUTH-INTEGRATION.md",
        "docs/RESEND-INTEGRATION.md",
        "docs/BETTERSTACK-INTEGRATION.md",
        "docs/UMAMI-INTEGRATION.md",
        "docs/INFRASTRUCTURE.md",
        "deploy/ssh.key",
    ],
)
def test_credential_files_are_gitignored(path: str) -> None:
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, check=False)  # noqa: S603, S607
    assert result.returncode == 0, f"{path} is not ignored"


def test_example_files_stay_trackable() -> None:
    result = subprocess.run(["git", "check-ignore", "-q", ".env.example"], cwd=ROOT, check=False)  # noqa: S603, S607
    assert result.returncode == 1


def test_agents_cannot_read_oauth_secrets_or_use_stripe_live() -> None:
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    deny = settings["permissions"]["deny"]
    assert "Read(./**/client_secret*.json)" in deny
    assert "Bash(stripe*--live*)" in deny
    assert "Bash(ovh*)" in settings["permissions"]["ask"]
    assert "Read(./.env)" in deny
