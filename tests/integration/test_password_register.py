"""Email/password registration and verification on real Postgres (ADR 0013, docs/PASSWORD-AUTH-SPEC.md).

Real API, Postgres, the Argon2id hasher and the ledger; the mail queue is a named fake that records what would
be sent. This proves the flow offline; real Resend delivery is unverified (docs/BLOCKERS.md B-004).
"""

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from google_helpers import GoogleKeys
from rm_api.auth.passwords import COMMON, CONTAINS_EMAIL, PasswordHasher, check_policy
from rm_core.db.models import AuthToken, CreditAccount, CreditLedger, User, UserCredential
from rm_core.privacy import delete_account, purge_expired
from rm_core.settings import Settings
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import FakeQueue, client_for, running, unique_email
from test_me_saved_admin import MakeToken

pytestmark = [pytest.mark.integration]
GOOD = "correct horse battery staple"


@pytest.fixture
async def queue_and_app(
    migrated_url: str, google_keys: GoogleKeys
) -> AsyncIterator[tuple[FakeQueue, FastAPI]]:
    queue = FakeQueue()
    async with running(migrated_url, google_keys, queue) as app:
        yield queue, app


def email_of() -> str:
    return f"pw-{uuid4().hex[:12]}@example.pl"


def token_from(url: str | None) -> str:
    assert url is not None
    assert "#t=" in url  # fragment, never a query string
    return url.split("#t=", 1)[1]


async def register(app: FastAPI, email: str, password: str = GOOD, ip: str | None = None) -> Any:
    return await client_for(app, ip).post("/api/auth/register", json={"email": email, "password": password})


async def verify(app: FastAPI, token: str, client: Any = None) -> Any:
    return await (client or client_for(app)).post("/api/auth/register/verify", json={"token": token})


# ------------------------------------------------------------------------------ the happy path
async def test_register_verify_then_an_authenticated_api_call(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email = email_of()
    r = await register(app, email)
    assert (r.status_code, r.json()) == (202, {})
    kind, to, url = queue.auth_mail[-1]
    assert (kind, to) == ("register", email)
    sm = async_sessionmaker(engine)
    async with sm() as s:
        assert (
            await s.scalar(select(User.id).where(User.email == email)) is None
        )  # no account before the link

    c = client_for(app)
    verified = await verify(app, token_from(url), c)
    assert verified.status_code == 200, verified.text
    me = verified.json()
    assert me["email"] == email
    assert me["email_verified"] is True
    assert "rm_session" in verified.headers.get("set-cookie", "")
    assert (await c.get("/api/me")).status_code == 200  # signed in by the verification

    async with sm() as s:
        stored = await s.scalar(
            select(UserCredential.password_hash).where(UserCredential.user_id == me["id"])
        )
        assert stored is not None
        assert stored.startswith("$argon2id$")
        assert GOOD not in stored  # a hash, never the password
        assert await s.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == me["id"])) == 3
        spent = await s.scalar(select(AuthToken.used_at).where(AuthToken.email == email))
        assert spent is not None
    hasher = PasswordHasher(Settings(app_env="test", database_url=""))
    assert (await hasher.verify(GOOD, stored))[0] is True
    assert (await hasher.verify("wrong horse battery staple", stored))[0] is False


# ------------------------------------------------------------------------------ non-enumeration
async def test_new_and_existing_addresses_get_the_same_answer(
    queue_and_app: tuple[FakeQueue, FastAPI], make_google_token: MakeToken
) -> None:
    queue, app = queue_and_app
    taken = unique_email()
    await client_for(app).post(
        "/api/auth/google", json={"credential": make_google_token(sub="s-" + uuid4().hex, email=taken)}
    )
    fresh = email_of()
    a, b = await register(app, fresh), await register(app, taken)
    assert (a.status_code, a.json(), a.headers["content-type"]) == (
        b.status_code,
        b.json(),
        b.headers["content-type"],
    )
    kinds = {to: (kind, url) for kind, to, url in queue.auth_mail}
    assert kinds[fresh][0] == "register"
    assert kinds[taken] == ("account_exists", None)  # the owner is told; no link, no token
    async with async_sessionmaker(app.state.engine)() as s:
        assert (
            await s.scalar(select(func.count()).select_from(AuthToken).where(AuthToken.email == taken)) == 0
        )


