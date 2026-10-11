"""`procrastinate --app=rm_worker.app.app schema --apply` is a production bootstrap step (blueprint §4.4)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

pytestmark = [pytest.mark.integration]


def test_procrastinate_cli_applies_schema_to_a_fresh_database(pg_url: str) -> None:
    url = make_url(pg_url)
    fresh = "rm_cli_schema_test"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{fresh}"'))
        conn.execute(text(f'CREATE DATABASE "{fresh}"'))
    dsn = url.set(database=fresh, drivername="postgresql").render_as_string(hide_password=False)
    try:
        exe = Path(sys.executable).parent / "procrastinate"
        env = {**os.environ, "PROCRASTINATE_DSN": dsn}
        result = subprocess.run(  # noqa: S603  (fixed argv, test-only)
            [str(exe), "--app=rm_worker.app.app", "schema", "--apply"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        check = create_engine(url.set(database=fresh))
        with check.connect() as conn:
            found = conn.scalar(text("SELECT to_regclass('public.procrastinate_jobs') IS NOT NULL"))
        check.dispose()
        assert found is True
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{fresh}" WITH (FORCE)'))
        admin.dispose()
