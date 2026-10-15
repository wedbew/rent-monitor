"""Seed a signed-in user for the browser journey lane (#269, FRONTEND-PLAN.md section 4).

    C="docker compose -f deploy/compose.yml exec -T api python scripts/e2e_session.py"
    $C create [--credits 5] [--admin]
    $C delete <user_id>

It runs *inside* the api container, with the deployed settings and database, and writes the user, a credit
account and a session row exactly as the sign-in routes would; the raw session token is printed once (JSON
on stdout) so the Playwright lane can put it in its browser cookie jar. There is no HTTP bypass and no
test-only route in the API: the browser then talks to the real, unmodified API with a real session cookie.

EVIDENCE CLASS: a throwaway synthetic account (`e2e-<random>@example.test`) on whatever stack runs it.
Never run it against a host that holds customer data; `delete` removes the user and everything that
cascades from it.

GDPR[personal-data]: the account is synthetic; the session token goes only to the caller (RM-269).
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

from rm_api.auth.sessions import create_session
from rm_core.db.models import User
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.settings import get_settings
from sqlalchemy import delete


async def create(credits: int, *, admin: bool) -> dict[str, object]:
    settings = get_settings()
    engine = make_engine(settings, pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        async with sm() as session, session.begin():
            email = f"e2e-{uuid4().hex[:10]}@example.test"
            user = User(
                email=email,
                email_verified_at=datetime.now(UTC),
                name="Użytkownik E2E",
                role="admin" if admin else "user",
            )
            session.add(user)
            await session.flush()
            await ensure_credit_account(session, user.id, verified=True, signup_credits=0)
            if credits:
                await admin_adjust(
                    session, user.id, credits, key=f"e2e:{user.id}", note="e2e journey credits"
                )
            token = await create_session(
                session, user.id, user_agent="playwright-e2e", ip=None, settings=settings
            )
            return {
                "user_id": user.id,
                "email": email,
                "credits": credits,
                "cookie_name": settings.cookie_name,
                "cookie_value": token,
                "public_origin": settings.public_origin,
            }
    finally:
        await engine.dispose()


async def remove(user_id: str) -> bool:
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        async with sm() as session, session.begin():
            result = await session.execute(
                delete(User).where(User.id == user_id, User.email.like("e2e-%@example.test"))
            )
            return bool(result.rowcount)  # type: ignore[attr-defined]  # cascades sessions, credits, audits
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("create")
    make.add_argument("--credits", type=int, default=5)
    make.add_argument("--admin", action="store_true")
    drop = sub.add_parser("delete")
    drop.add_argument("user_id")
    args = parser.parse_args()
    if args.command == "create":
        print(json.dumps(asyncio.run(create(args.credits, admin=args.admin))))
        return 0
    print(json.dumps({"deleted": asyncio.run(remove(args.user_id))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
