# ruff: noqa: F811  (the `queue_and_app` fixture is imported from test_password_register)
"""Password login on real Postgres (ADR 0013, docs/PASSWORD-AUTH-SPEC.md sections 1, 4 and 5).

Generic failures, throttling that is not a lockout, rehash on login, and bounded hashing work. The mail queue
is a named fake; users are created through the real register and verify routes.
"""

import asyncio
import logging
import unicodedata
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from rm_api.auth.passwords import PasswordHasher
from rm_core.db.models import CreditLedger, UserCredential, UserSession
from rm_core.settings import Settings
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import FakeQueue, client_for, unique_email
from test_me_saved_admin import MakeToken
from test_password_register import (  # noqa: F401  (fixture: `queue_and_app`)
    GOOD,
    email_of,
    queue_and_app,
    register,
    token_from,
    verify,
)

pytestmark = [pytest.mark.integration]


async def make_user(
    queue: FakeQueue, app: FastAPI, password: str = GOOD, email: str | None = None
) -> tuple[str, dict[str, Any]]:
    email = email or email_of()
    await register(app, email, password)
    r = await verify(app, token_from(queue.auth_mail[-1][2]))
    assert r.status_code == 200
    return email, r.json()


async def login(app: FastAPI, email: str, password: str, ip: str | None = None) -> Any:
    return await client_for(app, ip).post("/api/auth/login", json={"email": email, "password": password})


# ------------------------------------------------------------------------------ the happy path
async def test_login_signs_in_and_reaches_an_authenticated_route(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email, created = await make_user(queue, app)
    c = client_for(app)
    r = await c.post(
        "/api/auth/login", json={"email": email.upper(), "password": GOOD}
    )  # address is case-blind
    assert r.status_code == 200, r.text
    assert r.json() == created
    assert "rm_session" in r.headers.get("set-cookie", "")
    assert (await c.get("/api/me")).json()["email"] == email
    async with async_sessionmaker(engine)() as s:
        assert (
            await s.scalar(
                select(func.count()).select_from(UserSession).where(UserSession.user_id == created["id"])
            )
            == 2
        )
        grants = await s.scalar(
            select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == created["id"])
        )
    assert grants == 1  # logging in never grants signup credits again


async def test_the_password_is_unicode_normalised_before_hashing(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    composed = "zażółć gęślą jaźń 42"
    email, _ = await make_user(queue, app, unicodedata.normalize("NFC", composed))
    r = await login(app, email, unicodedata.normalize("NFD", composed))  # the same text typed another way
    assert r.status_code == 200


# ------------------------------------------------------------------------------ generic failures
async def test_every_failure_looks_the_same_and_unknown_addresses_still_cost_a_hash(
    queue_and_app: tuple[FakeQueue, FastAPI], make_google_token: MakeToken, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    google_only = unique_email()
    await client_for(app).post(
        "/api/auth/google", json={"credential": make_google_token(sub="s-" + uuid4().hex, email=google_only)}
    )
    pending = email_of()
    await register(app, pending)  # registered but the link was never used: no account yet

    dummies: list[int] = []
    real = PasswordHasher.verify_dummy

    async def counting(self: PasswordHasher, password: str) -> None:
        dummies.append(1)
        await real(self, password)

    monkeypatch.setattr(PasswordHasher, "verify_dummy", counting)
    cases = [
        (email, "the wrong passphrase 123"),  # wrong password
        (email_of(), GOOD),  # unknown address
        (google_only, GOOD),  # account with no password
        (pending, GOOD),  # pending registration (unverified)
    ]
    replies = [await login(app, e, p) for e, p in cases]
    assert {r.status_code for r in replies} == {401}
    assert {r.headers["content-type"] for r in replies} == {"application/problem+json"}
    bodies = [{k: v for k, v in r.json().items() if k not in {"instance", "request_id"}} for r in replies]
    assert all(b == bodies[0] for b in bodies)
    assert bodies[0]["code"] == "INVALID_CREDENTIALS"
    assert len(dummies) == 3  # unknown, no-password and pending took the same hash work as the wrong password
    assert all("set-cookie" not in r.headers for r in replies)


# ------------------------------------------------------------------------------ throttling
async def test_login_attempts_are_throttled_per_address_but_never_lock_the_owner_out(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    codes = [
        (await login(app, email, "wrong passphrase 999", ip="198.18.0.1")).status_code for _ in range(10)
    ]
    assert codes == [401] * 10
    blocked = await login(app, email, GOOD, ip="198.18.0.2")  # even the right password, from another IP
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    async with async_sessionmaker(engine)() as s, s.begin():  # the window passes
        await s.execute(text("UPDATE app.rate_limit SET window_start = window_start - interval '2 hours'"))
    assert (await login(app, email, GOOD, ip="198.18.0.3")).status_code == 200  # no lockout


async def test_login_attempts_are_throttled_per_ip_across_addresses(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    _, app = queue_and_app
    ip = "198.19.7.7"
    codes = [(await login(app, email_of(), GOOD, ip=ip)).status_code for _ in range(51)]
    assert codes[:50] == [401] * 50
    assert codes[50] == 429


# ------------------------------------------------------------------------------ bounds and hygiene
async def test_oversized_or_empty_passwords_never_reach_the_hasher(
    queue_and_app: tuple[FakeQueue, FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, app = queue_and_app

    async def boom(*_: object, **__: object) -> None:
        raise AssertionError("the hasher must not run for out-of-bounds input")

    monkeypatch.setattr(PasswordHasher, "verify", boom)
    monkeypatch.setattr(PasswordHasher, "verify_dummy", boom)
    for password in ("x" * 129, "€" * 100, ""):
        r = await login(app, email_of(), password)
        assert (r.status_code, r.json()["code"]) == (422, "VALIDATION_ERROR")
        assert password not in r.text or password == ""
    extra = await client_for(app).post(
        "/api/auth/login", json={"email": email_of(), "password": GOOD, "x": 1}
    )
    assert extra.status_code == 422


async def test_the_password_never_reaches_the_logs(
    queue_and_app: tuple[FakeQueue, FastAPI], caplog: pytest.LogCaptureFixture
) -> None:
    queue, app = queue_and_app
    secret = "an unusual login passphrase 9187"
    email, _ = await make_user(queue, app, secret)
    caplog.set_level(logging.DEBUG)
    await login(app, email, secret)
    await login(app, email, secret + "x")
    assert secret not in caplog.text


# ------------------------------------------------------------------------------ rehash and concurrency
async def test_a_hash_made_with_weaker_parameters_is_replaced_on_login(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email, created = await make_user(queue, app)
    weak = PasswordHasher(
        Settings(
            app_env="test", database_url="", password_argon2_memory_kib=8192, password_argon2_time_cost=1
        )
    )
    old = await weak.hash(GOOD)
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        await s.execute(
            update(UserCredential).where(UserCredential.user_id == created["id"]).values(password_hash=old)
        )
    assert (await login(app, email, GOOD)).status_code == 200
    async with sm() as s:
        now = await s.scalar(
            select(UserCredential.password_hash).where(UserCredential.user_id == created["id"])
        )
    assert now != old
    assert "m=19456,t=2,p=1" in (now or "")  # the current parameters
    assert (await login(app, email, GOOD)).status_code == 200  # and the new hash verifies


async def test_many_simultaneous_logins_all_succeed_under_the_hash_concurrency_cap(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    replies = await asyncio.gather(*(login(app, email, GOOD, ip=f"198.20.1.{i}") for i in range(1, 9)))
    assert [r.status_code for r in replies] == [200] * 8
