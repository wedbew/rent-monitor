"""Vision is wired only with a key and the images switch on; otherwise audits end degraded (#211)."""

import pytest
from pydantic import SecretStr
from rm_core.settings import Settings
from rm_worker.audit_wiring import build_vision
from rm_worker.vision_stage import OpenRouterVision
from sqlalchemy.ext.asyncio import async_sessionmaker

DSN = "postgresql+psycopg://u:p@localhost/none"


def settings(**kw: object) -> Settings:
    return Settings.model_validate({"app_env": "test", "database_url": DSN} | kw)


@pytest.mark.parametrize(
    "kw",
    [
        {},  # no key
        {"openrouter_api_key": SecretStr("")},
        {"openrouter_api_key": SecretStr("sk-or-test"), "legal_images_enabled": False},  # counsel's switch
    ],
    ids=["no_key", "empty_key", "switch_off"],
)
def test_no_key_or_switch_off_builds_no_vision(kw: dict[str, object]) -> None:
    assert build_vision(settings(**kw), async_sessionmaker()) is None


def test_key_and_switch_on_builds_the_openrouter_stage() -> None:
    built = build_vision(settings(openrouter_api_key=SecretStr("sk-or-test")), async_sessionmaker())
    assert isinstance(built, OpenRouterVision)


def test_the_images_switch_and_model_have_documented_defaults() -> None:
    s = settings()
    assert s.legal_images_enabled is True
    assert s.openrouter_vision_model == "google/gemini-2.5-flash-lite"
