from pathlib import Path

import pytest
from rm_core.settings import Settings


def test_defaults_match_blueprint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    for name in ("FREE_SIGNUP_CREDITS", "AUDIT_JOB_TIMEOUT_S", "WORKER_AUDIT_CONCURRENCY"):
        monkeypatch.delenv(name, raising=False)
    s = Settings()
    assert s.free_signup_credits == 3
    assert s.audit_job_timeout_s == 900
    assert s.worker_audit_concurrency == 1
