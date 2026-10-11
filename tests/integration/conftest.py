"""Real Postgres 17 via Testcontainers (never SQLite). One container per session, migrated with Alembic."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """SQLAlchemy URL of a disposable Postgres. `TEST_DATABASE_URL` overrides it (must be a throwaway DB)."""
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        yield override
        return
    with PostgresContainer("postgres:17", driver="psycopg") as pg:
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