async def test_resend_is_silent_about_what_exists(queue_and_app: tuple[FakeQueue, FastAPI]) -> None:
    queue, app = queue_and_app
    email = email_of()
    nothing = await client_for(app).post("/api/auth/register/resend", json={"email": email_of()})
    assert (nothing.status_code, nothing.json()) == (202, {})
    assert queue.auth_mail == []

    await register(app, email)
    first = token_from(queue.auth_mail[-1][2])
    again = await client_for(app).post("/api/auth/register/resend", json={"email": email})
    assert again.status_code == 202
    second = token_from(queue.auth_mail[-1][2])
    assert second != first
    assert (await verify(app, first)).status_code == 401  # the old link stops working
    assert (await verify(app, second)).status_code == 200


# ------------------------------------------------------------------------------ concurrency
async def test_concurrent_registrations_leave_one_live_token_and_the_last_wins(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email = email_of()
    replies = await asyncio.gather(*(register(app, email, f"{GOOD} {i}") for i in range(5)))
    assert {r.status_code for r in replies} == {202}
    async with async_sessionmaker(engine)() as s:
        live = await s.scalar(
            select(func.count())
            .select_from(AuthToken)
            .where(AuthToken.email == email, AuthToken.used_at.is_(None))
        )
    assert live == 1  # the advisory lock serialised them: no unique-index collision, one pending registration
    tokens = [token_from(url) for kind, to, url in queue.auth_mail if to == email]
    results = await asyncio.gather(*(verify(app, t) for t in tokens))
    assert sorted(r.status_code for r in results) == [200, 401, 401, 401, 401]


async def test_concurrent_verification_of_one_token_creates_one_account_and_one_grant(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email = email_of()
    await register(app, email)
    token = token_from(queue.auth_mail[-1][2])
    results = await asyncio.gather(*(verify(app, token) for _ in range(6)))
    assert sorted(r.status_code for r in results) == [200, 401, 401, 401, 401, 401]
    async with async_sessionmaker(engine)() as s:
        assert await s.scalar(select(func.count()).select_from(User).where(User.email == email)) == 1
        uid = await s.scalar(select(User.id).where(User.email == email))
        grants = await s.scalar(
            select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == uid)
        )
    assert grants == 1  # signup credits granted once


# ------------------------------------------------------------------------------ account safety
async def test_a_link_cannot_attach_a_password_to_an_account_that_appeared_meanwhile(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    queue, app = queue_and_app
    email = unique_email()  # a gmail.com address: Google is authoritative, so it can create the account
    await register(app, email, "attacker chosen passphrase")
    token = token_from(queue.auth_mail[-1][2])
    g = await client_for(app).post(
        "/api/auth/google", json={"credential": make_google_token(sub="s-" + uuid4().hex, email=email)}
    )
    assert g.status_code == 200
    r = await verify(app, token)
    assert r.status_code == 409
    assert r.json()["code"] == "ACCOUNT_EXISTS"
    async with async_sessionmaker(engine)() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(UserCredential)
                .where(UserCredential.user_id == g.json()["id"])
            )
            == 0
        )
    assert (await verify(app, token)).status_code == 401  # and the link is spent


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("password123", COMMON),
        ("1234567890", COMMON),
        ("zzzzzzzzzz", COMMON),
        ("my-email-is-secret", CONTAINS_EMAIL),
    ],
)
async def test_a_weak_password_is_refused_without_side_effects(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine, password: str, reason: str
) -> None:
    queue, app = queue_and_app
    email = f"my-email-{uuid4().hex[:6]}@example.pl"
    local = email.split("@", maxsplit=1)[0]
    r = await register(app, email, password if reason != CONTAINS_EMAIL else f"x-{local}-x")
    assert r.status_code == 422
    assert (r.json()["code"], r.json()["reason"]) == ("WEAK_PASSWORD", reason)
    assert queue.auth_mail == []
    async with async_sessionmaker(engine)() as s:
        assert (
            await s.scalar(select(func.count()).select_from(AuthToken).where(AuthToken.email == email)) == 0
        )


