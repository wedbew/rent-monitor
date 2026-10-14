# ruff: noqa: F811  (the `rig` fixture is imported from test_paddle_webhook and used as a parameter)
"""Support-initiated refunds of unused packs and buyer invoice access (PADDLE-INTEGRATION.md §6-§7, #229).

Real: API, Postgres, ledger and lots. Faked, by name: Paddle. A refund request is not a refund: units move
only when a verified approved adjustment arrives. Offline evidence only (no sandbox call, L-020).
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from rm_core.db.models import BillingAdjustment, BillingPurchase, ReportCreditLot
from rm_core.paddle import PaddleError
from rm_core.privacy import delete_account
from sqlalchemy import select
from test_me_saved_admin import make_admin, sign_in
from test_pack_lots import assert_consistent, finish, submit
from test_pack_reversals import bought, lot_of, report
from test_paddle_webhook import Rig, rig  # noqa: F401  (fixture: `rig`)

pytestmark = [pytest.mark.integration, pytest.mark.money]
REASON = {"reason": "buyer asked within 14 days, pack unused"}


async def refund(admin: Any, purchase_id: str, body: dict[str, str] | None = None) -> Any:
    return await admin.post(f"/api/admin/billing/purchases/{purchase_id}/refund", json=body or REASON)


async def adjustments_of(rig: Rig, purchase_id: str) -> list[BillingAdjustment]:
    async with rig.sm() as s:
        return list(
            (
                await s.scalars(
                    select(BillingAdjustment).where(BillingAdjustment.purchase_id == UUID(purchase_id))
                )
            ).all()
        )


async def admin_for(rig: Rig, engine: Any, make_google_token: Any) -> Any:
    admin, _ = await make_admin(rig.app, engine, make_google_token)
    return admin


async def test_pack_refund_intent_durable(rig: Rig, make_google_token: Any, engine: Any) -> None:
    """The lot is frozen and the intent committed *before* Paddle is called; units move only on approval."""
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    admin = await admin_for(rig, engine, make_google_token)

    seen: dict[str, Any] = {}
    real = rig.paddle.create_full_refund

    async def spy(*, transaction_id: str, reason: str) -> Any:
        rows = await adjustments_of(rig, out["purchase_id"])
        seen["intents"] = [(r.status, r.adjustment_id.startswith("intent-")) for r in rows]
        seen["frozen"] = (await lot_of(rig, out["purchase_id"])).frozen
        return await real(transaction_id=transaction_id, reason=reason)

    rig.paddle.create_full_refund = spy
    r = await refund(admin, out["purchase_id"])
    assert (r.status_code, r.json()["status"]) == (202, "requested")
    assert seen == {
        "intents": [("intent", True)],
        "frozen": True,
    }  # durable and frozen before the network call

    (row,) = await adjustments_of(rig, out["purchase_id"])
    assert (row.status, row.action, row.adjustment_id.startswith("adj_")) == (
        "pending_approval",
        "refund",
        True,
    )
    assert await rig.balance(me["id"]) == 5  # a request is not a refund: nothing taken back yet
    assert (await rig.purchase(out["purchase_id"])).state == "granted"

    refunded = rig.paddle.adjustments[row.adjustment_id].model_copy(update={"status": "approved"})
    await report(rig, out["transaction_id"], refunded)  # Paddle approves it
    assert await rig.balance(me["id"]) == 0
    assert (await rig.purchase(out["purchase_id"])).state == "refunded"
    await assert_consistent(rig.sm, me["id"])


async def test_repeated_and_parallel_requests_create_one_refund(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    admin = await admin_for(rig, engine, make_google_token)
    replies = await asyncio.gather(*(refund(admin, out["purchase_id"]) for _ in range(4)))
    assert {r.status_code for r in replies} <= {200, 202}
    again = await refund(admin, out["purchase_id"])
    assert (again.status_code, again.json()["status"]) == (200, "exists")
    assert rig.paddle.calls.count("create_full_refund") == 1
    assert len(await adjustments_of(rig, out["purchase_id"])) == 1


@pytest.mark.parametrize("how", ["consumed", "reserved"])
async def test_a_used_or_running_pack_goes_to_manual_review_without_calling_paddle(
    rig: Rig, make_google_token: Any, engine: Any, how: str
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    audit = await submit(rig.sm, me["id"])
    assert audit is not None
    if how == "consumed":
        assert await finish(rig.sm, audit, capture=True)
    admin = await admin_for(rig, engine, make_google_token)
    r = await refund(admin, out["purchase_id"])
    assert (r.status_code, r.json()["code"]) == (409, "REFUND_NEEDS_REVIEW")
    assert "create_full_refund" not in rig.paddle.calls
    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.error_code) == ("review", "USED_PACK")
    assert (await lot_of(rig, out["purchase_id"])).frozen is False  # nothing was frozen on the way to review


async def test_an_ambiguous_request_is_reconciled_before_any_second_creation(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    admin = await admin_for(rig, engine, make_google_token)

    rig.paddle.fail_refund_after_store = True  # the refund exists at Paddle but the reply was lost
    first = await refund(admin, out["purchase_id"])
    assert (first.status_code, first.json()["status"]) == (202, "unknown")
    assert (await adjustments_of(rig, out["purchase_id"]))[0].status == "unknown"
    assert (await lot_of(rig, out["purchase_id"])).frozen is True  # stays frozen while we do not know

    rig.paddle.fail_refund_after_store = False
    second = await refund(admin, out["purchase_id"])  # lists first, adopts what exists, creates nothing
    assert (second.status_code, second.json()["status"]) == (202, "requested")
    assert rig.paddle.calls.count("create_full_refund") == 1
    assert len(rig.paddle.adjustments) == 1
    rows = await adjustments_of(rig, out["purchase_id"])
    assert [r.adjustment_id.startswith("adj_") for r in rows] == [True]
    assert await rig.balance(me["id"]) == 5


async def test_an_ambiguous_request_that_never_reached_paddle_may_be_created_after_listing(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    admin = await admin_for(rig, engine, make_google_token)
    rig.paddle.fail_refund_before_store = True
    assert (await refund(admin, out["purchase_id"])).json()["status"] == "unknown"
    rig.paddle.fail_refund_before_store = False
    again = await refund(admin, out["purchase_id"])
    assert (again.status_code, again.json()["status"]) == (202, "requested")
    assert len(rig.paddle.adjustments) == 1  # listing found none, so exactly one was created


async def test_a_rejected_refund_makes_the_pack_spendable_again(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    admin = await admin_for(rig, engine, make_google_token)
    adj_id = (await refund(admin, out["purchase_id"])).json()["adjustment_id"]
    assert (await lot_of(rig, out["purchase_id"])).frozen is True
    rejected = rig.paddle.adjustments[adj_id].model_copy(update={"status": "rejected"})
    await report(rig, out["transaction_id"], rejected)
    assert (await lot_of(rig, out["purchase_id"])).frozen is False
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    assert await submit(rig.sm, me["id"]) is not None  # the units can be spent


async def test_a_refusal_by_paddle_unfreezes_and_reports_a_clean_error(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    admin = await admin_for(rig, engine, make_google_token)

    async def refuse(*, transaction_id: str, reason: str) -> Any:
        raise PaddleError("422")

    rig.paddle.create_full_refund = refuse
    r = await refund(admin, out["purchase_id"])
    assert (r.status_code, r.json()["code"]) == (502, "BILLING_PROVIDER_ERROR")
    assert (await lot_of(rig, out["purchase_id"])).frozen is False
    assert (await adjustments_of(rig, out["purchase_id"]))[0].status == "failed"


async def test_only_admins_can_refund_and_only_a_granted_purchase(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    assert (await refund(c, out["purchase_id"])).status_code == 403  # a buyer cannot refund themselves
    admin = await admin_for(rig, engine, make_google_token)
    pending = await rig.buy(c, "reports_1")  # created, never paid
    r = await refund(admin, pending["purchase_id"])
    assert (r.status_code, r.json()["code"]) == (409, "PURCHASE_NOT_REFUNDABLE")
    assert (await refund(admin, str(uuid4()))).status_code == 409
    bad = await refund(admin, out["purchase_id"], {"reason": "x"})
    assert bad.status_code == 422


# ------------------------------------------------------------------------------ invoices
async def test_the_buyer_gets_a_short_lived_invoice_link_for_a_paid_purchase_only(
    rig: Rig, make_google_token: Any
) -> None:
    a, _ = await sign_in(rig.app, make_google_token)
    b, _ = await sign_in(rig.app, make_google_token)
    paid = await bought(rig, a)
    r = await a.get(f"/api/billing/purchases/{paid['purchase_id']}/invoice")
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://invoices.test/")
    assert r.headers["cache-control"] == "no-store"
    assert (
        await b.get(f"/api/billing/purchases/{paid['purchase_id']}/invoice")
    ).status_code == 404  # never 403
    assert (await b.get(f"/api/billing/purchases/{uuid4()}/invoice")).status_code == 404
    unpaid = await rig.buy(a, "reports_1")
    assert (await a.get(f"/api/billing/purchases/{unpaid['purchase_id']}/invoice")).status_code == 409
    assert (await rig.purchase(paid["purchase_id"])).provider_txn_id in rig.paddle.transactions

    codes = [
        (await a.get(f"/api/billing/purchases/{paid['purchase_id']}/invoice")).status_code for _ in range(10)
    ]
    assert codes.count(429) >= 1  # throttled


async def test_an_invoice_outage_is_a_clean_502(rig: Rig, make_google_token: Any) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)

    async def down(transaction_id: str) -> str:
        raise PaddleError("503")

    rig.paddle.get_invoice_url = down
    r = await c.get(f"/api/billing/purchases/{out['purchase_id']}/invoice")
    assert (r.status_code, r.json()["code"]) == (502, "BILLING_PROVIDER_ERROR")


async def test_erasing_an_account_keeps_the_purchase_and_its_adjustments(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    admin = await admin_for(rig, engine, make_google_token)
    await refund(admin, out["purchase_id"])
    async with rig.sm() as s, s.begin():
        assert (await delete_account(s, me["id"])).deleted
    p = await rig.purchase(out["purchase_id"])
    assert (p.user_id, p.owner_ref is not None, p.grant_ledger_id) == (None, True, None)
    assert len(await adjustments_of(rig, out["purchase_id"])) == 1
    async with rig.sm() as s:
        assert await s.scalar(select(ReportCreditLot.id).where(ReportCreditLot.user_id == me["id"])) is None
        assert await s.get(BillingPurchase, UUID(out["purchase_id"])) is not None
