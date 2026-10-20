"""Real Postgres 17 via Testcontainers (never SQLite). One container per session, migrated with Alembic once
into a template database; every test module gets its own copy (`CREATE DATABASE ... TEMPLATE`), so modules
cannot see each other's rows and the suite can run in parallel (pytest-xdist, one container per worker).

Shared by `tests/integration/conftest.py` and `tests/smoke/conftest.py`, which re-export the fixtures."""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from pg_container import postgres_container
from psycopg import sql
from sqlalchemy.engine import make_url
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


TEMPLATE_DB = "rm_template"


def _conninfo(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _migrate(url: str) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")


async def _apply_procrastinate_schema(url: str) -> None:
    """Apply Procrastinate's schema beside schema `app` unless it is already there (it is not idempotent)."""
    from procrastinate import PsycopgConnector  # noqa: PLC0415
    from procrastinate.schema import SchemaManager  # noqa: PLC0415

    connector = PsycopgConnector(conninfo=_conninfo(url))
    await connector.open_async()
    try:
        present = await connector.execute_query_one_async(
            "SELECT to_regclass('public.procrastinate_jobs') AS t"
        )
        if present["t"] is None:
            await SchemaManager(connector).apply_schema_async()
    finally:
        await connector.close_async()


def _url_for(pg_url: str, database: str) -> str:
    return make_url(pg_url).set(database=database).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def template_url(pg_url: str) -> str | None:
    """A migrated database with Procrastinate's schema, built once per session. None with `TEST_DATABASE_URL`
    (a throwaway database we may not be allowed to create siblings of): modules then share it, as before."""
    if os.environ.get("TEST_DATABASE_URL"):
        return None
    with psycopg.connect(_conninfo(pg_url), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEMPLATE_DB)))
    url = _url_for(pg_url, TEMPLATE_DB)
    _migrate(url)
    asyncio.run(_apply_procrastinate_schema(url))
    return url


@pytest.fixture(scope="module")
def migrated_url(pg_url: str, template_url: str | None) -> Iterator[str]:
    """A migrated database private to the test module."""
    if template_url is None:
        _migrate(pg_url)
        yield pg_url
        return
    name = f"rm_{uuid4().hex[:12]}"
    with psycopg.connect(_conninfo(pg_url), autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(TEMPLATE_DB)
            )
        )
    try:
        yield _url_for(pg_url, name)
    finally:
        with psycopg.connect(_conninfo(pg_url), autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


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


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def procrastinate_schema(migrated_url: str) -> None:
    """Procrastinate's schema in this module's database (copied from the template, so normally present)."""
    await _apply_procrastinate_schema(migrated_url)
