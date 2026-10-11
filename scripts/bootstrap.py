"""Idempotent database bootstrap: Alembic migrations, Procrastinate schema (once), seed data (blueprint §4.4).

Safe to run on every start. Reads DATABASE_URL, PROCRASTINATE_DSN, ADMIN_EMAIL and STRIPE_PRICE_ID_PRO
from the environment.
"""

import asyncio
import os

import psycopg
from alembic import command
from alembic.config import Config
from procrastinate import PsycopgConnector
from procrastinate.schema import SchemaManager
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.seed import seed_all
from rm_core.settings import get_settings


def migrate() -> None:
    command.upgrade(Config("alembic.ini"), "head")


def procrastinate_schema_present(dsn: str) -> bool:
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        row = conn.execute("SELECT to_regclass('public.procrastinate_jobs') IS NOT NULL").fetchone()
    return bool(row and row[0])


async def apply_procrastinate_schema(dsn: str) -> bool:
    if procrastinate_schema_present(dsn):
        return False
    connector = PsycopgConnector(conninfo=dsn)
    await connector.open_async()
    try:
        await SchemaManager(connector).apply_schema_async()
    finally:
        await connector.close_async()
    return True


async def seed() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        async with make_sessionmaker(engine)() as session, session.begin():
            await seed_all(
                session,
                pro_allowance=settings.pro_monthly_audit_allowance,
                stripe_price_id_pro=os.environ.get("STRIPE_PRICE_ID_PRO") or None,
                admin_email=os.environ.get("ADMIN_EMAIL") or None,
            )
    finally:
        await engine.dispose()


async def main() -> None:
    settings = get_settings()
    migrate()
    applied = await apply_procrastinate_schema(settings.procrastinate_dsn)
    print(
        f"bootstrap: migrations at head, procrastinate schema {'applied' if applied else 'already present'}"
    )
    await seed()
    print("bootstrap: seed done")


if __name__ == "__main__":
    asyncio.run(main())
