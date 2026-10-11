"""pytest-alembic fixtures pointed at a disposable Postgres 17."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config() -> Config:
    return Config(
        config_options={"file": str(ROOT / "alembic.ini"), "script_location": str(ROOT / "migrations")}
    )


@pytest.fixture(scope="module")
def alembic_url() -> Iterator[str]:
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        yield override
        return
    with PostgresContainer("postgres:17", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture
def alembic_engine(alembic_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("DATABASE_URL", alembic_url)
    engine = create_engine(alembic_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS app CASCADE"))
    yield engine
    engine.dispose()
