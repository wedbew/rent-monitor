# ruff: noqa: F811  (the `rig` fixture is imported from test_paddle_webhook and used as a parameter)
"""Provider refunds and chargebacks applied to granted packs (PADDLE-INTEGRATION.md §6, slice 5a).

Real: API, Postgres, ledger and lots, the billing worker logic. Faked, by name: Paddle. Units already
spent are never clawed back as a debt: they become an account billing hold for staff. Offline evidence only.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from rm_core.billing_events import reconcile_purchases
from rm_core.db.models import CreditAccount, CreditLedger, ReportCreditLot
from rm_core.entitlements import load_entitlements
from rm_core.ledger import BillingHoldError, admin_adjust, ledger_mismatches, lot_mismatches, reserve
from rm_core.paddle import Adjustment
from rm_core.privacy import delete_account
from sqlalchemy import func, select, text
from test_me_saved_admin import make_admin, sign_in
from test_pack_lots import assert_consistent, finish, submit
from test_paddle_webhook import SECRET, Rig, rig  # noqa: F401  (fixture: `rig`)

pytestmark = [pytest.mark.integration, pytest.mark.money]


def adjustment(txn_id: str, action: str, status: str, total: int, ident: str | None = None) -> Adjustment:
    return Adjustment(
        id=ident or f"adj_{uuid4().hex[:10]}",
        transaction_id=txn_id,
        action=action,
        type="full",
        status=status,
        currency_code="PLN",
        total_minor=total,
    )


async def bought(rig: Rig, c: Any, pack: str = "reports_5") -> dict[str, Any]:
    out = await rig.buy(c, pack)
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    return out


async def report(rig: Rig, txn_id: str, *adjustments: Adjustment) -> None:
    for a in adjustments:
        rig.paddle.adjustments[a.id] = a
    await rig.deliver(txn_id, "adjustment.updated")
    await rig.sweep()


async def lot_of(rig: Rig, purchase_id: str) -> ReportCreditLot:
    async with rig.sm() as s:
        return await s.scalar(select(ReportCreditLot).where(ReportCreditLot.purchase_id == UUID(purchase_id)))  # type: ignore[return-value]


async def hold_of(rig: Rig, user_id: str) -> str | None:
    async with rig.sm() as s:
        return await s.scalar(select(CreditAccount.billing_hold).where(CreditAccount.user_id == user_id))


# ------------------------------------------------------------------------------ provenance
async def test_pack_refund_provenance(rig: Rig, make_google_token: Any) -> None:
    """A refund takes back that pack only, not a signup or admin grant or another pack; repeats are no-ops."""
    c, me = await sign_in(rig.app, make_google_token)
    async with rig.sm() as s, s.begin():
        await admin_adjust(s, me["id"], 3, key=f"bonus-{me['id']}", note="a gift")
    a = await bought(rig, c, "reports_5")
    b = await bought(rig, c, "reports_10")
    assert await rig.balance(me["id"]) == 18

    refund = adjustment(a["transaction_id"], "refund", "approved", 4000)
    await report(rig, a["transaction_id"], refund)
    await report(rig, a["transaction_id"], refund)  # the same adjustment redelivered
    await report(
        rig, a["transaction_id"], refund, adjustment(a["transaction_id"], "refund", "approved", 4000)
    )

    assert await rig.balance(me["id"]) == 13  # only the 5 of pack A went
    assert (await rig.purchase(a["purchase_id"])).state == "refunded"
    assert (await rig.purchase(b["purchase_id"])).state == "granted"
    lot_a = await lot_of(rig, a["purchase_id"])
    assert (lot_a.available, lot_a.revoked, lot_a.frozen, lot_a.reversed_at is not None) == (0, 5, True, True)
    lot_b = await lot_of(rig, b["purchase_id"])
    assert (lot_b.available, lot_b.revoked, lot_b.frozen) == (10, 0, False)
    async with rig.sm() as s:
        revokes = (
            await s.scalars(
                select(CreditLedger.delta).where(
                    CreditLedger.user_id == me["id"], CreditLedger.reason == "refund_revoke"
                )
            )
        ).all()
        assert list(revokes) == [-5]  # one append-only entry, never negative balance, nothing deleted
        gift = await s.scalar(
            select(ReportCreditLot).where(ReportCreditLot.grant_key == f"admin:bonus-{me['id']}")
        )
        assert gift is not None
        assert (gift.available, gift.revoked) == (3, 0)
    await assert_consistent(rig.sm, me["id"])


async def test_pack_refund_in_flight(rig: Rig, make_google_token: Any) -> None:
    """Units held by running audits are revoked as each settles: released and revoked together."""
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    first, second = await submit(rig.sm, me["id"]), await submit(rig.sm, me["id"])
    assert first is not None
    assert second is not None
    lot = await lot_of(rig, out["purchase_id"])
    assert (lot.available, lot.reserved) == (3, 2)

    await report(rig, out["transaction_id"], adjustment(out["transaction_id"], "refund", "approved", 4000))
    lot = await lot_of(rig, out["purchase_id"])
    assert (lot.available, lot.reserved, lot.revoked) == (0, 2, 3)  # the free units went, the held ones wait
    assert await rig.balance(me["id"]) == 0
    await assert_consistent(rig.sm, me["id"])

    assert await finish(rig.sm, first, capture=False)  # the audit failed: its unit is released AND revoked
    lot = await lot_of(rig, out["purchase_id"])
    assert (lot.available, lot.reserved, lot.revoked) == (0, 1, 4)
    assert (
        await rig.balance(me["id"]) == 0
    )  # the user does not get it back, and the balance never went negative
    await assert_consistent(rig.sm, me["id"])

    assert await hold_of(rig, me["id"]) is None
    assert await finish(rig.sm, second, capture=True)  # the other report completed on refunded units
    lot = await lot_of(rig, out["purchase_id"])
    assert (lot.reserved, lot.consumed) == (0, 1)
    assert await hold_of(rig, me["id"]) == "REFUND_CONSUMED"  # for staff to resolve; nothing is clawed back
    await assert_consistent(rig.sm, me["id"])


async def test_units_already_spent_become_a_billing_hold_not_a_debt(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    spent = await submit(rig.sm, me["id"])
    assert spent is not None
    assert await finish(rig.sm, spent, capture=True)  # one report made from the pack

    await report(
        rig, out["transaction_id"], adjustment(out["transaction_id"], "chargeback", "approved", 4000)
    )
    assert (
        await rig.balance(me["id"]) == 0
    )  # the 4 unspent units were taken back; the spent one is not a debt
    assert await hold_of(rig, me["id"]) == "REFUND_CONSUMED"
    async with rig.sm() as s, s.begin():
        with pytest.raises(BillingHoldError):
            await reserve(s, me["id"], "deal_audit", await load_entitlements(s, me["id"]), audit_id=uuid4())
    refused = await c.post(
        "/api/billing/checkout", json={"pack_code": "reports_1"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert (refused.status_code, refused.json()["code"]) == (
        403,
        "BILLING_HOLD",
    )  # no payment for units it cannot use
    assert (await c.get("/api/audits")).status_code == 200  # existing reports stay readable

    admin, _ = await make_admin(rig.app, engine, make_google_token)
    cleared = await admin.post(
        f"/api/admin/users/{me['id']}/billing-hold/clear", json={"note": "reviewed with the buyer"}
    )
    assert (cleared.status_code, cleared.json()) == (200, {"cleared": True})
    assert await hold_of(rig, me["id"]) is None


# ------------------------------------------------------------------------------ overlap, reversal, warnings
async def test_adjustment_overlap_and_reversal(rig: Rig, make_google_token: Any) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    txn = out["transaction_id"]
    refund = adjustment(txn, "refund", "approved", 4000)
    chargeback = adjustment(txn, "chargeback", "approved", 4000)
    await report(rig, txn, refund, chargeback)  # both approved: one reversal, not two
    assert await rig.balance(me["id"]) == 0
    async with rig.sm() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(CreditLedger)
                .where(CreditLedger.user_id == me["id"], CreditLedger.reason == "refund_revoke")
            )
            == 1
        )

    # the chargeback is reversed, but the refund still stands: nothing comes back
    undo = adjustment(txn, "chargeback_reverse", "approved", 4000)
    await report(rig, txn, refund, chargeback, undo)
    assert await rig.balance(me["id"]) == 0
    assert (await rig.purchase(out["purchase_id"])).state == "refunded"


async def test_a_reversed_chargeback_restores_only_what_it_took_and_only_once(
    rig: Rig, make_google_token: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    txn = out["transaction_id"]
    held = await submit(rig.sm, me["id"])
    assert held is not None
    chargeback = adjustment(txn, "chargeback", "approved", 4000)
    await report(rig, txn, chargeback)  # 4 free units taken, 1 held by a running audit
    assert await rig.balance(me["id"]) == 0
    assert await finish(rig.sm, held, capture=False)  # released and revoked: 5 taken in all

    undo = adjustment(txn, "chargeback_reverse", "approved", 4000)
    for _ in range(3):
        await report(rig, txn, chargeback, undo)  # the reversal arrives, and is redelivered
    assert await rig.balance(me["id"]) == 5  # exactly what the reversal had taken, once
    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.refunded_at) == ("granted", None)
    lot = await lot_of(rig, out["purchase_id"])
    assert (lot.available, lot.revoked, lot.frozen, lot.reversed_at) == (5, 0, False, None)
    assert lot.granted == 5  # the original pack was not granted a second time
    async with rig.sm() as s:
        counts = {
            reason: await s.scalar(
                select(func.count())
                .select_from(CreditLedger)
                .where(CreditLedger.user_id == me["id"], CreditLedger.reason == reason)
            )
            for reason in ("topup", "refund_revoke", "refund_restore")
        }
    assert counts == {
        "topup": 1,
        "refund_revoke": 2,
        "refund_restore": 1,
    }  # granted once, taken in two parts, given back once
    await assert_consistent(rig.sm, me["id"])


async def test_a_chargeback_warning_freezes_the_pack_until_it_clears(
    rig: Rig, make_google_token: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    txn = out["transaction_id"]
    warning = adjustment(txn, "chargeback_warning", "pending_approval", 0)
    await report(rig, txn, warning)
    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.error_code) == ("review", "CHARGEBACK_WARNING")
    assert await rig.balance(me["id"]) == 5  # nothing is taken on a warning
    assert (await lot_of(rig, out["purchase_id"])).frozen is True
    async with rig.sm() as s, s.begin():
        assert (
            await reserve(s, me["id"], "deal_audit", await load_entitlements(s, me["id"]), audit_id=uuid4())
            is None
        )  # unspendable

    rig.paddle.adjustments[warning.id] = warning.model_copy(update={"status": "rejected"})
    await rig.deliver(txn, "adjustment.updated")
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    assert (await lot_of(rig, out["purchase_id"])).frozen is False


async def test_a_partial_refund_or_credit_never_turns_into_unit_arithmetic(
    rig: Rig, make_google_token: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c, "reports_5")
    txn = out["transaction_id"]
    await report(
        rig, txn, adjustment(txn, "credit", "approved", 4000)
    )  # a tax/credit correction removes nothing
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    assert await rig.balance(me["id"]) == 5

    await report(rig, txn, adjustment(txn, "refund", "approved", 1000, "adj_part"))
    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.error_code) == ("review", "PARTIAL_REVERSAL")
    assert await rig.balance(me["id"]) == 5  # not rounded, not derived from the money ratio
    assert (await lot_of(rig, out["purchase_id"])).frozen is True
    await report(rig, txn, adjustment(txn, "refund", "rejected", 1000, "adj_part"))
    assert (await rig.purchase(out["purchase_id"])).state == "granted"  # nothing stands any more
    await assert_consistent(rig.sm, me["id"])


async def test_a_refund_request_or_rejection_changes_nothing(rig: Rig, make_google_token: Any) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    txn = out["transaction_id"]
    await report(rig, txn, adjustment(txn, "refund", "rejected", 4000))
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    await report(rig, txn, adjustment(txn, "refund", "pending_approval", 4000, "adj_wait"))
    assert (await rig.purchase(out["purchase_id"])).state == "review"  # surfaced and frozen, not refunded yet
    assert await rig.balance(me["id"]) == 5


# ------------------------------------------------------------------------------ recovery and races
async def test_a_reversal_whose_notification_never_came_is_found_by_reconciliation(
    rig: Rig, make_google_token: Any, engine: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    txn = out["transaction_id"]
    rig.paddle.adjustments["adj_silent"] = adjustment(txn, "refund", "approved", 4000, "adj_silent")
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE app.billing_purchase SET updated_at = now() - interval '1 hour'"))
    done = await reconcile_purchases(rig.sm, rig.paddle)
    assert done.get("reversal:reversed") == 1
    assert await rig.balance(me["id"]) == 0
    assert (await rig.purchase(out["purchase_id"])).state == "refunded"


async def test_a_reversal_racing_with_settling_audits_stays_consistent(
    rig: Rig, make_google_token: Any
) -> None:
    for _ in range(4):
        c, me = await sign_in(rig.app, make_google_token)
        out = await bought(rig, c, "reports_10")
        audits = [
            a for a in await asyncio.gather(*(submit(rig.sm, me["id"]) for _ in range(4))) if a is not None
        ]
        txn = out["transaction_id"]
        rig.paddle.adjustments["adj_race"] = adjustment(txn, "refund", "approved", 7000, "adj_race")
        await rig.deliver(txn, "adjustment.created")
        work = [finish(rig.sm, a, capture=i % 2 == 0) for i, a in enumerate(audits)] + [rig.sweep()]
        await asyncio.wait_for(asyncio.gather(*work), 30)  # no deadlock, no exception
        await rig.sweep()
        async with rig.sm() as s:
            assert await ledger_mismatches(s) == []
            assert await lot_mismatches(s) == []
        lot = await lot_of(rig, out["purchase_id"])
        assert lot.granted == lot.available + lot.reserved + lot.consumed + lot.revoked
        assert (lot.available, lot.reserved) == (0, 0)  # everything is either spent or taken back
        assert await rig.balance(me["id"]) == 0
        rig.paddle.adjustments.clear()


async def test_a_reversal_for_a_deleted_account_has_nobody_to_take_units_from(
    rig: Rig, make_google_token: Any
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await bought(rig, c)
    async with rig.sm() as s, s.begin():
        assert (await delete_account(s, me["id"])).deleted
    await report(rig, out["transaction_id"], adjustment(out["transaction_id"], "refund", "approved", 4000))
    p = await rig.purchase(out["purchase_id"])
    assert p.user_id is None  # the accounting row survived; no exception, no new account
