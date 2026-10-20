"""Real Postgres 17 via Testcontainers: fixtures from `tests/db_fixtures.py` (also used by tests/smoke)."""

from db_fixtures import engine, migrated_url, pg_url, procrastinate_schema, session, template_url

__all__ = ["engine", "migrated_url", "pg_url", "procrastinate_schema", "session", "template_url"]
