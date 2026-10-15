"""Real Postgres 17 via Testcontainers (never SQLite). One container per session, migrated with Alembic.

Shared by `tests/integration/conftest.py` and `tests/smoke/conftest.py`, which re-export the fixtures."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from pg_container import postgres_container
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """SQLAlchemy URL of a disposable Postgres. `TEST_DATABASE_URL` overrides it (must be a throwaway DB)."""
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        yield override
        return
    with postgres_container() as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def migrated_url(pg_url: str) -> str:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", pg_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    return pg_url


@pytest_asyncio.fixture(loop_scope="session")
async def engine(migrated_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(migrated_url, pool_size=10)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back, so tests do not leak rows into each other."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        sm = async_sessionmaker(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
        async with sm() as s:
            yield s
        await trans.rollback()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def procrastinate_schema(migrated_url: str) -> None:
    """Apply Procrastinate's own schema once per session (it is not idempotent), beside schema `app`."""
    from procrastinate import PsycopgConnector  # noqa: PLC0415
    from procrastinate.schema import SchemaManager  # noqa: PLC0415

    connector = PsycopgConnector(conninfo=migrated_url.replace("postgresql+psycopg://", "postgresql://"))
    await connector.open_async()
    try:
        await SchemaManager(connector).apply_schema_async()
    finally:
        await connector.close_async()
