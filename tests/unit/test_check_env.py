"""`scripts/check_env.py` reports by name only and catches the mistakes that matter on a server (#15)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_env

SECRET = "s3cr3t-value-that-must-never-be-printed-9f2c"
GOOD = {
    "APP_ENV": "production",
    "PUBLIC_APP_URL": "https://app.example.pl",
    "DATABASE_URL": f"postgresql+psycopg://rm:{SECRET}@postgres:5432/rm",
    "POSTGRES_PASSWORD": SECRET,
    "RESEND_API_KEY": "re_" + SECRET,
    "MAIL_FROM": "RentMonitor <noreply@example.pl>",
    "GOOGLE_CLIENT_ID": "abc.apps.googleusercontent.com",
    "SENTRY_DSN": "https://k@o.ingest.example/1",
    "AUDIT_PROVIDERS": "real",
    "RISK_FREE_RATE": "0.055",
}


def names(findings: list[check_env.Finding], level: str = "ERROR") -> set[str]:
    return {f.name for f in findings if f.level == level}


def test_a_complete_production_environment_has_no_errors() -> None:
    assert names(check_env.check(GOOD)) == set()


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"APP_ENV": "development"}, "APP_ENV"),
        ({"PUBLIC_APP_URL": "http://app.example.pl"}, "PUBLIC_APP_URL"),
        ({"POSTGRES_PASSWORD": "dev-only-change-me"}, "POSTGRES_PASSWORD"),
        ({"POSTGRES_PASSWORD": "short"}, "POSTGRES_PASSWORD"),
        ({"DATABASE_URL": "postgresql+psycopg://rm:dev-only-change-me@postgres/rm"}, "DATABASE_URL"),
        ({"RESEND_API_KEY": ""}, "RESEND_API_KEY"),
        ({"MAIL_FROM": "RentMonitor <onboarding@resend.dev>"}, "MAIL_FROM"),
        ({"RISK_FREE_RATE": ""}, "RISK_FREE_RATE"),
        ({"GOOGLE_CLIENT_ID": "changeme"}, "GOOGLE_CLIENT_ID"),
        ({"BILLING_PROVIDER": "paddle"}, "BILLING_PROVIDER"),
    ],
)
def test_the_mistakes_that_matter_are_errors(change: dict[str, str], expected: str) -> None:
    env = {**GOOD, **change}
    env = {k: v for k, v in env.items() if v != "" or k != "RISK_FREE_RATE"}
    assert expected in names(check_env.check(env))


def test_a_private_beta_may_use_http_on_localhost_only() -> None:
    local = {**GOOD, "PUBLIC_APP_URL": "http://localhost:8000"}
    assert "PUBLIC_APP_URL" in names(check_env.check(local))
    assert "PUBLIC_APP_URL" not in names(check_env.check(local, private=True))
    assert "PUBLIC_APP_URL" in names(
        check_env.check({**GOOD, "PUBLIC_APP_URL": "http://evil.example"}, private=True)
    )


def test_invalid_values_are_reported_by_name_and_type_never_by_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = {**GOOD, "AUDIT_JOB_TIMEOUT_S": "not-a-number", "RISK_FREE_RATE": "7"}
    findings = check_env.check(env)
    assert {"AUDIT_JOB_TIMEOUT_S"} <= names(findings)
    assert "not-a-number" not in repr(findings)


def test_no_secret_value_is_ever_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = {**GOOD, "MAIL_FROM": "RentMonitor <onboarding@resend.dev>", "APP_ENV": "development"}
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in broken.items()) + "\n# comment\n")
    code = check_env.main(["--env-file", str(env_file)])
    out = capsys.readouterr().out
    assert code == 1
    assert SECRET not in out
    assert "MAIL_FROM" in out
    assert "APP_ENV" in out


def test_the_env_file_parser_ignores_comments_and_quotes(tmp_path: Path) -> None:
    f = tmp_path / "e"
    f.write_text("# a\nA=1  # trailing\nB='two'\n\nC=\"three\"\nbroken line\n")
    assert check_env.parse_env_file(f) == {"A": "1", "B": "two", "C": "three"}
