"""Bounded synthetic load check for release gates 4 and 5 (blueprint section 6; issues #35, #36).

Run it where the stack runs, inside the api container, with the deployed settings and database:

    docker compose -f deploy/compose.yml [-f deploy/compose.prod.yml] exec -T api \\
        python scripts/load_check.py --audits 5 --base-url http://localhost:8000

`scripts/load_check.sh` wraps it and also records the worker's cgroup `memory.peak` around the run.

EVIDENCE CLASS: fake provider data, synthetic load. It plants N hand-built, anonymised listing snapshots
(fresh, so the worker makes no Otodom request; they carry no photos, so no OpenRouter call) with one
throwaway user and one credit each, submits the N audits at the same moment through the real HTTP API, polls
them to a terminal state and samples `pg_stat_activity` every second. It reports statuses, per-audit time,
API poll latency and the connection peak. It says nothing about Otodom, OpenRouter, accuracy, real traffic
or the batch workers (they are not running a real import here), and it is not a capacity claim beyond the
numbers it prints. Everything it creates is removed again, also after a failure; `--cleanup-stale` removes
leftovers of a killed run.

Bounds (a run that exceeds one stops and reports): at most `MAX_AUDITS` audits, a total deadline, and an
abort when the sampled connection count reaches `--stop-connections` (default 70, the gate's ceiling of the
100 `max_connections`).

GDPR[personal-data]: the accounts are synthetic (`load-<id>@load-check.invalid`); nothing personal is read
or logged."""

import argparse
import asyncio
import contextlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from rm_api.auth.sessions import create_session
from rm_core.comparables import StoredComparable, city_slug, replace_comparables
from rm_core.db.models import Audit, Listing, ListingSnapshot, MarketSidecar, SidecarKind, User
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.settings import get_settings
from rm_core.snapshots import FetchedListing, content_hash, store_snapshot
from sqlalchemy import delete, select, text, update

MAX_AUDITS = 25
DEFAULT_STOP_CONNECTIONS = 70
DEADLINE_S = 900.0
POLL_EVERY_S = 1.0
TERMINAL = {"succeeded", "succeeded_degraded", "failed", "rejected", "cancelled"}
EMAIL_DOMAIN = "load-check.invalid"
# IDLC + the 6-hex run id + a 2-digit index = 12 characters, the longest reference the API accepts
REF_PREFIX = "IDLC"
RUN_ID_LEN = 6


