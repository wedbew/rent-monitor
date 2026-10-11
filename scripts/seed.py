"""Seed plans, feature flags and the admin role. Idempotent.

Usage: `uv run python scripts/seed.py [--admin-email me@x]`.
Reads DATABASE_URL, PRO_MONTHLY_AUDIT_ALLOWANCE, STRIPE_PRICE_ID_PRO and ADMIN_EMAIL from the environment.
"""

import argparse
import asyncio
import os

from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.seed import seed_all
from rm_core.settings import get_settings


async def main(admin_email: str | None) -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        async with make_sessionmaker(engine)() as session, session.begin():
            await seed_all(
                session,
                pro_allowance=settings.pro_monthly_audit_allowance,
                stripe_price_id_pro=os.environ.get("STRIPE_PRICE_ID_PRO") or None,
                admin_email=admin_email or os.environ.get("ADMIN_EMAIL") or None,
            )
    finally:
        await engine.dispose()
    print("seed: done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email", default=None)
    asyncio.run(main(parser.parse_args().admin_email))
