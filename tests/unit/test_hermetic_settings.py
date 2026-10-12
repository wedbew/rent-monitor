"""Tests never read the owner's real .env (it holds live keys that a failing assertion could print)."""

import httpx
from rm_core.settings import Settings
from rm_worker.clients.resend import ResendMailer


def test_settings_in_tests_do_not_load_the_env_file() -> None:
    assert Settings.model_config.get("env_file") is None


def test_a_mailer_never_shows_its_key_in_repr() -> None:
    mailer = ResendMailer(httpx.AsyncClient(), "re_super_secret_value", "x@example.test")
    assert "re_super_secret_value" not in repr(mailer)
