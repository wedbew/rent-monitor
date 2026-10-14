"""Live audit check: one REAL Otodom listing through the deployed API, queue, worker, market data and engine.

Run it where the stack runs (inside the api container, deployed settings and database):
    docker compose -f deploy/compose.yml -f deploy/compose.prod.yml exec -T api \
        python scripts/live_audit_check.py --base-url http://localhost:8000 --listing <otodom url or id>

EVIDENCE CLASS: live (docs/STATUS.md level 3 for the parts it touches). It makes ONE real Otodom request for
the listing (the owner authorised single live fetches, L-005) and uses whatever market data the database
holds, so a city that was never imported shows a refused rent. It creates a throwaway user with one credit
and removes the user, audit, snapshot and listing row again. It prints one JSON object with statuses, codes,
the grade and the numbers the engine used; it never prints listing text, addresses, seller data or secrets.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from journey_check import Planted, drive, remove
from rm_api.auth.sessions import create_session
from rm_core.db.models import User
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.listing_ref import parse_listing_ref
from rm_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def plant_user(sm: async_sessionmaker[AsyncSession], p: Planted) -> None:
    async with sm() as s, s.begin():
        user = User(email=f"live-{p.run_id}@live-check.invalid", email_verified_at=datetime.now(UTC))
        s.add(user)
        await s.flush()
        p.user_id = user.id
        await ensure_credit_account(s, user.id, verified=True, signup_credits=0)
        await admin_adjust(s, user.id, 1, key=f"live:{p.run_id}", note="live check credit")
        p.cookie = await create_session(s, user.id, user_agent="live-check", ip=None, settings=get_settings())


def summarise(audit: dict[str, Any]) -> dict[str, Any]:
    result = audit.get("result") or {}
    rent = result.get("rent") or {}
    return {
        "status": audit["status"],
        "error_code": audit["error_code"],
        "charge_state": audit["charge_state"],
        "grade": audit["grade"],
        "warnings": result.get("warnings"),
        "rent_input_monthly_pln": rent.get("input_monthly_pln"),
        "rent_used_monthly_pln": rent.get("monthly_used_pln"),
        "rent_basis": rent.get("basis"),
        "rent_comparables": rent.get("comparables"),
        "rent_confidence": rent.get("confidence"),
        "vision": bool(result.get("vision")),
    }


async def run(base_url: str, listing: str) -> dict[str, Any]:
    ref = parse_listing_ref(listing)
    engine = make_engine(get_settings(), pool_size=2, max_overflow=0)
    sm = make_sessionmaker(engine)
    planted = Planted(uuid4().hex[:8], ref, f"live-audit-check-{uuid4().hex}", {}, [])
    evidence: dict[str, Any] = {"evidence_class": "live", "listing_id": ref}
    started = time.monotonic()
    try:
        await plant_user(sm, planted)
        audit = await drive(base_url, planted, evidence)
        evidence["audit"] = summarise(audit)
        evidence["elapsed_s"] = round(time.monotonic() - started, 2)
        return evidence
    finally:
        evidence["cleaned_up"] = await remove(sm, planted)
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--listing", required=True, help="Otodom listing URL or id (a SALE listing)")
    args = parser.parse_args()
    try:
        evidence = asyncio.run(run(args.base_url, args.listing))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
