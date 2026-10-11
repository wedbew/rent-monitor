"""Engine factory: refuses to start without a URL, applies the pool budget and server-side timeouts."""

import pytest
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.settings import Settings
from sqlalchemy import text

pytestmark = [pytest.mark.integration]


def test_engine_requires_a_database_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        make_engine(Settings(database_url=""))


async def test_engine_applies_timeouts_and_pool_budget(migrated_url: str) -> None:
    engine = make_engine(Settings(database_url=migrated_url))
    try:
        assert engine.pool.size() == 5  # type: ignore[attr-defined]
        async with make_sessionmaker(engine)() as s:
            assert await s.scalar(text("SHOW statement_timeout")) == "30s"
            assert await s.scalar(text("SHOW idle_in_transaction_session_timeout")) == "1min"
    finally:
        await engine.dispose()
