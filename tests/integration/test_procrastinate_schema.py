"""Procrastinate's tables are applied by its own schema manager, outside Alembic and outside schema `app`."""

import pytest
from procrastinate import PsycopgConnector
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration]


async def test_procrastinate_schema_applies_beside_app_schema(engine: AsyncEngine, migrated_url: str) -> None:
    dsn = migrated_url.replace("postgresql+psycopg://", "postgresql://")
    connector = PsycopgConnector(conninfo=dsn)
    await connector.open_async()
    try:
        from procrastinate.schema import SchemaManager  # noqa: PLC0415

        await SchemaManager(connector).apply_schema_async()
    finally:
        await connector.close_async()

    async with engine.connect() as conn:
        found = await conn.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'procrastinate_jobs'"
            )
        )
        app_tables = await conn.scalar(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'app'")
        )
    assert found == 1
    assert app_tables is not None
    assert app_tables >= 15
