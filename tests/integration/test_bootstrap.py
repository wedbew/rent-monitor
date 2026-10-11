"""`scripts/bootstrap.py` is safe to run on every start: the Procrastinate schema is applied once."""

import pytest
from bootstrap import apply_procrastinate_schema, procrastinate_schema_present
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

pytestmark = [pytest.mark.integration]


async def test_procrastinate_schema_is_applied_once_then_skipped(pg_url: str) -> None:
    url = make_url(pg_url)
    fresh = "rm_bootstrap_test"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{fresh}"'))
        conn.execute(text(f'CREATE DATABASE "{fresh}"'))
    dsn = url.set(database=fresh, drivername="postgresql").render_as_string(hide_password=False)
    try:
        assert procrastinate_schema_present(dsn) is False
        assert await apply_procrastinate_schema(dsn) is True
        assert procrastinate_schema_present(dsn) is True
        assert await apply_procrastinate_schema(dsn) is False  # second start: nothing to do, no error
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{fresh}" WITH (FORCE)'))
        admin.dispose()
