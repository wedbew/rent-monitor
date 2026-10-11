"""Procrastinate's tables are applied by its own schema manager, outside Alembic and outside schema `app`."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration]


@pytest.mark.usefixtures("procrastinate_schema")
async def test_procrastinate_schema_applies_beside_app_schema(engine: AsyncEngine) -> None:
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
