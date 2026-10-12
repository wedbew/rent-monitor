"""Data export and account erasure through the API (RM-82; GDPR access and erasure requests)."""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_api.billing_erasure import BillingUnavailable
from rm_core.db.models import (
    AuthIdentity,
    CreditAccount,
    CreditLedger,
    ErasureLog,
    StripeCustomer,
    User,
    UserSession,
)
from rm_core.privacy import user_hash
from rm_core.settings import Settings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from test_auth import Browser, FakeCerts, FakeQueue, client_for, unique_email, wait_until

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]


class FakeEraser:
    def __init__(self, fail: bool = False) -> None:
        self.deleted: list[str] = []
        self.fail = fail
        self.user_still_present: list[bool] = []

    async def delete_customer(self, customer_id: str) -> None:
        if self.fail:
            raise BillingUnavailable
        self.deleted.append(customer_id)


async def make_app(migrated_url: str, keys: GoogleKeys, eraser: FakeEraser | None) -> AsyncIterator[FastAPI]:
    settings = Settings(
        app_env="test",
        database_url=migrated_url,
        public_app_url="https://app.test",
        google_client_id=GOOGLE_AUDIENCE,
    )
    verifier = GoogleVerifier(GOOGLE_AUDIENCE, FakeCerts(keys.certs))
    app = create_app(settings, email_queue=FakeQueue(), google_verifier=verifier, billing_eraser=eraser)
    async with LifespanManager(app):
        await asyncio.wait_for(app.state.notify_listener.listening.wait(), 10)
        yield app


@pytest.fixture
async def app(migrated_url: str, google_keys: GoogleKeys) -> AsyncIterator[FastAPI]:
    async for application in make_app(migrated_url, google_keys, None):
        yield application


@pytest.fixture
async def billing_app(migrated_url: str, google_keys: GoogleKeys) -> AsyncIterator[FastAPI]:
    application_eraser = FakeEraser()
    async for application in make_app(migrated_url, google_keys, application_eraser):
        application.state.test_eraser = application_eraser
        yield application


async def sign_in(
    app: FastAPI, make_token: MakeToken, email: str | None = None
) -> tuple[Browser, dict[str, str]]:
    c = client_for(app)
    r = await c.post(
        "/api/auth/google",
        json={"credential": make_token(sub=f"s-{uuid4().hex}", email=email or unique_email())},
    )
    assert r.status_code == 200
    return c, r.json()


async def rows(engine: AsyncEngine, model: type, user_id: str) -> int:
    async with engine.connect() as conn:
        return int(
            await conn.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)) or 0
        )


