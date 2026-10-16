"""The load check's database side on real Postgres: it plants synthetic rows and removes exactly those."""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from rm_core.settings import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration]

SPEC = importlib.util.spec_from_file_location(
    "load_check", Path(__file__).resolve().parents[2] / "scripts" / "load_check.py"
)
assert SPEC is not None
assert SPEC.loader is not None
load_check: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_check)


async def count(engine: AsyncEngine, sql: str, **params: object) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text(sql), params)).scalar_one())


@pytest.fixture(autouse=True)
def database(migrated_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", migrated_url)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_plant_creates_n_accounts_with_credit_and_a_fresh_snapshot_each_and_remove_deletes_only_them(
    engine: AsyncEngine,
) -> None:
    bystander = await count(engine, "SELECT count(*) FROM app.app_user")
    planted = await load_check._plant("abcd1234", 3)
    assert [p["ref"] for p in planted] == ["IDLABCD123400", "IDLABCD123401", "IDLABCD123402"]
    assert all(p["cookie"] for p in planted)
    assert (
        await count(engine, "SELECT count(*) FROM app.app_user WHERE email LIKE '%@load-check.invalid'") == 3
    )
    assert await count(engine, "SELECT count(*) FROM app.listing WHERE otodom_id LIKE 'IDLABCD1234%'") == 3
    assert (
        await count(engine, "SELECT count(*) FROM app.listing_snapshot WHERE otodom_id LIKE 'IDLABCD1234%'")
        == 3
    )

    removed = await load_check._remove("abcd1234")
    assert removed == 3
    assert await count(engine, "SELECT count(*) FROM app.app_user") == bystander
    assert await count(engine, "SELECT count(*) FROM app.listing WHERE otodom_id LIKE 'IDL%'") == 0
    assert (
        await count(engine, "SELECT count(*) FROM app.market_sidecar WHERE source_stem LIKE 'load-check-%'")
        == 0
    )


async def test_cleanup_stale_removes_leftovers_of_every_run_and_nothing_else(engine: AsyncEngine) -> None:
    await load_check._plant("11112222", 1)
    await load_check._plant("33334444", 2)
    async with engine.begin() as conn:  # an unrelated user and listing that merely look similar must stay
        await conn.execute(
            text("INSERT INTO app.app_user (id, email) VALUES ('keep-me', 'load-keep@example.test')")
        )
    try:
        assert await load_check._remove(None) == 3
        assert await count(engine, "SELECT count(*) FROM app.app_user WHERE id = 'keep-me'") == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.app_user WHERE id = 'keep-me'"))
