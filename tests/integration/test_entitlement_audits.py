# ruff: noqa: F811  (the fixtures `h` and `clean_up` are imported and used as parameters)
"""`unlimited_reports`: analyses are not charged, usage stays on the audit, safeguards stay (RM-438).

Same harness as the journey test: real API, Postgres, ledger, a real worker and the engine; the listing
source and market context are the named offline fakes. A zero balance does not stop an entitled account;
it still stops an ordinary one.
"""

from typing import Any

import pytest
from rm_core.db.models import Audit, ChargeSource, ChargeState, CreditLedger
from rm_core.entitlement_grants import grant, revoke
from rm_core.ledger import admin_adjust
from sqlalchemy import func, select
from test_audit_journey import (  # noqa: F401  (fixtures)
    SIGNUP_CREDITS,
    Harness,
    MakeToken,
    clean_up,
    h,
    new_ref,
    sale_ad,
    submit,
)
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]


async def drained(h: Harness, make_google_token: MakeToken) -> tuple[Any, dict[str, Any]]:
    c, me = await sign_in(h.app, make_google_token)
    async with h.sm() as s, s.begin():
        await admin_adjust(s, me["id"], -SIGNUP_CREDITS, key=f"drain:{me['id']}", note="test")
    return c, me


async def test_an_entitled_account_with_no_credit_completes_analyses_without_spending_any(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await drained(h, make_google_token)
    async with h.sm() as s:
        await grant(s, me["email"], note="test")
    assert (await c.get("/api/me")).json()["plan"]["unlimited_reports"] is True
    for _ in range(SIGNUP_CREDITS + 2):  # more analyses than the balance could ever pay for
        ref = new_ref()
        h.source.ads[ref] = sale_ad()
        accepted = await submit(c, ref)
        assert accepted.status_code == 202, accepted.text
        assert accepted.json()["credits_remaining"] is None
        await h.run_worker()
        audit = await h.audit(accepted.json()["audit_id"])
        assert audit.status.value in {"succeeded", "succeeded_degraded"}
        assert (audit.charge_source, audit.charge_state) == (ChargeSource.admin_free, ChargeState.captured)
    async with h.sm() as s:
        by_audit = select(func.count()).select_from(CreditLedger).where(CreditLedger.audit_id.is_not(None))
        assert (
            await s.scalar(by_audit.where(CreditLedger.user_id == me["id"])) == 0
        )  # no hold, capture or release
        own = select(func.count()).select_from(Audit).where(Audit.user_id == me["id"])
        assert await s.scalar(own) == SIGNUP_CREDITS + 2  # the usage record is the audit rows
    assert await h.balance(me["id"]) == 0  # nothing was fabricated or spent
    await h.assert_ledger_consistent()


async def test_a_failed_analysis_of_an_entitled_account_settles_once_and_touches_no_credit(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await drained(h, make_google_token)
    async with h.sm() as s:
        await grant(s, me["email"], note="test")
    ref = new_ref()
    h.source.ads[ref] = sale_ad(adCategory={"type": "RENT"})  # invariant 1: a rental is not a deal
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker()
    audit = await h.audit(audit_id)
    assert (audit.status.value, audit.charge_state) == ("rejected", ChargeState.released)
    assert await h.balance(me["id"]) == 0


async def test_the_one_active_audit_per_listing_rule_still_holds_for_an_entitled_account(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await drained(h, make_google_token)
    async with h.sm() as s:
        await grant(s, me["email"], note="test")
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    assert (await submit(c, ref)).status_code == 202
    again = await submit(c, ref)
    assert again.status_code == 409
    assert again.json()["code"] == "AUDIT_IN_PROGRESS"


async def test_an_ordinary_account_at_zero_is_still_refused_and_revoking_restores_the_limit(
    h: Harness, make_google_token: MakeToken
) -> None:
    ordinary, _ = await drained(h, make_google_token)
    assert (await submit(ordinary, new_ref())).status_code == 402
    c, me = await drained(h, make_google_token)
    async with h.sm() as s:
        await grant(s, me["email"], note="test")
    assert (await submit(c, new_ref())).status_code == 202
    async with h.sm() as s:
        await revoke(s, me["email"])
    assert (await c.get("/api/me")).json()["plan"]["unlimited_reports"] is False
    assert (await submit(c, new_ref())).status_code == 402