# ---------- export ----------
async def test_export_returns_my_data_with_download_headers_and_no_secrets(
    app: FastAPI, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    async with c:
        r = await c.get("/api/me/export")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["profile"]["email"] == me["email"]
    assert body["profile"]["id"] == me["id"]
    assert body["credit_balance"] == 3
    assert [i["provider"] for i in body["identities"]] == ["google"]
    assert len(body["sessions"]) == 1
    raw = c.cookies["rm_session"]
    text = r.text
    assert raw not in text
    assert hashlib.sha256(raw.encode()).hexdigest() not in text  # token hashes are never exported


async def test_export_contains_only_my_data(app: FastAPI, make_google_token: MakeToken) -> None:
    a, me_a = await sign_in(app, make_google_token)
    b, me_b = await sign_in(app, make_google_token)
    async with a, b:
        text_a = (await a.get("/api/me/export")).text
        text_b = (await b.get("/api/me/export")).text
    assert me_b["email"] not in text_a
    assert me_a["email"] not in text_b
    assert me_b["id"] not in text_a


async def test_export_needs_a_session_and_is_limited_to_five_per_hour(
    app: FastAPI, make_google_token: MakeToken
) -> None:
    async with client_for(app) as anonymous:
        assert (await anonymous.get("/api/me/export")).status_code == 401
    c, _ = await sign_in(app, make_google_token)
    async with c:
        codes = [(await c.get("/api/me/export")).status_code for _ in range(7)]
        limited = await c.get("/api/me/export")
    assert codes == [200] * 5 + [429, 429]
    assert limited.json()["code"] == "RATE_LIMITED"
    assert int(limited.headers["retry-after"]) >= 1


# ---------- erasure ----------
async def test_delete_needs_a_session_the_origin_and_the_typed_address(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    async with c, client_for(app, origin=None) as no_origin, client_for(app) as anonymous:
        assert (
            await anonymous.request("DELETE", "/api/me", json={"confirm_email": me["email"]})
        ).status_code == 401
        no_origin.cookies.set("rm_session", c.cookies["rm_session"])
        r = await no_origin.request("DELETE", "/api/me", json={"confirm_email": me["email"]})
        assert r.status_code == 403
        assert r.json()["code"] == "ORIGIN_NOT_ALLOWED"
        wrong = await c.request("DELETE", "/api/me", json={"confirm_email": "someone.else@example.test"})
        assert wrong.status_code == 422
        assert wrong.json()["code"] == "CONFIRMATION_MISMATCH"
        assert (await c.request("DELETE", "/api/me", json={})).status_code == 422
        assert (await c.request("DELETE", "/api/me")).status_code == 422
    assert await rows(engine, UserSession, me["id"]) == 1  # nothing was touched


async def test_delete_erases_everything_logs_only_a_hash_and_ends_the_session(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token, email=unique_email().upper().replace("USER", "user"))
    other, me_other = await sign_in(app, make_google_token)
    async with c, other:
        raw = c.cookies["rm_session"]
        assert (await c.get("/api/auth/sessions")).status_code == 200  # the principal is now cached
        r = await c.request(
            "DELETE", "/api/me", json={"confirm_email": me["email"].upper()}
        )  # case-insensitive
        assert r.status_code == 204
        assert "max-age=0" in r.headers["set-cookie"].lower()
        c.cookies.set("rm_session", raw)  # replay the old cookie

        async def refused() -> bool:
            return (await c.get("/api/auth/sessions")).status_code == 401

        await wait_until(refused, within=2.0)  # the cached principal must not outlive the account
        assert (await other.get("/api/auth/sessions")).status_code == 200  # nobody else is affected
    for model in (UserSession, AuthIdentity, CreditAccount, CreditLedger):
        assert await rows(engine, model, me["id"]) == 0
    async with engine.connect() as conn:
        assert await conn.scalar(select(func.count()).select_from(User).where(User.id == me["id"])) == 0
        logged = await conn.scalar(
            select(func.count()).select_from(ErasureLog).where(ErasureLog.user_hash == user_hash(me["id"]))
        )
    assert logged == 1
    assert await rows(engine, UserSession, me_other["id"]) == 1


async def test_deleting_twice_at_once_is_safe(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    raw = c.cookies["rm_session"]

    async def attempt() -> int:
        async with client_for(app) as other:
            other.cookies.set("rm_session", raw)
            return (await other.request("DELETE", "/api/me", json={"confirm_email": me["email"]})).status_code

    await c.aclose()
    statuses = await asyncio.gather(attempt(), attempt(), attempt())
    assert set(statuses) <= {204, 401}
    assert 204 in statuses
    async with engine.connect() as conn:
        logged = await conn.scalar(
            select(func.count()).select_from(ErasureLog).where(ErasureLog.user_hash == user_hash(me["id"]))
        )
    assert logged == 1


# ---------- the processor's copy ----------
async def add_customer(engine: AsyncEngine, user_id: str, customer_id: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    async with async_sessionmaker(engine)() as s, s.begin():
        s.add(StripeCustomer(user_id=user_id, stripe_customer_id=customer_id))


async def test_the_stripe_customer_is_erased_before_the_account(
    billing_app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    eraser: FakeEraser = billing_app.state.test_eraser
    c, me = await sign_in(billing_app, make_google_token)
    customer = f"cus_{uuid4().hex[:14]}"
    await add_customer(engine, me["id"], customer)
    async with c:
        r = await c.request("DELETE", "/api/me", json={"confirm_email": me["email"]})
    assert r.status_code == 204
    assert eraser.deleted == [customer]
    assert await rows(engine, StripeCustomer, me["id"]) == 0


async def test_a_user_without_a_customer_never_touches_the_processor(
    billing_app: FastAPI, make_google_token: MakeToken
) -> None:
    eraser: FakeEraser = billing_app.state.test_eraser
    c, me = await sign_in(billing_app, make_google_token)
    async with c:
        assert (await c.request("DELETE", "/api/me", json={"confirm_email": me["email"]})).status_code == 204
    assert eraser.deleted == []


async def test_if_the_processor_is_down_nothing_is_deleted_and_the_request_can_be_repeated(
    billing_app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    eraser: FakeEraser = billing_app.state.test_eraser
    c, me = await sign_in(billing_app, make_google_token)
    await add_customer(engine, me["id"], f"cus_{uuid4().hex[:14]}")
    async with c:
        eraser.fail = True
        down = await c.request("DELETE", "/api/me", json={"confirm_email": me["email"]})
        assert down.status_code == 503
        assert await rows(engine, UserSession, me["id"]) == 1
        assert await rows(engine, StripeCustomer, me["id"]) == 1  # the id is still there to retry with
        assert (await c.get("/api/auth/sessions")).status_code == 200  # and the user is still signed in
        eraser.fail = False
        assert (await c.request("DELETE", "/api/me", json={"confirm_email": me["email"]})).status_code == 204
    assert len(eraser.deleted) == 1


async def test_without_a_billing_eraser_a_user_with_a_customer_cannot_be_deleted(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    await add_customer(engine, me["id"], f"cus_{uuid4().hex[:14]}")
    async with c:
        r = await c.request("DELETE", "/api/me", json={"confirm_email": me["email"]})
    assert r.status_code == 503
    assert await rows(engine, StripeCustomer, me["id"]) == 1  # fail safe: the processor id is not lost