async def test_a_password_below_the_floor_is_a_validation_error_that_does_not_echo_it(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    r = await register(app, email_of(), "tooshort1")
    assert (r.status_code, r.json()["code"]) == (422, "VALIDATION_ERROR")
    assert "tooshort1" not in r.text
    assert queue.auth_mail == []


def test_the_policy_has_no_composition_rules_and_checks_the_address() -> None:
    assert check_policy(GOOD, "a@example.pl") is None
    assert check_policy("alllowercaseletters", "a@example.pl") is None  # no digit or symbol required
    assert check_policy("jan.kowalski-secret", "jan.kowalski@example.pl") == CONTAINS_EMAIL
    assert check_policy("abcabcabc1", "ab@example.pl") is None  # a very short local part is not matched
    assert (
        check_policy("".join(chr(ord(ch) + 0xFEE0) for ch in "password123"), "a@example.pl") == COMMON
    )  # NFKC folds full-width forms first


# ------------------------------------------------------------------------------ tokens
async def test_expired_replayed_and_wrong_purpose_tokens_are_refused(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email = email_of()
    await register(app, email)
    token = token_from(queue.auth_mail[-1][2])
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        await s.execute(
            update(AuthToken)
            .where(AuthToken.email == email)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    expired = await verify(app, token)
    assert (expired.status_code, expired.json()["code"]) == (401, "AUTH_TOKEN_INVALID")

    other = email_of()
    await register(app, other)
    good = token_from(queue.auth_mail[-1][2])
    assert (await verify(app, good)).status_code == 200
    assert (await verify(app, good)).status_code == 401  # replay

    async with sm() as s, s.begin():  # a reset-purpose token must not complete a registration
        await s.execute(
            text(
                "INSERT INTO app.auth_token (token_hash, purpose, email, expires_at)"
                " VALUES (:h, 'reset', :e, now() + interval '1 hour')"
            ),
            {"h": hashlib.sha256(b"r" * 40).hexdigest(), "e": email_of()},
        )
    assert (await verify(app, "r" * 40)).status_code == 401
    assert (await verify(app, "not a token")).status_code == 422


# ------------------------------------------------------------------------------ throttling
async def test_registration_is_throttled_per_address_and_per_ip(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    email = email_of()
    codes = [(await register(app, email, ip="203.0.113.7")).status_code for _ in range(6)]
    assert codes == [202] * 5 + [429]  # 5 per address per hour
    ip = "203.0.113.99"
    codes = [(await register(app, email_of(), ip=ip)).status_code for _ in range(21)]
    assert codes[:20] == [202] * 20
    assert codes[20] == 429  # 20 per IP per hour
    assert len(queue.auth_mail) == 25


# ------------------------------------------------------------------------------ hygiene and retention
async def test_neither_the_password_nor_the_token_reaches_the_logs(
    queue_and_app: tuple[FakeQueue, FastAPI], caplog: pytest.LogCaptureFixture
) -> None:
    queue, app = queue_and_app
    caplog.set_level(logging.DEBUG)
    email = email_of()
    secret = "very unusual passphrase 7731"
    await register(app, email, secret)
    token = token_from(queue.auth_mail[-1][2])
    await verify(app, token)
    await verify(app, token)
    assert secret not in caplog.text
    assert token not in caplog.text


async def test_expired_tokens_are_purged_and_erasure_removes_credentials_and_pending_registrations(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    sm = async_sessionmaker(engine)
    email, pending = email_of(), email_of()
    await register(app, email)
    me = (await verify(app, token_from(queue.auth_mail[-1][2]))).json()
    await register(app, pending)
    async with sm() as s, s.begin():
        await s.execute(
            update(AuthToken)
            .where(AuthToken.email == email)
            .values(used_at=datetime.now(UTC) - timedelta(days=3))
        )
    report = await purge_expired(sm, app.state.settings)
    assert report.auth_tokens >= 1
    async with sm() as s:
        assert (
            await s.scalar(select(func.count()).select_from(AuthToken).where(AuthToken.email == email)) == 0
        )
        assert (
            await s.scalar(select(func.count()).select_from(AuthToken).where(AuthToken.email == pending)) == 1
        )

    async with sm() as s, s.begin():
        await delete_account(s, me["id"])
    async with sm() as s:
        assert (
            await s.scalar(
                select(func.count()).select_from(UserCredential).where(UserCredential.user_id == me["id"])
            )
            == 0
        )


async def test_erasing_an_account_also_removes_a_pending_registration_for_its_address(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    _queue, app = queue_and_app
    sm = async_sessionmaker(engine)
    email = unique_email()
    await register(app, email)  # pending: the address has no account yet
    g = await client_for(app).post(
        "/api/auth/google", json={"credential": make_google_token(sub="s-" + uuid4().hex, email=email)}
    )
    async with sm() as s, s.begin():
        await delete_account(s, g.json()["id"])
    async with sm() as s:
        assert (
            await s.scalar(select(func.count()).select_from(AuthToken).where(AuthToken.email == email)) == 0
        )
