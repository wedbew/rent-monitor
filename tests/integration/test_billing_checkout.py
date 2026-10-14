"""Pack catalog and checkout intents on real Postgres with an offline Paddle (docs/PADDLE-INTEGRATION.md §3).

Real: the API, Postgres, session auth, rate limits. Faked, by name: Paddle (`tests/paddle_fake.py`). This
proves the checkout contract offline; no real Paddle sandbox call has been made (docs/LIMITATIONS.md L-020).
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from paddle_fake import FakePaddle
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_api.auth.sessions import create_session
from rm_core.billing import sync_catalog
from rm_core.billing_catalog import Catalog, Pack
from rm_core.db.models import BillingPack, BillingPurchase, User
from rm_core.paddle import PaddleError
from rm_core.privacy import delete_account
from rm_core.settings import Settings
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import FakeCerts, FakeQueue, client_for
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration, pytest.mark.money]
MakeToken = Callable[..., str]
CATALOG = Catalog(
    environment="sandbox",  # test amounts only: the owner has not approved real prices
    packs=(
        Pack("reports_1", 1, "pri_test_one", 1000),
        Pack("reports_5", 5, "pri_test_five", 4000),
        Pack("reports_10", 10, "pri_test_ten", 7000),
    ),
)


@asynccontextmanager
async def running(
    migrated_url: str, keys: GoogleKeys, paddle: FakePaddle | None, catalog: Catalog | None = CATALOG
) -> AsyncIterator[FastAPI]:
    settings = Settings(
        app_env="test",
        database_url=migrated_url,
        public_app_url="https://app.test",
        google_client_id=GOOGLE_AUDIENCE,
    )
    verifier = GoogleVerifier(GOOGLE_AUDIENCE, FakeCerts(keys.certs))
    app = create_app(
        settings,
        email_queue=FakeQueue(),
        google_verifier=verifier,
        paddle_client=paddle,
        catalog=catalog if paddle is not None else None,
    )
    async with LifespanManager(app):
        await asyncio.wait_for(app.state.notify_listener.listening.wait(), 10)
        yield app


@pytest.fixture
async def paddle() -> FakePaddle:
    fake = FakePaddle()
    for pack in CATALOG.packs:
        fake.add_price(pack.price_id, amount_minor=pack.amount_minor)
    return fake


@pytest.fixture
async def app(migrated_url: str, google_keys: GoogleKeys, paddle: FakePaddle) -> AsyncIterator[FastAPI]:
    async with running(migrated_url, google_keys, paddle) as application:
        yield application


@pytest.fixture(autouse=True)
async def clean(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.billing_purchase"))


async def checkout(
    c: Any, pack: str = "reports_5", key: UUID | None = None, *, extra: dict[str, object] | None = None
) -> Any:
    return await c.post(
        "/api/billing/checkout",
        json={"pack_code": pack, **(extra or {})},
        headers={"Idempotency-Key": str(key or uuid4())},
    )


# ------------------------------------------------------------------------------ catalog
async def test_disabled_billing_lists_nothing_and_refuses_checkout(
    migrated_url: str, google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    async with running(migrated_url, google_keys, None) as disabled:
        c, _ = await sign_in(disabled, make_google_token)
        packs = (await c.get("/api/billing/packs")).json()
        assert packs == {"enabled": False, "packs": []}
        r = await checkout(c)
        assert (r.status_code, r.json()["code"]) == (503, "BILLING_UNAVAILABLE")


async def test_packs_come_from_the_approved_catalog_only(app: FastAPI, make_google_token: MakeToken) -> None:
    c, _ = await sign_in(app, make_google_token)
    body = (await c.get("/api/billing/packs")).json()
    assert body["enabled"] is True
    assert [
        (p["code"], p["reports"], p["gross_pln"], p["currency"], p["catalog_version"]) for p in body["packs"]
    ] == [
        ("reports_1", 1, "10", "PLN", 1),
        ("reports_5", 5, "40", "PLN", 1),
        ("reports_10", 10, "70", "PLN", 1),
    ]
    assert (await client_for(app).get("/api/billing/packs")).status_code == 401


async def test_a_changed_price_is_a_new_catalog_version_and_the_old_one_is_kept(engine: AsyncEngine) -> None:
    sm = async_sessionmaker(engine)
    env = "live"  # a separate environment so the sandbox rows of other tests stay untouched
    first = Catalog(
        env,
        (
            Pack("reports_1", 1, "pri_live_a", 1000),
            Pack("reports_5", 5, "pri_live_b", 4000),
            Pack("reports_10", 10, "pri_live_c", 7000),
        ),
    )
    changed = Catalog(
        env,
        (
            Pack("reports_1", 1, "pri_live_a", 1000),
            Pack("reports_5", 5, "pri_live_b2", 4500),
            Pack("reports_10", 10, "pri_live_c", 7000),
        ),
    )
    try:
        async with sm() as s, s.begin():
            await sync_catalog(s, first)
        async with sm() as s, s.begin():
            await sync_catalog(s, first)  # unchanged: no new version
        async with sm() as s, s.begin():
            await sync_catalog(s, changed)
        async with sm() as s:
            rows = (
                await s.scalars(
                    select(BillingPack)
                    .where(BillingPack.environment == env)
                    .order_by(BillingPack.code, BillingPack.catalog_version)
                )
            ).all()
        assert [(r.code, r.catalog_version, r.active) for r in rows] == [
            ("reports_1", 1, True),
            ("reports_10", 1, True),
            ("reports_5", 1, False),  # the sold version is kept, not rewritten
            ("reports_5", 2, True),
        ]
        assert next(r for r in rows if r.code == "reports_5" and r.catalog_version == 1).amount_minor == 4000
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.billing_pack WHERE environment = 'live'"))


# ------------------------------------------------------------------------------ checkout
async def test_checkout_creates_one_server_priced_transaction_bound_to_the_purchase(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, me = await sign_in(app, make_google_token)
    r = await checkout(c, "reports_5")
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["pack_code"], out["reports"], out["gross_pln"], out["state"]) == (
        "reports_5",
        5,
        "40",
        "created",
    )
    assert out["transaction_id"] in paddle.transactions
    assert out["checkout_url"].startswith("https://checkout.test/")
    assert set(out) == {
        "purchase_id",
        "pack_code",
        "reports",
        "gross_pln",
        "currency",
        "state",
        "transaction_id",
        "checkout_url",
        "created_at",
        "granted_at",
        "refunded_at",
    }  # no binding token, no provider payload

    txn = paddle.transactions[out["transaction_id"]]
    assert [(i.price_id, i.quantity) for i in txn.items] == [
        ("pri_test_five", 1)
    ]  # the server chose the price
    assert txn.custom_data is not None
    assert txn.custom_data["purchase_id"] == out["purchase_id"]
    async with async_sessionmaker(engine)() as s:
        row = await s.get_one(BillingPurchase, UUID(out["purchase_id"]))
    assert row.user_id == me["id"]
    assert row.binding_hash == hashlib.sha256(str(txn.custom_data["binding"]).encode()).hexdigest()
    assert row.owner_ref == hashlib.sha256(f"owner:{me['id']}".encode()).hexdigest()
    assert (row.amount_minor, row.price_id, row.catalog_version, row.environment) == (
        4000,
        "pri_test_five",
        1,
        "sandbox",
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"amount_minor": 1},
        {"price_id": "pri_x"},
        {"reports": 99},
        {"quantity": 2},
        {"user_id": "someone"},
        {"discount_id": "dsc_1"},
        {"success_url": "https://evil.test"},
    ],
)
async def test_nothing_a_buyer_sends_can_change_what_is_bought(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken, extra: dict[str, object]
) -> None:
    c, _ = await sign_in(app, make_google_token)
    r = await checkout(c, "reports_1", extra=extra)
    assert (r.status_code, r.json()["code"]) == (422, "VALIDATION_ERROR")
    assert paddle.calls == []
    bad = await checkout(c, "reports_20")
    assert bad.status_code == 422


async def test_checkout_needs_a_verified_signed_in_buyer_and_an_idempotency_key(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    assert (await checkout(client_for(app))).status_code == 401
    c, _ = await sign_in(app, make_google_token)
    missing = await c.post("/api/billing/checkout", json={"pack_code": "reports_1"})
    assert missing.status_code == 422
    not_a_uuid = await c.post(
        "/api/billing/checkout", json={"pack_code": "reports_1"}, headers={"Idempotency-Key": "nope"}
    )
    assert not_a_uuid.status_code == 422

    uid = str(uuid4())  # an account whose address was never confirmed, with a live session
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        s.add(User(id=uid, email=f"{uid}@example.test"))
        await s.flush()
        token = await create_session(s, uid, user_agent="test", ip=None, settings=app.state.settings)
    unverified = client_for(app)
    unverified.cookies.set(app.state.settings.cookie_name, token)
    r = await checkout(unverified)
    assert (r.status_code, r.json()["code"]) == (403, "EMAIL_NOT_VERIFIED")
    assert paddle.calls == []  # nothing reached the provider for any of these


async def test_paddle_checkout_idempotent(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, me = await sign_in(app, make_google_token)
    key = uuid4()
    replies = await asyncio.gather(
        *(checkout(c, "reports_5", key) for _ in range(4))
    )  # inside the 5/min limit
    assert {r.status_code for r in replies} <= {200, 202}
    assert len({r.json()["purchase_id"] for r in replies}) == 1  # one purchase
    assert paddle.calls.count("create_transaction") == 1  # one transaction at Paddle, never two payments
    created = [r for r in replies if r.json()["state"] == "created"]
    assert created, "at least one reply carries the finished transaction"
    assert {r.json()["purchase_id"] for r in created} == {replies[0].json()["purchase_id"]}
    assert paddle.calls.count("create_transaction") == 1

    clash = await checkout(
        c, "reports_10", key
    )  # the fifth request of the minute: a different pack, same key
    assert (clash.status_code, clash.json()["code"]) == (409, "IDEMPOTENCY_CONFLICT")
    assert paddle.calls.count("create_transaction") == 1
    async with async_sessionmaker(engine)() as s:
        assert (
            await s.scalar(
                select(func.count()).select_from(BillingPurchase).where(BillingPurchase.user_id == me["id"])
            )
            == 1
        )


# ------------------------------------------------------------------------------ ambiguity
async def test_paddle_create_timeout_recovery(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, _ = await sign_in(app, make_google_token)
    key = uuid4()
    paddle.fail_create_after_store = True  # the transaction exists at Paddle but the reply was lost
    first = await checkout(c, "reports_5", key)
    assert (first.status_code, first.json()["state"], first.json()["transaction_id"]) == (
        202,
        "creation_unknown",
        None,
    )
    assert paddle.calls.count("create_transaction") == 1

    paddle.fail_create_after_store = False
    again = await checkout(c, "reports_5", key)  # the same request recovers; it does not create a second one
    assert again.status_code == 200
    assert again.json()["state"] == "created"
    assert again.json()["transaction_id"] in paddle.transactions
    assert len(paddle.transactions) == 1
    assert paddle.calls.count("create_transaction") == 1


async def test_an_unrecoverable_creation_stays_unknown_and_is_never_recreated(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)
    key = uuid4()
    paddle.fail_create_before_store = True  # timed out and nothing exists; we cannot know that
    for _ in range(3):
        r = await checkout(c, "reports_1", key)
        assert (r.status_code, r.json()["state"]) == (202, "creation_unknown")
    assert paddle.calls.count("create_transaction") == 1
    assert paddle.transactions == {}


async def test_two_matching_transactions_go_to_review_not_to_a_guess(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)
    key = uuid4()
    paddle.fail_create_after_store = True
    await checkout(c, "reports_1", key)
    (only,) = paddle.transactions.values()
    clone = only.model_copy(update={"id": "txn_clone"})
    paddle.transactions["txn_clone"] = clone  # a second transaction with the same reference and binding
    paddle.fail_create_after_store = False
    r = await checkout(c, "reports_1", key)
    assert r.json()["state"] == "review"
    assert paddle.calls.count("create_transaction") == 1


async def test_a_claim_that_died_mid_call_is_recovered_not_repeated(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, _ = await sign_in(app, make_google_token)
    key = uuid4()
    paddle.fail_create_before_store = True
    first = await checkout(c, "reports_1", key)
    pid = UUID(first.json()["purchase_id"])
    paddle.fail_create_before_store = False
    async with engine.begin() as conn:  # the worker/API holding the claim died: lease expired, state creating
        await conn.execute(
            text(
                "UPDATE app.billing_purchase SET state = 'creating',"
                " lease_until = now() - interval '1 minute' WHERE id = :i"
            ),
            {"i": pid},
        )
    r = await checkout(c, "reports_1", key)
    assert (r.status_code, r.json()["state"]) == (202, "creation_unknown")
    assert paddle.calls.count("create_transaction") == 1


async def test_a_definite_provider_failure_is_a_clean_error_and_a_new_key_can_retry(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)

    async def refuse(*, price_id: str, custom_data: dict[str, str]) -> None:
        raise PaddleError("422")

    real = paddle.create_transaction
    paddle.create_transaction = refuse  # type: ignore[method-assign,assignment]
    key = uuid4()
    r = await checkout(c, "reports_1", key)
    assert (r.status_code, r.json()["code"]) == (502, "BILLING_PROVIDER_ERROR")
    paddle.create_transaction = real
    assert (await checkout(c, "reports_1", key)).status_code == 502  # the same key stays failed
    ok = await checkout(c, "reports_1", uuid4())
    assert ok.json()["state"] == "created"


# ------------------------------------------------------------------------------ limits and tenancy
async def test_checkout_is_throttled_per_user(
    app: FastAPI, paddle: FakePaddle, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)
    codes = [(await checkout(c, "reports_1")).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]  # 5 per minute
    assert paddle.calls.count("create_transaction") == 5


async def test_purchases_are_private_to_their_buyer(app: FastAPI, make_google_token: MakeToken) -> None:
    a, _ = await sign_in(app, make_google_token)
    b, _ = await sign_in(app, make_google_token)
    mine = (await checkout(a, "reports_10")).json()
    assert [p["purchase_id"] for p in (await a.get("/api/billing/purchases")).json()["purchases"]] == [
        mine["purchase_id"]
    ]
    assert (await a.get(f"/api/billing/purchases/{mine['purchase_id']}")).status_code == 200
    foreign = await b.get(f"/api/billing/purchases/{mine['purchase_id']}")
    unknown = await b.get(f"/api/billing/purchases/{uuid4()}")
    assert foreign.status_code == unknown.status_code == 404  # never 403
    assert foreign.json()["code"] == unknown.json()["code"]
    assert (await b.get("/api/billing/purchases")).json() == {"purchases": []}


async def test_erasing_the_account_keeps_the_accounting_record_without_the_user(
    app: FastAPI, make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    c, me = await sign_in(app, make_google_token)
    pid = UUID((await checkout(c, "reports_5")).json()["purchase_id"])
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        assert (await delete_account(s, me["id"])).deleted
    async with sm() as s:
        row = await s.get_one(BillingPurchase, pid)
    assert row.user_id is None  # the link is gone, SET NULL
    assert row.owner_ref == hashlib.sha256(f"owner:{me['id']}".encode()).hexdigest()  # a hash only
    assert (row.pack_code, row.amount_minor, row.provider_txn_id is not None) == ("reports_5", 4000, True)
