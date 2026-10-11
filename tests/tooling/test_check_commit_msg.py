import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_commit_msg import check_range, is_valid  # noqa: E402


@pytest.mark.parametrize(
    "msg",
    [
        "feat(RM-12): add credit ledger reserve/settle",
        "fix(RM-31)!: reject unverified Google emails",
        "chore(RM-1): bootstrap tooling\n\nbody text",
        "Merge pull request #40 from me/rm-12-ledger",
        "# comment line\nci(RM-7): pin actions by sha",
        "build(deps): bump the python-minor-patch group with 4 updates",
        "chore(release): 1.4.0",
    ],
)
def test_valid(msg: str) -> None:
    assert is_valid(msg)


@pytest.mark.parametrize(
    "msg",
    [
        "feat: no ticket",
        "feat(#12): hash form not allowed",
        "feat(rm-12): lowercase key",
        "feat(RM-0): zero issue",
        "feature(RM-12): unknown type",
        "feat(RM-12):missing space",
        "feat(RM-12): " + "x" * 73,
        "",
        "feat(deps): bots may not ship features",
        "chore(release-notes): not the release scope",
    ],
)
def test_invalid(msg: str) -> None:
    assert not is_valid(msg)


def _commit(repo: Path, msg: str) -> None:
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", msg], cwd=repo, check=True)


def test_root_commit_exempt_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for k, v in {"user.name": "t", "user.email": "t@example.com"}.items():
        subprocess.run(["git", "config", k, v], cwd=tmp_path, check=True)
    _commit(tmp_path, "initial bootstrap")              # root: exempt
    _commit(tmp_path, "feat(RM-1): first ticket")       # valid
    _commit(tmp_path, "chore: bootstrap again")         # not root: rejected
    monkeypatch.chdir(tmp_path)
    bad = check_range("HEAD")
    assert len(bad) == 1 and "chore: bootstrap again" in bad[0]
