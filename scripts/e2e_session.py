"""Seed a signed-in user for the browser journey lane (#269, FRONTEND-PLAN.md section 4).

    C="docker compose -f deploy/compose.yml exec -T api python scripts/e2e_session.py"
    $C create [--credits 5] [--admin]
    $C register-token --email e2e-<x>@example.test --password <p>
    $C delete <user_id>
    $C delete-email e2e-<x>@example.test
    $C plant-listing [--kind sale|rent]
    $C unplant --ref IDJ... --stem journey-check-...
    $C plant-market [--run <tag>]        # four synthetic places (a run tag in every name), published through
    $C age-market --run <tag> --hours N  # production code; the checkpoint is backdated to move the freshness
    $C market-db --run <tag>             # clock; medians recomputed by SQL as an independent cross-check
    $C unplant-market --run <tag>

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
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from deal_analyzer.market_stats import summarise_asking
from journey_check import CITY, Planted, hand_built_ad
from journey_check import remove as remove_planted
from rm_api.auth.password import _issue_register_token
from rm_api.auth.passwords import PasswordHasher
from rm_api.auth.sessions import create_session
from rm_contracts.market import (
    ImportRun,
    LocationCatalogue,
    LocationEntry,
    OfferObservation,
    RunMode,
    RunState,
)
from rm_core.comparables import StoredComparable, city_slug, replace_comparables
from rm_core.db.models import AuthToken, MarketCatalogue, MarketLocation, MarketSidecar, SidecarKind, User
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.market_corpus import PgCorpus
from rm_core.market_history import PgMarketHistory
from rm_core.settings import get_settings
from rm_core.snapshots import FetchedListing, content_hash, store_snapshot
from sqlalchemy import delete, func, select, text


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


MARKET_SOURCE_REF = "e2e-journey"
# One place per state the page must show: sufficient, withheld (too few priced offers), bootstrap pending,
# and a fourth that is only a catalogue entry. Rents are hand-made, so every figure can be computed by hand:
#   alfa: 12 offers 2000..2550 step 50 at 50 m2 (PLN/m2 40..51), then 4 offers 3000..3150 two days ago.
#   Before the second batch the median rent is 2275.00 (45.50 PLN/m2); with all 16: 2375.00 (47.50 PLN/m2).
MARKET_PLACES = {"alfa": "Alfa", "beta": "Beta", "gamma": "Gamma", "delta": "Delta"}


def _market_ids(run: str) -> dict[str, str]:
    return {key: f"e2e-{run}-{key}" for key in MARKET_PLACES}


async def plant_market(run: str | None) -> dict[str, Any]:
    """Four synthetic places published through the production corpus and summary code. EVIDENCE CLASS: fake
    provider data; nothing is fetched from Otodom. Every name carries the run tag, so a search for the tag
    finds only this run's places whatever else the catalogue holds, and `unplant-market` removes only them."""
    tag = run or uuid4().hex[:6]
    settings = get_settings()
    version = settings.otodom_market_catalogue_version
    ids = _market_ids(tag)
    now = datetime.now(UTC)
    boot, mid, recent = now - timedelta(days=5), now - timedelta(days=2), now - timedelta(hours=2)
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        corpus = PgCorpus(sm)
        entries = [
            LocationEntry(location_id=ids[k], name=f"E2E{tag} {label}", otodom_path=f"cala-polska/{ids[k]}")
            for k, label in MARKET_PLACES.items()
        ]
        async with sm() as session, session.begin():
            exists = await session.get(MarketCatalogue, version)
            top = await session.scalar(
                select(func.max(MarketLocation.position)).where(MarketLocation.catalogue_version == version)
            )
            if exists is not None:
                for i, e in enumerate(entries, start=(top or -1) + 1):
                    session.add(
                        MarketLocation(
                            catalogue_version=version,
                            location_id=e.location_id,
                            position=i,
                            name=e.name,
                            otodom_path=e.otodom_path,
                        )
                    )
        if exists is None:
            await corpus.ensure_catalogue(LocationCatalogue.build(version, MARKET_SOURCE_REF, entries))
        base = int(tag, 16) * 1000 if all(c in "0123456789abcdef" for c in tag) else 7_000_000

        def offers(loc: str, first: int, rents: list[int], seen: datetime) -> list[OfferObservation]:
            return [
                OfferObservation(
                    source_offer_id=str(base + first + i),
                    location_id=loc,
                    asking_rent_pln=Decimal(r),
                    area_m2=Decimal(50),
                    rooms=2,
                    observed_at=seen,
                )
                for i, r in enumerate(rents)
            ]

        async def run_one(
            rid: str, loc: str, mode: RunMode, window: tuple[datetime, datetime], obs: list
        ) -> None:
            start, end = window
            await corpus.start_run(
                ImportRun(run_id=rid, location_id=loc, mode=mode, window_start=start, window_end=end)
            )
            await corpus.save_progress(rid, pages_fetched=1, pages_expected=1)
            if obs:
                await corpus.record_offers(rid, obs, end)
            await corpus.finish_run(rid, state=RunState.published, now=end)

        # A source id belongs to one place for good (a second place claiming it is a conflict), so ids differ.
        for spread, (key, first_rents) in enumerate(
            (("alfa", [2000 + 50 * i for i in range(12)]), ("beta", [2000, 2100, 2200]))
        ):
            loc = ids[key]
            await run_one(
                f"{loc}-b",
                loc,
                RunMode.bootstrap,
                (boot - timedelta(hours=24), boot),
                offers(loc, spread * 500, first_rents, boot),
            )
            second = [3000, 3050, 3100, 3150] if key == "alfa" else []
            await run_one(
                f"{loc}-1",
                loc,
                RunMode.incremental,
                (boot, mid),
                offers(loc, spread * 500 + 100, second, mid),
            )
            await run_one(f"{loc}-2", loc, RunMode.incremental, (mid, recent), [])
        history = PgMarketHistory(sm)
        for key in ("alfa", "beta"):
            for back in range(5, -1, -1):
                await history.publish_day(
                    ids[key], (now - timedelta(days=back)).date(), now=now, summarise=summarise_asking
                )
        return {
            "run": tag,
            "ids": ids,
            "names": {k: f"E2E{tag} {v}" for k, v in MARKET_PLACES.items()},
            "catalogue_version": version,
            "created_catalogue": exists is None,
        }
    finally:
        await engine.dispose()


