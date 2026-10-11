"""Alembic environment: everything lives in schema `app`; the version table too (blueprint §3)."""

import os

from alembic import context
from rm_core.db import models  # noqa: F401  (registers every table on Base.metadata)
from rm_core.db.base import SCHEMA, Base
from rm_core.settings import get_settings
from sqlalchemy import create_engine, pool
from sqlalchemy.schema import CreateSchema

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = (
        config.get_main_option("sqlalchemy.url")
        or os.environ.get("DATABASE_URL")
        or get_settings().database_url
    )
    if not url:
        msg = "DATABASE_URL is not set"
        raise RuntimeError(msg)
    return url


def _include_object(obj, name, type_, reflected, compare_to):
    # Procrastinate's tables live in `public` and are applied by `procrastinate schema --apply`.
    return not (type_ == "table" and getattr(obj, "schema", None) != SCHEMA)


# Every migration runs with bounded waits: a blocked DDL fails fast instead of queueing behind traffic.
GUARDS = ("SET lock_timeout = '5s'", "SET statement_timeout = '5min'")


def run_migrations_offline() -> None:
    context.configure(
        url="postgresql+psycopg://",  # offline SQL generation needs the dialect only, never a connection
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_object=_include_object,
        version_table_schema=SCHEMA,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        for guard in GUARDS:
            context.execute(guard)
        context.execute(CreateSchema(SCHEMA, if_not_exists=True))
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(CreateSchema(SCHEMA, if_not_exists=True))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=_include_object,
            version_table_schema=SCHEMA,
            compare_type=True,
        )
        with context.begin_transaction():
            for guard in GUARDS:
                context.execute(guard)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
