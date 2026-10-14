from pathlib import Path

import pytest
from check_env import check, main, parse_env

GOOD = {
    "APP_ENV": "production",
    "PUBLIC_APP_URL": "https://beta.example.test",
    "POSTGRES_PASSWORD": "x" * 32,
}


def test_parse_env_handles_comments_quotes_and_inline_comments() -> None:
    text = 'A=1  # note\n# C=3\nB="two words"\nEMPTY=\nbroken line\n'
    assert parse_env(text) == {"A": "1", "B": "two words", "EMPTY": ""}


def test_good_vps_env_has_no_problems() -> None:
    assert check(GOOD, "vps") == []


def test_local_target_never_blocks() -> None:
    assert check({}, "local") == []


@pytest.mark.parametrize(
    ("change", "name"),
    [
        ({"APP_ENV": "development"}, "APP_ENV"),
        ({"PUBLIC_APP_URL": "http://beta.example.test"}, "PUBLIC_APP_URL"),
        ({"POSTGRES_PASSWORD": "change-me"}, "POSTGRES_PASSWORD"),
        ({"POSTGRES_PASSWORD": "short"}, "POSTGRES_PASSWORD"),
        ({"DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/d"}, "DATABASE_URL"),
        ({"BILLING_PROVIDER": "paddle", "PADDLE_ENVIRONMENT": "sandbox"}, "PADDLE_ENVIRONMENT"),
        ({"AUDIT_PROVIDERS": "real", "LEGAL_SCRAPING_ENABLED": "false"}, "LEGAL_SCRAPING_ENABLED"),
    ],
)
def test_each_rule_blocks_and_names_the_variable(change: dict[str, str], name: str) -> None:
    problems = check({**GOOD, **change}, "vps")
    assert any(p.startswith(f"{name}:") for p in problems)


def test_missing_required_names_are_reported() -> None:
    assert len(check({}, "vps")) == 3


def test_output_never_contains_a_secret_value(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    secret = "s3cr3t-value-that-must-not-leak"
    env = tmp_path / "env"
    env.write_text(f"APP_ENV=development\nPOSTGRES_PASSWORD={secret}\nRESEND_API_KEY={secret}\n")
    assert main([str(env)]) == 1
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert "RESEND_API_KEY" in captured.out


def test_missing_file_fails(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope")]) == 1