async def age_market(run: str, hours: int, gap_days: int | None) -> dict[str, int]:
    """Backdate the run's checkpoints, so the API's real clock reads them as delayed (over 36 h) or stale
    (over 72 h, or with a gap). The summaries are untouched: only the checkpoint's freshness moves."""
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    update = text(
        "UPDATE app.market_import_checkpoint"
        " SET last_successful_refresh_at = now() - make_interval(hours => :h),"
        " unresolved_gap_since = CASE WHEN CAST(:g AS integer) IS NULL THEN NULL"
        " ELSE now() - make_interval(days => CAST(:g AS integer)) END"
        " WHERE location_id LIKE :p"
    )
    try:
        async with engine.begin() as conn:
            result = await conn.execute(update, {"h": hours, "g": gap_days, "p": f"e2e-{run}-%"})
            return {"updated": int(getattr(result, "rowcount", 0))}
    finally:
        await engine.dispose()


async def market_db(run: str) -> dict[str, Any]:
    """The figures of the run's places recomputed by SQL (`percentile_cont`) from the stored offers, for the
    journey to compare with what the API and the page say."""
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT location_id, count(*) AS n,"
                        " round((percentile_cont(0.5) WITHIN GROUP"
                        " (ORDER BY asking_rent_pln))::numeric, 2)::text AS median_rent,"
                        " round((percentile_cont(0.5) WITHIN GROUP"
                        " (ORDER BY asking_rent_pln / area_m2))::numeric, 2)::text AS median_ppm2"
                        " FROM app.market_offer WHERE location_id LIKE :p GROUP BY location_id"
                    ),
                    {"p": f"e2e-{run}-%"},
                )
            ).all()
            return {
                r.location_id: {"offers": r.n, "median_rent": r.median_rent, "median_ppm2": r.median_ppm2}
                for r in rows
            }
    finally:
        await engine.dispose()


_DELETES = (
    ("market_daily_summary", text("DELETE FROM app.market_daily_summary WHERE location_id LIKE :p")),
    ("market_district", text("DELETE FROM app.market_district WHERE location_id LIKE :p")),
    ("market_offer", text("DELETE FROM app.market_offer WHERE location_id LIKE :p")),
    ("market_import_run", text("DELETE FROM app.market_import_run WHERE location_id LIKE :p")),
    ("market_import_checkpoint", text("DELETE FROM app.market_import_checkpoint WHERE location_id LIKE :p")),
    ("market_location", text("DELETE FROM app.market_location WHERE location_id LIKE :p")),
)


async def unplant_market(run: str) -> dict[str, int]:
    """Remove only this run's places and what hangs on them; the catalogue header goes too if this tool
    made it and nothing else is left in it. Never touches another run's or any real place."""
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    removed: dict[str, int] = {}
    header = text(
        "DELETE FROM app.market_catalogue c WHERE c.source_ref = :s AND NOT EXISTS"
        " (SELECT 1 FROM app.market_location l WHERE l.catalogue_version = c.version)"
    )
    try:
        async with engine.begin() as conn:
            for name, statement in _DELETES:
                result = await conn.execute(statement, {"p": f"e2e-{run}-%"})
                removed[name] = int(getattr(result, "rowcount", 0))
            result = await conn.execute(header, {"s": MARKET_SOURCE_REF})
            removed["market_catalogue"] = int(getattr(result, "rowcount", 0))
        return removed
    finally:
        await engine.dispose()


def main() -> int:  # noqa: PLR0911  (one early return per sub-command)
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
    pm = sub.add_parser("plant-market")
    pm.add_argument("--run")
    am = sub.add_parser("age-market")
    am.add_argument("--run", required=True)
    am.add_argument("--hours", type=int, required=True)
    am.add_argument("--gap-days", type=int)
    md = sub.add_parser("market-db")
    md.add_argument("--run", required=True)
    um = sub.add_parser("unplant-market")
    um.add_argument("--run", required=True)
    args = parser.parse_args()
    if args.command == "plant-market":
        print(json.dumps(asyncio.run(plant_market(args.run))))
        return 0
    if args.command == "age-market":
        print(json.dumps(asyncio.run(age_market(args.run, args.hours, args.gap_days))))
        return 0
    if args.command == "market-db":
        print(json.dumps(asyncio.run(market_db(args.run))))
        return 0
    if args.command == "unplant-market":
        print(json.dumps(asyncio.run(unplant_market(args.run))))
        return 0
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
