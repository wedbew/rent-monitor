"""Deployed journey check: API -> real queue -> worker -> Postgres -> engine child -> persisted result.

Run it where the stack runs, inside the api container so it uses the deployed settings and database:
    docker compose -f deploy/compose.yml [-f deploy/compose.prod.yml] exec -T api \
        python scripts/journey_check.py --base-url http://localhost:8000

EVIDENCE CLASS: fake provider data. It plants a hand-built, anonymised listing snapshot (fresh, so the
worker makes no Otodom request) and hand-built rental comparables for a throwaway city, creates a throwaway
user with one credit and a session, then drives the real HTTP API, the real Procrastinate worker, Postgres and
the killable engine child, and compares the stored result with the engine run in this process. It is NOT
evidence about Otodom, market data or any vendor (docs/STATUS.md level 3). It needs `RISK_FREE_RATE` and
`AUDIT_PROVIDERS=real` in the deployed environment, or the audit correctly ends CONTEXT_UNAVAILABLE or fails
closed. Everything it creates is removed again. It prints one JSON object (no secrets); exit 1 on any failure.
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from deal_analyzer import analyse_listing, extract_listing
from deal_analyzer.rent import RentComparable, estimate_rent
from rm_api.auth.sessions import create_session
from rm_core.comparables import StoredComparable, city_slug, replace_comparables
from rm_core.db.models import Audit, Listing, ListingSnapshot, MarketSidecar, SidecarKind, User
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.settings import get_settings
from rm_core.snapshots import FetchedListing, content_hash, store_snapshot
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

CITY = "Journeycheck"
POLL_TIMEOUT_S = 180.0


def hand_built_ad(otodom_id: str) -> dict[str, Any]:
    """An anonymised SALE ad: no seller data, a made-up city."""
    return {
        "id": 90000001,
        "title": "Mieszkanie 2 pokoje, Journeycheck",
        "description": "Testowe ogloszenie do sprawdzenia przeplywu. Cisza, spokoj, blisko komunikacji.",
        "createdAt": "2026-09-01T10:00:00Z",
        "modifiedAt": "2026-10-01T08:30:00Z",
        "adCategory": {"type": "SELL"},
        "characteristics": [
            {"key": "price", "value": "450000"},
            {"key": "m", "value": "48.5"},
            {"key": "rooms_num", "value": "2"},
            {"key": "rent", "value": "600"},
            {"key": "floor_no", "value": "2"},
            {"key": "building_floors_num", "value": "5"},
            {"key": "build_year", "value": "1998"},
        ],
        "location": {
            "coordinates": {"latitude": 52.2297, "longitude": 21.0122},
            "address": {"city": {"name": CITY}, "street": {"name": "Przykladowa", "number": "1"}},
        },
    }


@dataclass
class Planted:
    run_id: str
    ref: str
    stem: str
    ad: dict[str, Any]
    rows: list[StoredComparable]
    cookie: str = ""
    user_id: str | None = None


async def plant(sm: async_sessionmaker[AsyncSession], p: Planted) -> None:
    settings = get_settings()
    async with sm() as s, s.begin():
        user = User(email=f"journey-{p.run_id}@journey-check.invalid", email_verified_at=datetime.now(UTC))
        s.add(user)
        await s.flush()
        p.user_id = user.id
        await ensure_credit_account(s, user.id, verified=True, signup_credits=0)
        await admin_adjust(s, user.id, 1, key=f"journey:{p.run_id}", note="journey check credit")
        p.cookie = await create_session(s, user.id, user_agent="journey-check", ip=None, settings=settings)
        sidecar = MarketSidecar(
            kind=SidecarKind.otodom_rental,
            price_basis="rent",
            city_slug=city_slug(CITY),
            period=date(2026, 10, 1),
            size_bucket="30-50",
            source_stem=p.stem,
            sha256=uuid4().hex * 2,
            payload={},
            generated_at=datetime.now(UTC),
        )
        s.add(sidecar)
        await s.flush()
        await replace_comparables(s, sidecar.id, p.rows)
        fetched = FetchedListing(
            otodom_id=p.ref,
            url=f"https://www.otodom.pl/pl/oferta/{p.ref}",
            ad=p.ad,
            content_sha256=content_hash(p.ad),
        )
        await store_snapshot(s, fetched)


def _field(frame: str, name: str) -> str:
    return next(line[len(name) + 2 :] for line in frame.split("\n") if line.startswith(f"{name}: "))


async def drive(base_url: str, p: Planted, evidence: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    headers = {"Origin": settings.public_origin, "Cookie": f"{settings.cookie_name}={p.cookie}"}
    timeout = httpx.Timeout(POLL_TIMEOUT_S)
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout) as http:
        submitted = await http.post("/api/audits", json={"listing_ref": p.ref})
        if submitted.status_code != 202:
            msg = f"POST /api/audits -> {submitted.status_code}"
            raise RuntimeError(msg)
        audit_id = submitted.json()["audit_id"]
        stream = await http.get(f"/api/audits/{audit_id}/events")
        frames = [f for f in stream.text.split("\n\n") if f.strip() and not f.startswith(":")]
        kinds = [_field(f, "event") for f in frames]
        evidence["events"] = kinds
        evidence["stages"] = [json.loads(_field(f, "data")).get("stage") for f in frames]
        if not kinds or kinds[-1] not in {"done", "error"}:
            msg = f"event stream did not end in done or error: {kinds}"
            raise RuntimeError(msg)
        return (await http.get(f"/api/audits/{audit_id}")).json()


def check_result(p: Planted, audit: dict[str, Any], evidence: dict[str, Any]) -> None:
    evidence.update({"status": audit["status"], "error_code": audit["error_code"], "grade": audit["grade"]})
    if audit["status"] not in {"succeeded", "succeeded_degraded"} or audit["charge_state"] != "captured":
        msg = f"audit ended {audit['status']} / {audit['error_code']} / {audit['charge_state']}"
        raise RuntimeError(msg)
    comparables = [RentComparable(monthly_rent_pln=r.monthly_rent_pln, area_m2=r.area_m2) for r in p.rows]
    estimate = estimate_rent(Decimal("48.5"), comparables)
    risk_free = get_settings().risk_free_rate or Decimal(0)
    expected = analyse_listing(extract_listing(p.ad), rent=estimate.to_input(), risk_free=risk_free)
    evidence["result_matches_engine"] = audit["result"] == expected.model_dump(mode="json")
    if not evidence["result_matches_engine"]:
        msg = "stored result differs from the engine run in this process"
        raise RuntimeError(msg)


async def remove(sm: async_sessionmaker[AsyncSession], p: Planted) -> bool:
    async with sm() as s, s.begin():
        await s.execute(update(Audit).where(Audit.otodom_id == p.ref).values(snapshot_id=None))
        if p.user_id is not None:
            await s.execute(
                delete(User).where(User.id == p.user_id)
            )  # cascades audits, events, credit, session
        await s.execute(delete(Audit).where(Audit.otodom_id == p.ref))
        await s.execute(delete(ListingSnapshot).where(ListingSnapshot.otodom_id == p.ref))
        await s.execute(delete(Listing).where(Listing.otodom_id == p.ref))
        await s.execute(delete(MarketSidecar).where(MarketSidecar.source_stem == p.stem))
    async with sm() as s:
        return await s.scalar(select(Audit.id).where(Audit.otodom_id == p.ref)) is None


async def run(base_url: str) -> dict[str, Any]:
    engine = make_engine(get_settings(), pool_size=2, max_overflow=0)
    sm = make_sessionmaker(engine)
    run_id = uuid4().hex[:8]
    ref = "IDJ" + run_id.upper()
    rows = [StoredComparable(Decimal(price * 48), Decimal(48)) for price in (60, 61, 62, 63, 64, 65)]
    planted = Planted(run_id, ref, f"journey-check-{run_id}", hand_built_ad(ref), rows)
    evidence: dict[str, Any] = {"run_id": run_id, "evidence_class": "fake-provider-data"}
    started = time.monotonic()
    try:
        await plant(sm, planted)
        audit = await drive(base_url, planted, evidence)
        check_result(planted, audit, evidence)
        evidence["elapsed_s"] = round(time.monotonic() - started, 2)
        evidence["ok"] = True
        return evidence
    finally:
        evidence["cleaned_up"] = await remove(sm, planted)
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        evidence = asyncio.run(run(args.base_url))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