def percentile(values: list[float], fraction: float) -> float | None:
    """The nearest-rank percentile (`fraction` in 0..1); `None` for no samples."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return round(ordered[rank - 1], 3)


@dataclass
class Run:
    audits: int
    stop_connections: int
    connection_samples: list[int] = field(default_factory=list)
    poll_latencies_s: list[float] = field(default_factory=list)
    finished_s: dict[str, float] = field(default_factory=dict)
    statuses: dict[str, str] = field(default_factory=dict)
    aborted: str | None = None


def summarise(run: Run) -> dict[str, Any]:
    """The report and its verdict: every audit terminal and successful, connections under the ceiling."""
    peak = max(run.connection_samples, default=0)
    counts: dict[str, int] = {}
    for status in run.statuses.values():
        counts[status] = counts.get(status, 0) + 1
    done = sorted(run.finished_s.values())
    ok = (
        run.aborted is None
        and len(run.statuses) == run.audits
        and all(s in {"succeeded", "succeeded_degraded"} for s in run.statuses.values())
        and peak < run.stop_connections
    )
    return {
        "evidence_class": "fake-provider-data, synthetic load",
        "audits": run.audits,
        "statuses": counts,
        "aborted": run.aborted,
        "pg_connections_peak": peak,
        "pg_connections_ceiling": run.stop_connections,
        "pg_connection_samples": len(run.connection_samples),
        "time_to_finish_s": {
            "first": done[0] if done else None,
            "median": percentile(done, 0.5),
            "last": done[-1] if done else None,
        },
        "poll_latency_s": {
            "p50": percentile(run.poll_latencies_s, 0.5),
            "p95": percentile(run.poll_latencies_s, 0.95),
            "max": max(run.poll_latencies_s, default=None),
        },
        "ok": ok,
    }


def hand_built_ad(city: str) -> dict[str, Any]:
    """An anonymised SALE ad: no seller data, no photos, a made-up city."""
    return {
        "id": 90000002,
        "title": f"Mieszkanie 2 pokoje, {city}",
        "description": "Testowe ogloszenie do sprawdzenia obciazenia. Cisza, spokoj, blisko komunikacji.",
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
            "address": {"city": {"name": city}, "street": {"name": "Przykladowa", "number": "1"}},
        },
    }


async def _plant(run_id: str, count: int) -> list[dict[str, str]]:

    settings = get_settings()
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    sm = make_sessionmaker(engine)
    city = f"Loadcheck{run_id[:6]}"
    ad = hand_built_ad(city)
    rows = [StoredComparable(Decimal(price * 48), Decimal(48)) for price in (60, 61, 62, 63, 64, 65)]
    planted: list[dict[str, str]] = []
    try:
        async with sm() as s, s.begin():
            sidecar = MarketSidecar(
                kind=SidecarKind.otodom_rental,
                price_basis="rent",
                city_slug=city_slug(city),
                period=date(2026, 10, 1),
                size_bucket="30-50",
                source_stem=f"load-check-{run_id}",
                sha256=uuid4().hex * 2,
                payload={},
                generated_at=datetime.now(UTC),
            )
            s.add(sidecar)
            await s.flush()
            await replace_comparables(s, sidecar.id, rows)
            for n in range(count):
                ref = f"{REF_PREFIX}{run_id.upper()}{n:02d}"
                user = User(email=f"load-{run_id}-{n}@{EMAIL_DOMAIN}", email_verified_at=datetime.now(UTC))
                s.add(user)
                await s.flush()
                await ensure_credit_account(s, user.id, verified=True, signup_credits=0)
                await admin_adjust(s, user.id, 1, key=f"load:{run_id}:{n}", note="load check credit")
                cookie = await create_session(s, user.id, user_agent="load-check", ip=None, settings=settings)
                fetched = FetchedListing(
                    otodom_id=ref,
                    url=f"https://www.otodom.pl/pl/oferta/{ref}",
                    ad=ad,
                    content_sha256=content_hash(ad),
                )
                await store_snapshot(s, fetched)
                planted.append({"ref": ref, "user_id": user.id, "cookie": cookie})
    finally:
        await engine.dispose()
    return planted


def planted_refs(run_id: str) -> list[str]:
    """Every listing reference a run can have planted: exact names, never a prefix pattern."""
    return [f"{REF_PREFIX}{run_id.upper()}{n:02d}" for n in range(MAX_AUDITS)]


async def _remove(run_id: str | None) -> int:
    """Delete everything a run planted; with `None`, the leftovers of every run that still has a trace.

    Rows are found through the synthetic accounts (`load-<run>-<n>@load-check.invalid`) and sidecars
    (`load-check-<run>`) and deleted by exact reference, so a real listing whose id merely starts alike is
    never touched. Returns the users removed."""
    engine = make_engine(get_settings(), pool_size=2, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        async with sm() as s, s.begin():
            emails = list(
                (await s.scalars(select(User.email).where(User.email.like(f"load-%@{EMAIL_DOMAIN}")))).all()
            )
            stems = list(
                (
                    await s.scalars(
                        select(MarketSidecar.source_stem).where(
                            MarketSidecar.source_stem.like("load-check-%")
                        )
                    )
                ).all()
            )
            found = {m.group(1) for e in emails if (m := re.match(r"load-([0-9a-f]{6})-\d+@", e))}
            found |= {m.group(1) for t in stems if (m := re.fullmatch(r"load-check-([0-9a-f]{6})", t))}
            run_ids = [run_id] if run_id else sorted(found)
            refs = [ref for rid in run_ids for ref in planted_refs(rid)]
            mails = [e for e in emails if any(e.startswith(f"load-{rid}-") for rid in run_ids)]
            users = (
                list((await s.scalars(select(User.id).where(User.email.in_(mails)))).all()) if mails else []
            )
            await s.execute(update(Audit).where(Audit.otodom_id.in_(refs)).values(snapshot_id=None))
            if users:
                await s.execute(
                    delete(User).where(User.id.in_(users))
                )  # cascades audits, events, credit, session
            await s.execute(delete(Audit).where(Audit.otodom_id.in_(refs)))
            await s.execute(delete(ListingSnapshot).where(ListingSnapshot.otodom_id.in_(refs)))
            await s.execute(delete(Listing).where(Listing.otodom_id.in_(refs)))
            await s.execute(
                delete(MarketSidecar).where(
                    MarketSidecar.source_stem.in_([f"load-check-{rid}" for rid in run_ids])
                )
            )
        return len(users)
    finally:
        await engine.dispose()


async def _sample_connections(run: Run, stop: asyncio.Event) -> None:

    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    try:
        while not stop.is_set():
            async with engine.connect() as conn:
                count = int(
                    (
                        await conn.execute(
                            text("SELECT count(*) FROM pg_stat_activity WHERE datname IS NOT NULL")
                        )
                    ).scalar_one()
                )
            run.connection_samples.append(count)
            if count >= run.stop_connections and run.aborted is None:
                run.aborted = f"pg connections reached {count} (ceiling {run.stop_connections})"
                stop.set()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=1.0)
    finally:
        await engine.dispose()


async def _drive_one(
    base_url: str, item: dict[str, str], run: Run, started: float, stop: asyncio.Event
) -> None:

    settings = get_settings()
    headers = {"Origin": settings.public_origin, "Cookie": f"{settings.cookie_name}={item['cookie']}"}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=httpx.Timeout(30.0)) as http:
        submitted = await http.post("/api/audits", json={"listing_ref": item["ref"]})
        if submitted.status_code != 202:
            run.statuses[item["ref"]] = f"submit_{submitted.status_code}"
            return
        audit_id = submitted.json()["audit_id"]
        while not stop.is_set() and time.monotonic() - started < DEADLINE_S:
            t0 = time.monotonic()
            body = (await http.get(f"/api/audits/{audit_id}")).json()
            run.poll_latencies_s.append(time.monotonic() - t0)
            if body["status"] in TERMINAL:
                run.statuses[item["ref"]] = body["status"]
                run.finished_s[item["ref"]] = round(time.monotonic() - started, 2)
                return
            await asyncio.sleep(POLL_EVERY_S)
        if run.aborted is None:
            run.aborted = "deadline"


async def run_check(base_url: str, audits: int, stop_connections: int) -> dict[str, Any]:
    run_id = uuid4().hex[:RUN_ID_LEN]
    run = Run(audits=audits, stop_connections=stop_connections)
    stop = asyncio.Event()
    started = time.monotonic()
    try:
        planted = await _plant(run_id, audits)
        sampler = asyncio.create_task(_sample_connections(run, stop))
        await asyncio.gather(*(_drive_one(base_url, item, run, started, stop) for item in planted))
        stop.set()
        await sampler
    finally:
        removed = await _remove(run_id)
    report = summarise(run)
    report["run_id"] = run_id
    report["elapsed_s"] = round(time.monotonic() - started, 2)
    report["cleaned_up_users"] = removed
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--audits", type=int, default=5)
    parser.add_argument("--stop-connections", type=int, default=DEFAULT_STOP_CONNECTIONS)
    parser.add_argument(
        "--cleanup-stale", action="store_true", help="remove leftovers of a killed run and exit"
    )
    args = parser.parse_args()
    if args.cleanup_stale:
        print(json.dumps({"removed_users": asyncio.run(_remove(None))}))
        return 0
    if not 1 <= args.audits <= MAX_AUDITS:
        print(json.dumps({"ok": False, "error": f"--audits must be 1..{MAX_AUDITS}"}))
        return 2
    try:
        report = asyncio.run(run_check(args.base_url, args.audits, args.stop_connections))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
