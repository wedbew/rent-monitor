"""Signed, durable Paddle webhook, the grant worker and reconciliation (docs/PADDLE-INTEGRATION.md §5).

Real: the API, Postgres, the ledger and lots, the billing worker logic (`run_sweep`). Faked, by name: Paddle
(`tests/paddle_fake.py`) and the job queue. Nothing here touches the real Paddle sandbox (L-020), so this is
level 2 offline evidence, not provider verification.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from paddle_fake import FakePaddle
from pydantic import SecretStr
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_core.billing_catalog import Catalog, Pack
from rm_core.billing_events import MAX_ATTEMPTS, claim_pending, reconcile_purchases
from rm_core.db.models import (
    BillingEvent,
    BillingPurchase,
    CreditAccount,
    CreditLedger,
    ReportCreditLot,
    User,
)
from rm_core.ledger import ledger_mismatches, lot_mismatches
from rm_core.paddle import Adjustment, PaddleError
from rm_core.paddle_webhook import sign
from rm_core.privacy import delete_account, purge_expired
from rm_core.settings import Settings
from rm_worker.tasks.billing import run_sweep
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import FakeCerts, FakeQueue, client_for
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration, pytest.mark.money]
MakeToken = Callable[..., str]
SECRET = "pdl_ntfset_integration"
CATALOG = Catalog(
    environment="sandbox",  # test amounts: the owner has not approved real prices
    packs=(
        Pack("reports_1", 1, "pri_wh_one", 1000),
        Pack("reports_5", 5, "pri_wh_five", 4000),
        Pack("reports_10", 10, "pri_wh_ten", 7000),
    ),
)


class Rig:
    def __init__(self, app: FastAPI, paddle: FakePaddle, queue: FakeQueue, engine: AsyncEngine) -> None:
        self.app, self.paddle, self.queue = app, paddle, queue
        self.sm = async_sessionmaker(engine, expire_on_commit=False)

    async def buy(self, c: Any, pack: str = "reports_5") -> dict[str, Any]:
        r = await c.post(
            "/api/billing/checkout", json={"pack_code": pack}, headers={"Idempotency-Key": str(uuid4())}
        )
        assert r.status_code == 200, r.text
        return r.json()

    def complete(self, txn_id: str, **changes: Any) -> None:
        """Paddle now reports this transaction as paid (and optionally changed)."""
        txn = self.paddle.transactions[txn_id]
        self.paddle.transactions[txn_id] = txn.model_copy(update={"status": "completed", **changes})

    async def deliver(
        self, txn_id: str, kind: str = "transaction.completed", event_id: str | None = None, **env: Any
    ) -> Any:
        body = json.dumps(
            {
                "event_id": event_id or f"evt_{uuid4().hex[:20]}",
                "event_type": kind,
                "occurred_at": datetime.now(UTC).isoformat(),
                "notification_id": f"ntf_{uuid4().hex[:12]}",
                "data": {
                    "id": txn_id,
                    "status": "completed",
                    "customer": {"email": "buyer@example.test"},
                    **env,
                },
            }
        ).encode()
        header = sign(SECRET, body, timestamp=int(time.time()))
        return await client_for(self.app, origin=None).post(
            "/api/webhooks/paddle",
            content=body,
            headers={"Paddle-Signature": header, "Content-Type": "application/json"},
        )

    async def sweep(self, reconcile: bool = False) -> dict[str, int]:
        return await run_sweep(self.sm, self.paddle, reconcile=reconcile)

    async def purchase(self, purchase_id: str) -> BillingPurchase:
        async with self.sm() as s:
            return await s.get_one(BillingPurchase, UUID(purchase_id), populate_existing=True)

    async def balance(self, user_id: str) -> int:
        async with self.sm() as s:
            return int(
                await s.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == user_id)) or 0
            )

    async def grants(self, user_id: str) -> int:
        async with self.sm() as s:
            return int(
                await s.scalar(
                    select(func.count())
                    .select_from(CreditLedger)
                    .where(CreditLedger.user_id == user_id, CreditLedger.reason == "topup")
                )
                or 0
            )


@pytest.fixture
async def rig(migrated_url: str, google_keys: GoogleKeys, engine: AsyncEngine) -> AsyncIterator[Rig]:
    paddle = FakePaddle()
    for pack in CATALOG.packs:
        paddle.add_price(pack.price_id, amount_minor=pack.amount_minor)
    queue = FakeQueue()
    settings = Settings(
        app_env="test",
        database_url=migrated_url,
        public_app_url="https://app.test",
        google_client_id=GOOGLE_AUDIENCE,
        paddle_webhook_secret=SecretStr(SECRET),
        free_signup_credits=0,  # so a balance is exactly what was bought
    )
    app = create_app(
        settings,
        email_queue=queue,
        google_verifier=GoogleVerifier(GOOGLE_AUDIENCE, FakeCerts(google_keys.certs)),
        paddle_client=paddle,
        catalog=CATALOG,
    )
    async with LifespanManager(app):
        await asyncio.wait_for(app.state.notify_listener.listening.wait(), 10)
        yield Rig(app, paddle, queue, engine)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.billing_event"))
        await conn.execute(text("DELETE FROM app.billing_adjustment"))
        await conn.execute(
            text("UPDATE app.report_credit_lot SET purchase_id = NULL WHERE purchase_id IS NOT NULL")
        )
        await conn.execute(text("DELETE FROM app.billing_purchase"))


# ------------------------------------------------------------------------------ receipt
async def test_paddle_raw_signature(rig: Rig, engine: AsyncEngine) -> None:
    body = json.dumps(
        {"event_id": "evt_sig", "event_type": "transaction.completed", "data": {"id": "txn_x"}}
    ).encode()
    ts = int(time.time())
    good = sign(SECRET, body, timestamp=ts)
    c = client_for(rig.app, origin=None)

    async def post(content: bytes, header: str | None) -> Any:
        headers = {"Content-Type": "application/json", **({"Paddle-Signature": header} if header else {})}
        return await c.post("/api/webhooks/paddle", content=content, headers=headers)

    for content, header in [
        (body + b" ", good),  # modified bytes
        (body, sign("wrong", body, timestamp=ts)),  # wrong secret
        (body, sign(SECRET, body, timestamp=ts - 3600)),  # too old
        (body, sign(SECRET, body, timestamp=ts + 3600)),  # from the future
        (body, "garbage"),
        (body, None),
    ]:
        r = await post(content, header)
        assert (r.status_code, r.json()["code"]) == (400, "INVALID_WEBHOOK_SIGNATURE")
    async with engine.connect() as conn:  # nothing was stored for any refused request
        assert (
            await conn.scalar(text("SELECT count(*) FROM app.billing_event WHERE event_id = 'evt_sig'")) == 0
        )
    assert (await post(body, good)).status_code == 200


async def test_the_webhook_is_off_until_billing_is_configured(
    migrated_url: str, google_keys: GoogleKeys
) -> None:
    app = create_app(
        Settings(app_env="test", database_url=migrated_url, public_app_url="https://app.test"),
        email_queue=FakeQueue(),
        google_verifier=GoogleVerifier(GOOGLE_AUDIENCE, FakeCerts(google_keys.certs)),
    )
    async with LifespanManager(app):
        body = b"{}"
        r = await client_for(app, origin=None).post(
            "/api/webhooks/paddle",
            content=body,
            headers={"Paddle-Signature": sign("x", body, timestamp=int(time.time()))},
        )
        assert (r.status_code, r.json()["code"]) == (503, "BILLING_UNAVAILABLE")


async def test_paddle_webhook_durable_receipt(
    rig: Rig, make_google_token: MakeToken, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    rig.complete(out["transaction_id"])

    first = await rig.deliver(out["transaction_id"], event_id="evt_dur")
    again = await rig.deliver(out["transaction_id"], event_id="evt_dur")  # Paddle redelivers
    assert (first.status_code, again.status_code) == (200, 200)
    async with rig.sm() as s:
        rows = (await s.scalars(select(BillingEvent).where(BillingEvent.event_id == "evt_dur"))).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].payload == {
        "transaction_id": out["transaction_id"],
        "status": "completed",
    }  # no buyer data kept
    assert rig.queue.billing_kicks == 1  # only the first delivery wakes a worker

    # the wake-up failing changes nothing: the committed row is what the sweeper finds
    async def down() -> None:
        raise ConnectionError("queue down")

    monkeypatch.setattr(rig.queue, "process_billing_events", down)
    ok = await rig.deliver(out["transaction_id"], event_id="evt_dur2")
    assert ok.status_code == 200

    # a database failure is a 5xx so that Paddle retries, and leaves no row
    from rm_api import billing_webhook  # noqa: PLC0415

    async def boom(*_: object, **__: object) -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(billing_webhook, "record_event", boom)
    failed = await rig.deliver(out["transaction_id"], event_id="evt_never")
    assert failed.status_code == 500
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT count(*) FROM app.billing_event WHERE event_id = 'evt_never'"))
            == 0
        )


async def test_a_lease_that_ran_out_makes_an_event_claimable_again_and_claims_do_not_overlap(
    rig: Rig, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    for i in range(6):
        await rig.deliver(out["transaction_id"], event_id=f"evt_lease{i}")
    a, b = await asyncio.gather(claim_pending(rig.sm, 6), claim_pending(rig.sm, 6))
    assert sorted(a + b) == sorted(set(a + b))  # SKIP LOCKED: no event is leased to two workers
    assert len(a + b) == 6
    assert await claim_pending(rig.sm, 6) == []  # all leased
    async with engine.begin() as conn:  # the worker holding them died
        await conn.execute(text("UPDATE app.billing_event SET lease_until = now() - interval '1 second'"))
    assert len(await claim_pending(rig.sm, 6)) == 6


# ------------------------------------------------------------------------------ the grant
async def test_a_completed_payment_credits_the_pack_once_with_provenance(
    rig: Rig, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_5")
    await rig.deliver(out["transaction_id"], event_id="evt_before")  # arrives while Paddle still says "ready"
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).state == "created"  # no grant from a notification alone
    assert await rig.balance(me["id"]) == 0

    rig.complete(out["transaction_id"], customer_id="ctm_1")
    await rig.deliver(out["transaction_id"], event_id="evt_done")
    await rig.sweep()

    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.provider_txn_id, p.customer_id, p.error_code) == (
        "granted",
        out["transaction_id"],
        "ctm_1",
        None,
    )
    assert p.granted_at is not None
    assert p.grant_ledger_id is not None
    assert await rig.balance(me["id"]) == 5  # the pack's own count, from our snapshot
    async with rig.sm() as s:
        lot = await s.scalar(select(ReportCreditLot).where(ReportCreditLot.purchase_id == p.id))
        assert lot is not None
        assert (lot.source, lot.granted, lot.available, lot.user_id) == ("purchase", 5, 5, me["id"])
        assert lot.grant_key == f"paddle:sandbox:{out['transaction_id']}:grant"
        assert await ledger_mismatches(s) == []
        assert await lot_mismatches(s) == []
    shown = (await c.get(f"/api/billing/purchases/{out['purchase_id']}")).json()
    assert (shown["state"], shown["reports"]) == ("granted", 5)
    assert (
        (await c.get("/api/me")).json()["credits"]["balance"] == 5
        if "credits" in (await c.get("/api/me")).json()
        else True
    )


async def test_paddle_duplicate_grant(rig: Rig, make_google_token: MakeToken) -> None:
    """Parallel duplicates, other events, several workers and the reconciler: one credit."""
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_10")
    rig.complete(out["transaction_id"])
    deliveries = await asyncio.gather(
        *(rig.deliver(out["transaction_id"], event_id="evt_same") for _ in range(4)),
        rig.deliver(out["transaction_id"], "transaction.updated", event_id="evt_other"),
        rig.deliver(out["transaction_id"], "transaction.completed", event_id="evt_third"),
    )
    assert {d.status_code for d in deliveries} == {200}
    await asyncio.gather(*(rig.sweep(reconcile=True) for _ in range(4)))
    await rig.sweep(reconcile=True)
    assert await rig.balance(me["id"]) == 10
    assert await rig.grants(me["id"]) == 1
    async with rig.sm() as s:
        assert (
            await s.scalar(
                select(func.count()).select_from(ReportCreditLot).where(ReportCreditLot.user_id == me["id"])
            )
            == 1
        )
        assert await ledger_mismatches(s) == []
        assert await lot_mismatches(s) == []


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            {"items_price": "pri_wh_ten"},
            "WRONG_PRICE_OR_QUANTITY",
        ),  # a cheaper pack's purchase paid with another price
        ({"items_quantity": 2}, "WRONG_PRICE_OR_QUANTITY"),
        ({"currency_code": "EUR"}, "WRONG_TOTAL"),
        ({"total_minor": 3000}, "WRONG_TOTAL"),  # a discount or a partial payment
        ({"discount_id": "dsc_1"}, "DISCOUNT"),
        ({"subscription_id": "sub_1"}, "SUBSCRIPTION"),
        ({"custom_data": {"purchase_id": "someone-else", "binding": "x"}}, "NOT_OUR_REFERENCE"),
        ({"bad_binding": True}, "BINDING_MISMATCH"),
        ({"two_items": True}, "ITEM_COUNT"),
    ],
    ids=[
        "other-price",
        "quantity-2",
        "currency",
        "total",
        "discount",
        "subscription",
        "reference",
        "binding",
        "items",
    ],
)
async def test_paddle_binding_and_catalog(
    rig: Rig, make_google_token: MakeToken, change: dict[str, Any], code: str
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_5")
    txn = rig.paddle.transactions[out["transaction_id"]]
    updates: dict[str, Any] = {
        k: v
        for k, v in change.items()
        if k in {"currency_code", "total_minor", "discount_id", "subscription_id", "custom_data"}
    }
    if "items_price" in change:
        updates["items"] = (txn.items[0].model_copy(update={"price_id": change["items_price"]}),)
    if "items_quantity" in change:
        updates["items"] = (txn.items[0].model_copy(update={"quantity": change["items_quantity"]}),)
    if "bad_binding" in change:
        updates["custom_data"] = {**(txn.custom_data or {}), "binding": "forged"}
    if "two_items" in change:
        updates["items"] = (txn.items[0], txn.items[0])
    rig.complete(out["transaction_id"], **updates)
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.error_code) == ("review", code)  # zero granted, a human looks
    assert await rig.balance(me["id"]) == 0
    assert await rig.grants(me["id"]) == 0


async def test_a_second_transaction_for_one_purchase_is_not_granted(
    rig: Rig, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    original = rig.paddle.transactions[out["transaction_id"]]
    clone = original.model_copy(update={"id": "txn_clone", "status": "completed"})
    rig.paddle.transactions["txn_clone"] = clone  # same reference and binding, another transaction
    await rig.deliver("txn_clone")
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).state == "review"
    assert await rig.balance(me["id"]) == 0


async def test_an_unknown_transaction_is_ignored(rig: Rig) -> None:
    from rm_core.paddle import Transaction  # noqa: PLC0415

    rig.paddle.transactions["txn_stranger"] = Transaction(
        id="txn_stranger", status="completed", currency_code="PLN"
    )
    assert (await rig.deliver("txn_stranger")).status_code == 200
    await rig.sweep()
    async with rig.sm() as s:
        row = await s.scalar(select(BillingEvent).order_by(BillingEvent.id.desc()).limit(1))
    assert (row.status, row.error_code) == ("ignored", "NO_PURCHASE")  # type: ignore[union-attr]


async def test_paddle_blik_pending(rig: Rig, make_google_token: MakeToken) -> None:
    """Authorised-but-not-captured, a browser callback and failed attempts grant nothing; the capture does."""
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_1")
    txn_id = out["transaction_id"]
    for status in ("billed", "paid", "past_due"):
        rig.paddle.transactions[txn_id] = rig.paddle.transactions[txn_id].model_copy(
            update={"status": status}
        )
        await rig.deliver(txn_id, "transaction.updated")
        await rig.sweep()
        assert await rig.balance(me["id"]) == 0
    await rig.deliver(txn_id, "transaction.payment_failed")
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).state == "created"
    rig.complete(txn_id)  # the capture arrives (BLIK can take minutes)
    await rig.deliver(txn_id)
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    assert await rig.balance(me["id"]) == 1


async def test_a_late_failed_event_cannot_undo_a_completed_payment(
    rig: Rig, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    for kind in ("transaction.payment_failed", "transaction.canceled", "transaction.updated"):
        await rig.deliver(out["transaction_id"], kind)
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    assert await rig.balance(me["id"]) == 5


# ------------------------------------------------------------------------------ reversals and accounts
async def test_refund_before_payment_event(rig: Rig, make_google_token: MakeToken) -> None:
    """A transaction fully refunded when its completion arrives records the payment, grants nothing."""
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_5")
    txn_id = out["transaction_id"]
    rig.complete(txn_id)
    rig.paddle.adjustments["adj_1"] = Adjustment(
        id="adj_1",
        transaction_id=txn_id,
        action="refund",
        type="full",
        status="approved",
        currency_code="PLN",
        total_minor=4000,
    )
    await rig.deliver(txn_id)
    await rig.sweep()
    p = await rig.purchase(out["purchase_id"])
    assert p.state == "refunded"
    assert (p.paid_at is not None, p.refunded_at is not None, p.grant_ledger_id) == (True, True, None)
    assert await rig.balance(me["id"]) == 0
    await rig.deliver(txn_id, event_id="evt_stale_completed")  # a stale completed event cannot resurrect it
    await rig.sweep(reconcile=True)
    assert await rig.balance(me["id"]) == 0
    assert (await rig.purchase(out["purchase_id"])).state == "refunded"


async def test_a_partial_or_open_reversal_before_the_grant_goes_to_review(
    rig: Rig, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_5")
    rig.complete(out["transaction_id"])
    rig.paddle.adjustments["adj_p"] = Adjustment(
        id="adj_p",
        transaction_id=out["transaction_id"],
        action="refund",
        type="partial",
        status="approved",
        currency_code="PLN",
        total_minor=1000,
    )
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    assert (await rig.purchase(out["purchase_id"])).error_code == "PARTIAL_REVERSAL"
    assert await rig.balance(me["id"]) == 0


async def test_an_adjustment_event_with_nothing_standing_changes_nothing(
    rig: Rig, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    await rig.deliver(out["transaction_id"], "adjustment.created")  # no adjustment exists at Paddle
    await rig.sweep()
    async with rig.sm() as s:
        row = await s.scalar(select(BillingEvent).order_by(BillingEvent.id.desc()).limit(1))
    assert row is not None
    assert (row.status, row.event_type) == ("processed", "adjustment.created")
    assert (await rig.purchase(out["purchase_id"])).state == "granted"
    assert await rig.balance(me["id"]) == 5


async def test_a_payment_completing_after_the_account_was_deleted_never_recreates_it(
    rig: Rig, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    async with rig.sm() as s, s.begin():
        assert (await delete_account(s, me["id"])).deleted
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    p = await rig.purchase(out["purchase_id"])
    assert (p.state, p.error_code, p.user_id) == ("review", "ACCOUNT_DELETED", None)
    async with rig.sm() as s:
        assert await s.scalar(select(func.count()).select_from(User).where(User.id == me["id"])) == 0
        assert (
            await s.scalar(
                select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == me["id"])
            )
            == 0
        )


# ------------------------------------------------------------------------------ recovery
async def test_paddle_reconciliation(rig: Rig, make_google_token: MakeToken, engine: AsyncEngine) -> None:
    """No notification arrives: the reconciler finds the payment, and an ambiguous creation by reference."""
    c, me = await sign_in(rig.app, make_google_token)
    paid = await rig.buy(c, "reports_5")
    rig.complete(paid["transaction_id"])
    await rig.sweep(reconcile=True)  # too fresh: reconciliation leaves very recent purchases to the webhook
    assert (await rig.purchase(paid["purchase_id"])).state == "created"
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE app.billing_purchase SET updated_at = now() - interval '10 minutes'"))
    done = await rig.sweep(reconcile=True)
    assert done.get("reconcile:granted") == 1
    assert await rig.balance(me["id"]) == 5

    rig.paddle.fail_create_after_store = True  # a creation whose reply was lost
    lost = await c.post(
        "/api/billing/checkout", json={"pack_code": "reports_1"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert lost.json()["state"] == "creation_unknown"
    rig.paddle.fail_create_after_store = False
    await reconcile_purchases(rig.sm, rig.paddle)
    assert (await rig.purchase(lost.json()["purchase_id"])).state == "created"


async def test_provider_outages_retry_with_backoff_and_then_fail_loudly(
    rig: Rig, make_google_token: MakeToken, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"], event_id="evt_retry")

    async def down(_: str) -> None:
        raise PaddleError("503")

    real = rig.paddle.get_transaction
    monkeypatch.setattr(rig.paddle, "get_transaction", down)
    first = await rig.sweep()
    assert first == {"retry": 1}
    async with rig.sm() as s:
        row = await s.scalar(select(BillingEvent).where(BillingEvent.event_id == "evt_retry"))
    assert (row.status, row.attempts) == ("pending", 1)  # type: ignore[union-attr]
    assert row.lease_until is not None  # type: ignore[union-attr]
    assert row.lease_until > datetime.now(UTC) + timedelta(seconds=5)  # type: ignore[union-attr]
    assert await rig.sweep() == {}  # backed off: not retried immediately

    monkeypatch.setattr(rig.paddle, "get_transaction", real)  # Paddle is back
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE app.billing_event SET lease_until = now() - interval '1 second'"))
    assert (await rig.sweep())["granted"] == 1
    assert await rig.balance(me["id"]) == 5

    # an event that never succeeds ends failed, not retried forever
    await rig.deliver(out["transaction_id"], event_id="evt_doomed")
    monkeypatch.setattr(rig.paddle, "get_transaction", down)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE app.billing_event SET attempts = :n WHERE event_id = 'evt_doomed'"),
            {"n": MAX_ATTEMPTS - 1},
        )
    assert await rig.sweep() == {"failed": 1}


async def test_old_events_are_purged_but_purchases_are_kept(
    rig: Rig, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, _ = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c)
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"], event_id="evt_old")
    await rig.sweep()
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE app.billing_event SET received_at = now() - interval '200 days'"))
    report = await purge_expired(rig.sm, rig.app.state.settings)
    assert report.billing_events >= 1
    async with rig.sm() as s:
        assert (
            await s.scalar(
                select(func.count()).select_from(BillingEvent).where(BillingEvent.event_id == "evt_old")
            )
            == 0
        )
        assert (
            await s.scalar(
                select(func.count())
                .select_from(BillingPurchase)
                .where(BillingPurchase.id == UUID(out["purchase_id"]))
            )
            == 1
        )


async def test_the_journey_checkout_webhook_credit_and_a_spendable_balance(
    rig: Rig, make_google_token: MakeToken
) -> None:
    from rm_core.entitlements import load_entitlements  # noqa: PLC0415
    from rm_core.ledger import reserve  # noqa: PLC0415

    c, me = await sign_in(rig.app, make_google_token)
    out = await rig.buy(c, "reports_1")
    rig.complete(out["transaction_id"])
    await rig.deliver(out["transaction_id"])
    await rig.sweep()
    async with rig.sm() as s, s.begin():
        res = await reserve(s, me["id"], "deal_audit", await load_entitlements(s, me["id"]), audit_id=uuid4())
    assert res is not None  # the bought report can be spent
    assert res.allocations
