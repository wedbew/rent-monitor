"""Seed a signed-in user for the browser journey lane (#269, FRONTEND-PLAN.md section 4).

    C="docker compose -f deploy/compose.yml exec -T api python scripts/e2e_session.py"
    $C create [--credits 5] [--admin]
    $C register-token --email e2e-<x>@example.test --password <p>
    $C delete <user_id>
    $C delete-email e2e-<x>@example.test
    $C plant-listing [--kind sale|rent]
    $C unplant --ref IDJ... --stem journey-check-...

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
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from journey_check import CITY, Planted, hand_built_ad
from journey_check import remove as remove_planted
from rm_api.auth.password import _issue_register_token
from rm_api.auth.passwords import PasswordHasher
from rm_api.auth.sessions import create_session
from rm_core.comparables import StoredComparable, city_slug, replace_comparables
from rm_core.db.models import AuthToken, MarketSidecar, SidecarKind, User
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.settings import get_settings
from rm_core.snapshots import FetchedListing, content_hash, store_snapshot
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


async def register_token(email: str, password: str) -> dict[str, str]:
    """The one-time token the sign-up e-mail would carry, stored exactly as registration stores it (one live
    token per address, SHA-256 at rest, Argon2id hash of the password). The raw token is returned here instead
    of being mailed, so a journey can open `/signup/verify#t=<token>` without a mailbox."""
    if not email.startswith("e2e-") or not email.endswith("@example.test"):
        msg = "refusing: only e2e-*@example.test addresses"
        raise SystemExit(msg)
    settings = get_settings()
    engine = make_engine(settings, pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        password_hash = await PasswordHasher(settings).hash(password)
        async with sm() as session, session.begin():
            token = await _issue_register_token(session, settings, email, password_hash)
        return {"email": email, "token": token}
    finally:
        await engine.dispose()


async def remove_email(email: str) -> bool:
    if not email.startswith("e2e-") or not email.endswith("@example.test"):
        return False
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        async with sm() as session, session.begin():
            await session.execute(delete(AuthToken).where(AuthToken.email == email))
            result = await session.execute(delete(User).where(User.email == email))
            return bool(getattr(result, "rowcount", 0))
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


async def plant_listing(kind: str) -> dict[str, str]:
    """A fresh, hand-built, anonymised listing snapshot (so the worker makes no Otodom request) and, for a
    sale, hand-built rental comparables for a made-up city, as `scripts/journey_check.py` plants them.
    EVIDENCE CLASS: fake provider data. `kind=rent` plants a rental ad: the audit must end
    `rejected / RENT_NOT_DEAL`."""
    run_id = uuid4().hex[:8]
    ref = "IDJ" + run_id.upper()
    stem = f"journey-check-{run_id}"
    ad: dict[str, Any] = hand_built_ad(ref)
    city = f"{CITY}{run_id}"  # one made-up city per listing: parallel journeys never share a sidecar grain
    ad["location"]["address"]["city"]["name"] = city
    if kind == "rent":
        ad["adCategory"] = {"type": "RENT"}
    rows = [StoredComparable(Decimal(price * 48), Decimal(48)) for price in (60, 61, 62, 63, 64, 65)]
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        async with sm() as session, session.begin():
            sidecar = MarketSidecar(
                kind=SidecarKind.otodom_rental,
                price_basis="rent",
                city_slug=city_slug(city),
                period=date(2026, 10, 1),
                size_bucket="30-50",
                source_stem=stem,
                sha256=uuid4().hex * 2,
                payload={},
                generated_at=datetime.now(UTC),
            )
            session.add(sidecar)
            await session.flush()
            await replace_comparables(session, sidecar.id, rows)
            await store_snapshot(
                session,
                FetchedListing(
                    otodom_id=ref,
                    url=f"https://www.otodom.pl/pl/oferta/{ref}",
                    ad=ad,
                    content_sha256=content_hash(ad),
                ),
            )
        return {"ref": ref, "stem": stem, "kind": kind}
    finally:
        await engine.dispose()


async def unplant_listing(ref: str, stem: str) -> bool:
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        planted = Planted(run_id="", ref=ref, stem=stem, ad={}, rows=[])
        return await remove_planted(sm, planted)
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
    token = sub.add_parser("register-token")
    token.add_argument("--email", required=True)
    token.add_argument("--password", required=True)
    drop_email = sub.add_parser("delete-email")
    drop_email.add_argument("email")
    plant = sub.add_parser("plant-listing")
    plant.add_argument("--kind", choices=["sale", "rent"], default="sale")
    unplant = sub.add_parser("unplant")
    unplant.add_argument("--ref", required=True)
    unplant.add_argument("--stem", required=True)
    args = parser.parse_args()
    if args.command == "plant-listing":
        print(json.dumps(asyncio.run(plant_listing(args.kind))))
        return 0
    if args.command == "unplant":
        print(json.dumps({"removed": asyncio.run(unplant_listing(args.ref, args.stem))}))
        return 0
    if args.command == "create":
        print(json.dumps(asyncio.run(create(args.credits, admin=args.admin))))
        return 0
    if args.command == "register-token":
        print(json.dumps(asyncio.run(register_token(args.email, args.password))))
        return 0
    if args.command == "delete-email":
        print(json.dumps({"deleted": asyncio.run(remove_email(args.email))}))
        return 0
    print(json.dumps({"deleted": asyncio.run(remove(args.user_id))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
