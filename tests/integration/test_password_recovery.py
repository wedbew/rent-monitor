# ruff: noqa: F811  (the `queue_and_app` fixture is imported from test_password_register)
"""Forgot, reset and change password on real Postgres (ADR 0013, docs/PASSWORD-AUTH-SPEC.md sections 1-5).

Non-enumeration, single-use hashed tokens, one-use under concurrency, session revocation and safe linking. The
mail queue is a named fake; accounts are made through the real register, verify and Google routes.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from rm_core.db.models import AuthToken, User, UserCredential
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import FakeQueue, client_for, unique_email
from test_me_saved_admin import MakeToken
from test_password_login import login, make_user
from test_password_register import (  # noqa: F401  (fixture: `queue_and_app`)
    GOOD,
    email_of,
    queue_and_app,
    register,
    token_from,
    verify,
)

pytestmark = [pytest.mark.integration]
NEW = "a brand new passphrase 2026"


async def forgot(app: FastAPI, email: str, ip: str | None = None) -> Any:
    return await client_for(app, ip).post("/api/auth/password/forgot", json={"email": email})


async def reset(app: FastAPI, token: str, password: str = NEW) -> Any:
    return await client_for(app).post("/api/auth/password/reset", json={"token": token, "password": password})


def reset_mails(queue: FakeQueue, email: str) -> list[str]:
    return [token_from(url) for kind, to, url in queue.auth_mail if kind == "reset" and to == email]


# ------------------------------------------------------------------------------ forgot
async def test_forgot_answers_the_same_whether_or_not_the_address_has_an_account(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    known, _ = await make_user(queue, app)
    unknown = email_of()
    a, b = await forgot(app, known), await forgot(app, unknown)
    assert (a.status_code, a.json(), a.headers["content-type"]) == (
        b.status_code,
        b.json(),
        b.headers["content-type"],
    )
    assert len(reset_mails(queue, known)) == 1
    assert reset_mails(queue, unknown) == []  # nothing is sent to an address with no account


async def test_the_reset_link_points_at_the_configured_app_origin(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    r = await client_for(app).post(
        "/api/auth/password/forgot",
        json={"email": email},
        headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"},
    )
    assert r.status_code == 202
    url = next(u for k, to, u in queue.auth_mail if k == "reset" and to == email)
    assert url is not None
    assert url.startswith(app.state.settings.public_origin + "/")
    assert "evil.example" not in url


async def test_a_queue_outage_does_not_change_the_answer(queue_and_app: tuple[FakeQueue, FastAPI]) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)

    async def down(*, kind: str, email: str, url: str | None) -> None:
        raise ConnectionError("queue down")

    queue.send_auth_mail = down
    known, unknown = await forgot(app, email), await forgot(app, email_of())
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json()) == (202, {})


async def test_forgot_is_throttled_per_address(queue_and_app: tuple[FakeQueue, FastAPI]) -> None:
    _, app = queue_and_app
    email = email_of()
    codes = [(await forgot(app, email, ip="203.0.113.50")).status_code for _ in range(6)]
    assert codes == [202] * 5 + [429]


async def test_a_second_request_replaces_the_first_link(queue_and_app: tuple[FakeQueue, FastAPI]) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    await forgot(app, email)
    await forgot(app, email)
    first, second = reset_mails(queue, email)
    assert (await reset(app, first)).status_code == 401
    assert (await reset(app, second)).status_code == 204


# ------------------------------------------------------------------------------ reset
async def test_reset_sets_the_password_signs_everyone_out_and_signs_nobody_in(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    browser = client_for(app)
    assert (await browser.post("/api/auth/login", json={"email": email, "password": GOOD})).status_code == 200
    assert (await browser.get("/api/me")).status_code == 200  # a live, cached session

    await forgot(app, email)
    r = await reset(app, reset_mails(queue, email)[0])
    assert r.status_code == 204
    assert "set-cookie" not in r.headers  # nobody is signed in by a reset
    assert (
        await browser.get("/api/me")
    ).status_code == 401  # the old session is gone at once, cache included
    assert (await login(app, email, GOOD)).status_code == 401
    assert (await login(app, email, NEW)).status_code == 200


async def test_expired_replayed_wrong_purpose_and_weak_resets(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    sm = async_sessionmaker(engine)

    await forgot(app, email)
    weak = reset_mails(queue, email)[-1]
    refused = await reset(app, weak, "password123")
    assert (refused.status_code, refused.json()["reason"]) == (422, "common")
    assert (await reset(app, weak)).status_code == 204  # a weak attempt did not spend the link
    assert (await reset(app, weak)).status_code == 401  # replay

    await forgot(app, email)
    old = reset_mails(queue, email)[-1]
    async with sm() as s, s.begin():
        await s.execute(
            update(AuthToken)
            .where(AuthToken.email == email)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert (await reset(app, old)).status_code == 401

    other = email_of()
    await register(app, other)
    register_token = token_from(queue.auth_mail[-1][2])
    assert (await reset(app, register_token)).status_code == 401  # a registration link cannot reset anything
    assert (await verify(app, register_token)).status_code == 200  # and was not spent by the attempt


async def test_concurrent_consumption_of_one_reset_link_succeeds_once(
    queue_and_app: tuple[FakeQueue, FastAPI],
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    await forgot(app, email)
    token = reset_mails(queue, email)[0]
    passwords = [f"{NEW} {i}" for i in range(6)]
    results = await asyncio.gather(*(reset(app, token, p) for p in passwords))
    assert sorted(r.status_code for r in results) == [204, 401, 401, 401, 401, 401]
    logins = [(await login(app, email, p)).status_code for p in passwords]
    assert logins.count(200) == 1  # exactly one of the racing passwords won


async def test_reset_gives_a_google_account_its_first_password_without_touching_its_identity(
    queue_and_app: tuple[FakeQueue, FastAPI], make_google_token: MakeToken, engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email, sub = unique_email(), "s-" + uuid4().hex
    google = await client_for(app).post(
        "/api/auth/google", json={"credential": make_google_token(sub=sub, email=email)}
    )
    uid = google.json()["id"]
    assert (await login(app, email, GOOD)).status_code == 401  # no password yet
    await forgot(app, email)
    assert (await reset(app, reset_mails(queue, email)[0])).status_code == 204
    me = await login(app, email, NEW)
    assert me.status_code == 200
    assert me.json()["id"] == uid  # the same account, not a second one
    again = await client_for(app).post(
        "/api/auth/google", json={"credential": make_google_token(sub=sub, email=email)}
    )
    assert again.json()["id"] == uid  # Google still signs in
    async with async_sessionmaker(engine)() as s:
        assert await s.scalar(select(func.count()).select_from(User).where(User.email == email)) == 1


# ------------------------------------------------------------------------------ change
async def test_change_requires_the_current_password_and_signs_every_session_out(
    queue_and_app: tuple[FakeQueue, FastAPI], engine: AsyncEngine
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    a, b = client_for(app), client_for(app)
    for c in (a, b):
        assert (await c.post("/api/auth/login", json={"email": email, "password": GOOD})).status_code == 200

    wrong = await a.post(
        "/api/auth/password/change", json={"current_password": "not it at all 1", "new_password": NEW}
    )
    assert (wrong.status_code, wrong.json()["code"]) == (401, "INVALID_CREDENTIALS")
    weak = await a.post(
        "/api/auth/password/change", json={"current_password": GOOD, "new_password": "1234567890"}
    )
    assert (weak.status_code, weak.json()["reason"]) == (422, "common")
    assert (await a.get("/api/me")).status_code == 200  # failures sign nobody out

    ok = await a.post("/api/auth/password/change", json={"current_password": GOOD, "new_password": NEW})
    assert ok.status_code == 204
    assert "rm_session" in ok.headers.get("set-cookie", "")  # the cookie is cleared
    assert (await a.get("/api/me")).status_code == 401
    assert (await b.get("/api/me")).status_code == 401  # other browsers too, cache included
    assert (await login(app, email, GOOD)).status_code == 401
    assert (await login(app, email, NEW)).status_code == 200
    async with async_sessionmaker(engine)() as s:
        stored = await s.scalar(
            select(UserCredential.password_hash)
            .join(User, User.id == UserCredential.user_id)
            .where(User.email == email)
        )
    assert stored is not None
    assert stored.startswith("$argon2id$")


async def test_change_needs_a_session_and_a_password_to_change(
    queue_and_app: tuple[FakeQueue, FastAPI], make_google_token: MakeToken
) -> None:
    _, app = queue_and_app
    body = {"current_password": GOOD, "new_password": NEW}
    assert (await client_for(app).post("/api/auth/password/change", json=body)).status_code == 401
    google = client_for(app)
    await google.post(
        "/api/auth/google",
        json={"credential": make_google_token(sub="s-" + uuid4().hex, email=unique_email())},
    )
    r = await google.post(
        "/api/auth/password/change", json=body
    )  # a Google-only account must recover instead
    assert (r.status_code, r.json()["code"]) == (401, "INVALID_CREDENTIALS")


async def test_no_password_or_token_reaches_the_logs(
    queue_and_app: tuple[FakeQueue, FastAPI], caplog: pytest.LogCaptureFixture
) -> None:
    queue, app = queue_and_app
    email, _ = await make_user(queue, app)
    caplog.set_level(logging.DEBUG)
    await forgot(app, email)
    token = reset_mails(queue, email)[0]
    secret = "recovery passphrase nobody logs 5521"
    await reset(app, token, secret)
    assert secret not in caplog.text
    assert token not in caplog.text
