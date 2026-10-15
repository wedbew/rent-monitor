"""Google and magic-link sign-in, sessions and revocation on real Postgres (blueprint §2 Auth decision, §4.6).

Named tests from the blueprint: test_google_token_validation, test_google_signup_gets_credits,
test_google_links_existing_email (with the unverified and magic-link cases), and gate 7
(test_sign_out_everywhere_evicts_cached_sessions_in_all_processes).
"""

import asyncio
import contextlib
import hashlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from httpx import ASGITransport, AsyncClient
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_core.db.models import CreditAccount, CreditLedger, LoginToken, RateLimit, User, UserSession
from rm_core.privacy import purge_expired
from rm_core.settings import Settings
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]
ORIGIN = "https://app.test"
MakeToken = Callable[..., str]


class FakeQueue:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.auth_mail: list[tuple[str, str, str | None]] = []
        self.billing_kicks = 0

    async def send_magic_link(self, *, email: str, url: str) -> None:
        self.sent.append((email, url))

    async def send_auth_mail(self, *, kind: str, email: str, url: str | None) -> None:
        self.auth_mail.append((kind, email, url))

    async def process_billing_events(self) -> None:
        self.billing_kicks += 1


class FakeCerts:
    def __init__(self, certs: Mapping[str, str]) -> None:
        self.certs = dict(certs)
        self.available = True

    async def get(self, *, refresh: bool = False) -> Mapping[str, str]:
        from rm_api.auth.google import GoogleUnavailable  # noqa: PLC0415

        if not self.available:
            raise GoogleUnavailable("down")
        return self.certs


async def wait_until(check: Callable[[], Awaitable[bool]], within: float) -> float:
    """Poll `check` until it is true; return the seconds it took. Used where the effect crosses processes."""
    started = time.monotonic()
    while not await check():
        if time.monotonic() - started > within:
            raise AssertionError(f"condition not met within {within}s")
        await asyncio.sleep(0.01)
    return time.monotonic() - started


def unique_email() -> str:
    return f"user-{uuid4().hex[:12]}@gmail.com"  # Google is authoritative for gmail.com (D-13)


def unique_ip() -> str:
    n = uuid4().int
    return f"198.51.{n % 250}.{(n >> 8) % 250 + 1}"


@asynccontextmanager
async def running(
    migrated_url: str,
    keys: GoogleKeys,
    queue: FakeQueue | None = None,
    *,
    env: str = "test",
    certs: FakeCerts | None = None,
) -> AsyncIterator[FastAPI]:
    settings = Settings(
        app_env="production" if env == "production" else "test",
        database_url=migrated_url,
        public_app_url=ORIGIN,
        google_client_id=GOOGLE_AUDIENCE,
    )
    verifier = GoogleVerifier(GOOGLE_AUDIENCE, certs or FakeCerts(keys.certs))
    app = create_app(settings, email_queue=queue or FakeQueue(), google_verifier=verifier)
    async with LifespanManager(app):
        listener = app.state.notify_listener
        await asyncio.wait_for(listener.listening.wait(), 10)
        yield app


class Browser(AsyncClient):
    """A test browser usable first and put in `async with` later (httpx forbids re-entering a client)."""

    async def __aenter__(self) -> "Browser":
        with contextlib.suppress(RuntimeError):  # already opened by an earlier request
            await super().__aenter__()
        return self


def client_for(app: FastAPI, ip: str | None = None, *, origin: str | None = ORIGIN) -> Browser:
    headers = {"Origin": origin} if origin else {}
    return Browser(
        transport=ASGITransport(app=app, raise_app_exceptions=False, client=(ip or unique_ip(), 5000)),
        base_url=ORIGIN,
        headers=headers,
    )


@pytest.fixture
async def app(migrated_url: str, google_keys: GoogleKeys) -> AsyncIterator[FastAPI]:
    async with running(migrated_url, google_keys) as application:
        yield application


@pytest.fixture
async def http(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(app) as c:
        yield c


async def user_count(engine: AsyncEngine, email: str) -> int:
    async with engine.connect() as conn:
        return int(await conn.scalar(select(func.count()).select_from(User).where(User.email == email)) or 0)


async def identities(engine: AsyncEngine, email: str) -> list[tuple[str, str]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT i.provider, i.subject FROM app.auth_identity i "
                "JOIN app.app_user u ON u.id = i.user_id "
                "WHERE u.email = :e ORDER BY i.provider, i.subject"
            ),
            {"e": email},
        )
        return [(r[0], r[1]) for r in rows]


async def credit_balance(engine: AsyncEngine, email: str) -> int | None:
    async with engine.connect() as conn:
        return await conn.scalar(
            select(CreditAccount.balance)
            .join(User, User.id == CreditAccount.user_id)
            .where(User.email == email)
        )


# ---------- Google: test_google_token_validation ----------
async def test_google_token_validation_a_valid_token_creates_one_user_one_identity_one_session(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email, sub = unique_email(), f"sub-{uuid4().hex}"
    r = await http.post("/api/auth/google", json={"credential": make_google_token(sub=sub, email=email)})
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == email
    assert me["email_verified"] is True
    assert me["role"] == "user"
    assert await user_count(engine, email) == 1
    assert await identities(engine, email) == [("google", sub)]
    async with engine.connect() as conn:
        sessions = await conn.scalar(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == me["id"])
        )
    assert sessions == 1


@pytest.mark.parametrize(
    "bad",
    [
        {"aud": "another-client"},
        {"exp_in": -3600},
        {"iss": "https://evil.example.test"},
        {"signer": "other"},
    ],
)
async def test_google_token_validation_bad_tokens_are_401_and_create_nothing(
    http: AsyncClient,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    google_keys: GoogleKeys,
    bad: dict[str, object],
) -> None:
    email = unique_email()
    kwargs: dict[str, object] = dict(bad)
    if kwargs.get("signer") == "other":
        kwargs["signer"] = google_keys.other_signer
    r = await http.post("/api/auth/google", json={"credential": make_google_token(email=email, **kwargs)})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_GOOGLE_TOKEN"
    assert await user_count(engine, email) == 0
    assert "set-cookie" not in r.headers


async def test_google_credential_must_be_a_bounded_string(http: AsyncClient) -> None:
    for body in ({}, {"credential": ""}, {"credential": "x" * 5000}, {"credential": "x" * 30, "extra": 1}):
        r = await http.post("/api/auth/google", json=body)
        assert r.status_code == 422
        assert r.json()["code"] == "VALIDATION_ERROR"


async def test_google_unverified_email_is_rejected_and_creates_nothing(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email = unique_email()
    r = await http.post(
        "/api/auth/google", json={"credential": make_google_token(email=email, email_verified=False)}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "GOOGLE_EMAIL_UNVERIFIED"
    assert await user_count(engine, email) == 0


async def test_google_without_a_client_id_or_certificates_is_503_not_401(
    migrated_url: str, google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    certs = FakeCerts(google_keys.certs)
    certs.available = False
    async with running(migrated_url, google_keys, certs=certs) as application, client_for(application) as c:
        r = await c.post("/api/auth/google", json={"credential": make_google_token()})
    assert r.status_code == 503


# ---------- Google: test_google_signup_gets_credits ----------
async def test_google_signup_gets_credits_exactly_once(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email, sub = unique_email(), f"sub-{uuid4().hex}"
    token = make_google_token(sub=sub, email=email)
    me = None
    for _ in range(3):  # signing in again must not grant again
        r = await http.post("/api/auth/google", json={"credential": token})
        assert r.status_code == 200
        me = r.json()
    assert me is not None
    assert await credit_balance(engine, email) == 3
    async with engine.connect() as conn:
        grants = await conn.scalar(
            select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == me["id"])
        )
    assert grants == 1


async def test_concurrent_first_google_sign_ins_create_one_user_and_one_grant(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email, sub = unique_email(), f"sub-{uuid4().hex}"
    token = make_google_token(sub=sub, email=email)

    async def attempt() -> int:
        async with client_for(app) as c:
            return (await c.post("/api/auth/google", json={"credential": token})).status_code

    statuses = await asyncio.gather(*(attempt() for _ in range(8)))
    assert statuses == [200] * 8
    assert await user_count(engine, email) == 1
    assert await identities(engine, email) == [("google", sub)]
    assert await credit_balance(engine, email) == 3


# ---------- linking: test_google_links_existing_email ----------
async def magic_sign_in(app: FastAPI, queue: FakeQueue, email: str) -> Browser:
    c = client_for(app)
    assert (await c.post("/api/auth/email/start", json={"email": email})).status_code == 204
    token = queue.sent[-1][1].split("#t=")[1]
    assert (await c.post("/api/auth/email/verify", json={"token": token})).status_code == 200
    return c


async def test_google_links_existing_magic_link_user_on_a_verified_email(
    migrated_url: str, google_keys: GoogleKeys, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    queue, email, sub = FakeQueue(), unique_email(), f"sub-{uuid4().hex}"
    async with running(migrated_url, google_keys, queue) as application:
        magic = await magic_sign_in(application, queue, email)
        try:
            first = (await magic.get("/api/auth/sessions")).status_code
        finally:
            await magic.aclose()
        async with client_for(application) as g:
            r = await g.post("/api/auth/google", json={"credential": make_google_token(sub=sub, email=email)})
    assert first == 200
    assert r.status_code == 200
    assert await user_count(engine, email) == 1
    assert await identities(engine, email) == [("email", email), ("google", sub)]
    assert await credit_balance(engine, email) == 3  # one grant across both identities


async def test_an_unverified_google_email_never_links_to_an_existing_user(
    migrated_url: str, google_keys: GoogleKeys, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    queue, email = FakeQueue(), unique_email()
    async with running(migrated_url, google_keys, queue) as application:
        await (await magic_sign_in(application, queue, email)).aclose()
        async with client_for(application) as g:
            r = await g.post(
                "/api/auth/google",
                json={
                    "credential": make_google_token(
                        sub=f"sub-{uuid4().hex}", email=email, email_verified=False
                    )
                },
            )
    assert r.status_code == 401
    assert await identities(engine, email) == [("email", email)]


async def test_google_first_then_magic_link_is_the_same_user(
    migrated_url: str, google_keys: GoogleKeys, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    queue, email, sub = FakeQueue(), unique_email(), f"sub-{uuid4().hex}"
    async with running(migrated_url, google_keys, queue) as application:
        async with client_for(application) as g:
            await g.post("/api/auth/google", json={"credential": make_google_token(sub=sub, email=email)})
        await (await magic_sign_in(application, queue, email)).aclose()
    assert await user_count(engine, email) == 1
    assert await identities(engine, email) == [("email", email), ("google", sub)]
    assert await credit_balance(engine, email) == 3


async def test_a_returning_google_user_is_found_by_sub_even_if_the_email_changed(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    sub, old, new = f"sub-{uuid4().hex}", unique_email(), unique_email()
    first = (
        await http.post("/api/auth/google", json={"credential": make_google_token(sub=sub, email=old)})
    ).json()
    second = (
        await http.post("/api/auth/google", json={"credential": make_google_token(sub=sub, email=new)})
    ).json()
    assert second["id"] == first["id"]
    assert await user_count(engine, new) == 0  # identity is the sub, never the email


async def test_an_unsafe_avatar_url_is_not_stored(http: AsyncClient, make_google_token: MakeToken) -> None:
    for picture in (
        "javascript:alert(1)",
        "http://insecure.example.test/a.png",
        "data:image/png;base64,AAAA",
    ):
        me = (
            await http.post(
                "/api/auth/google",
                json={
                    "credential": make_google_token(
                        sub=f"sub-{uuid4().hex}", email=unique_email(), picture=picture
                    )
                },
            )
        ).json()
        assert me["avatar_url"] is None


# ---------- magic link ----------
async def test_magic_link_start_is_204_for_known_and_unknown_addresses_and_stores_only_a_hash(
    app: FastAPI, engine: AsyncEngine
) -> None:
    queue: FakeQueue = app.state.email_queue
    known, unknown = unique_email(), unique_email()
    async with client_for(app) as c:
        await c.post("/api/auth/google", json={"credential": "x" * 30})  # noise, ignored
        a = await c.post("/api/auth/email/start", json={"email": known})
        b = await c.post("/api/auth/email/start", json={"email": unknown})
    assert a.status_code == b.status_code == 204
    assert a.content == b.content == b""
    assert {e for e, _ in queue.sent} == {known, unknown}
    email, url = queue.sent[0]
    assert url.startswith(f"{ORIGIN}/login/email#t=")  # a fragment: never sent to servers or proxies
    token = url.split("#t=")[1]
    async with engine.connect() as conn:
        row = (await conn.execute(select(LoginToken).where(LoginToken.email == email))).one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash
    assert row.used_at is None
    assert timedelta(minutes=29) < row.expires_at - datetime.now(UTC) <= timedelta(minutes=30)


async def test_magic_link_signs_in_once_and_grants_the_free_credits(
    app: FastAPI, engine: AsyncEngine
) -> None:
    queue: FakeQueue = app.state.email_queue
    email = unique_email()
    async with client_for(app) as c:
        await c.post("/api/auth/email/start", json={"email": email.upper()})
        token = queue.sent[-1][1].split("#t=")[1]
        first = await c.post("/api/auth/email/verify", json={"token": token})
        assert first.status_code == 200
        assert first.json()["email"] == email  # lower-cased
        assert first.json()["email_verified"] is True
        assert "httponly" in first.headers["set-cookie"].lower()
        assert (await c.get("/api/auth/sessions")).status_code == 200
    async with client_for(app) as other:
        second = await other.post("/api/auth/email/verify", json={"token": token})
    assert second.status_code == 401
    assert second.json()["code"] == "MAGIC_LINK_INVALID"
    assert await credit_balance(engine, email) == 3


async def test_an_expired_magic_link_is_rejected(app: FastAPI, engine: AsyncEngine) -> None:
    queue: FakeQueue = app.state.email_queue
    email = unique_email()
    async with client_for(app) as c:
        await c.post("/api/auth/email/start", json={"email": email})
        token = queue.sent[-1][1].split("#t=")[1]
        async with engine.begin() as conn:
            await conn.execute(
                update(LoginToken)
                .where(LoginToken.email == email)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        r = await c.post("/api/auth/email/verify", json={"token": token})
    assert r.status_code == 401
    assert await user_count(engine, email) == 0


@pytest.mark.parametrize("token", ["", "short", "has space " * 4, "x" * 200, "a/b+c=" * 8])
async def test_malformed_magic_tokens_are_validation_errors(http: AsyncClient, token: str) -> None:
    assert (await http.post("/api/auth/email/verify", json={"token": token})).status_code == 422


async def test_a_wrong_but_well_formed_token_is_401(http: AsyncClient) -> None:
    r = await http.post("/api/auth/email/verify", json={"token": "A" * 43})
    assert r.status_code == 401
    assert r.json()["code"] == "MAGIC_LINK_INVALID"


@pytest.mark.parametrize(
    "email", ["", "no-at-sign", "a b@c.pl", "a@b", "<x>@y.pl", "a@b..pl", "x" * 300 + "@y.pl"]
)
async def test_invalid_email_addresses_are_validation_errors_and_send_nothing(
    app: FastAPI, http: AsyncClient, email: str
) -> None:
    r = await http.post("/api/auth/email/start", json={"email": email})
    assert r.status_code == 422
    assert app.state.email_queue.sent == []


async def test_concurrent_verify_of_one_magic_link_signs_in_exactly_once(
    app: FastAPI, engine: AsyncEngine
) -> None:
    queue: FakeQueue = app.state.email_queue
    email = unique_email()
    async with client_for(app) as c:
        await c.post("/api/auth/email/start", json={"email": email})
    token = queue.sent[-1][1].split("#t=")[1]

    async def attempt() -> int:
        async with client_for(app) as c:
            return (await c.post("/api/auth/email/verify", json={"token": token})).status_code

    statuses = await asyncio.gather(*(attempt() for _ in range(10)))
    assert sorted(statuses) == [200] + [401] * 9
    assert await user_count(engine, email) == 1
    assert await credit_balance(engine, email) == 3


async def test_the_per_address_limit_is_exactly_five_per_hour_even_under_concurrency(app: FastAPI) -> None:
    queue: FakeQueue = app.state.email_queue
    email = unique_email()

    async def attempt() -> httpx.Response:
        async with client_for(app) as c:  # a fresh IP each time, so only the address limit can trigger
            return await c.post("/api/auth/email/start", json={"email": email})

    responses = await asyncio.gather(*(attempt() for _ in range(15)))
    codes = [r.status_code for r in responses]
    assert codes.count(204) == 5
    assert codes.count(429) == 10
    assert len(queue.sent) == 5
    limited = next(r for r in responses if r.status_code == 429)
    assert limited.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(limited.headers["retry-after"]) <= 3600


async def test_the_per_ip_limit_is_twenty_per_hour(app: FastAPI) -> None:
    ip = unique_ip()
    async with client_for(app, ip) as c:
        codes = [
            (await c.post("/api/auth/email/start", json={"email": unique_email()})).status_code
            for _ in range(23)
        ]
    assert codes.count(204) == 20
    assert codes[-3:] == [429, 429, 429]


async def test_rate_limit_rows_hold_hashes_not_addresses_and_are_purged(
    app: FastAPI, engine: AsyncEngine
) -> None:
    email = unique_email()
    async with client_for(app) as c:
        await c.post("/api/auth/email/start", json={"email": email})
    async with engine.connect() as conn:
        keys = [r[0] for r in await conn.execute(select(RateLimit.key))]
    assert all(len(k) == 64 and "@" not in k for k in keys)
    stale = "f" * 64
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO app.rate_limit (key, window_start, n) VALUES (:k, now() - interval '3 days', 4)"
            ),
            {"k": stale},
        )
    report = await purge_expired(async_sessionmaker(engine), Settings())
    assert report.rate_limit >= 1
    async with engine.connect() as conn:
        assert (
            await conn.scalar(select(func.count()).select_from(RateLimit).where(RateLimit.key == stale)) == 0
        )


# ---------- sessions ----------
async def google_session(
    app: FastAPI, make_token: MakeToken, **claims: object
) -> tuple[Browser, dict[str, str]]:
    c = client_for(app)
    r = await c.post("/api/auth/google", json={"credential": make_token(**claims)})
    assert r.status_code == 200
    return c, r.json()


async def test_the_session_cookie_holds_a_random_token_and_the_database_only_its_hash(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await google_session(app, make_google_token, sub=f"s-{uuid4().hex}", email=unique_email())
    async with c:
        raw = c.cookies["rm_session"]
    async with engine.connect() as conn:
        stored = (
            (await conn.execute(select(UserSession.token_hash).where(UserSession.user_id == me["id"])))
            .scalars()
            .all()
        )
    assert stored == [hashlib.sha256(raw.encode()).hexdigest()]
    assert raw not in stored[0]
    assert len(raw) >= 43


async def test_production_sets_the_host_prefixed_secure_cookie(
    migrated_url: str, google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    async with (
        running(migrated_url, google_keys, env="production") as application,
        client_for(application) as c,
    ):
        r = await c.post(
            "/api/auth/google",
            json={"credential": make_google_token(sub=f"s-{uuid4().hex}", email=unique_email())},
        )
    header = r.headers["set-cookie"].lower()
    assert header.startswith("__host-rm_session=")
    assert all(a in header for a in ("httponly", "secure", "samesite=lax", "path=/"))
    assert "domain=" not in header


async def test_requests_without_or_with_a_bad_session_are_401(app: FastAPI) -> None:
    async with client_for(app) as c:
        none = await c.get("/api/auth/sessions")
        c.cookies.set("rm_session", "A" * 43)
        bad = await c.get("/api/auth/sessions")
        c.cookies.set("rm_session", "A" * 500)
        huge = await c.get("/api/auth/sessions")
    for r in (none, bad, huge):
        assert r.status_code == 401
        assert r.json()["code"] == "UNAUTHENTICATED"


async def test_an_expired_session_is_refused(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await google_session(app, make_google_token, sub=f"s-{uuid4().hex}", email=unique_email())
    async with engine.begin() as conn:
        await conn.execute(
            update(UserSession)
            .where(UserSession.user_id == me["id"])
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    app.state.principal_cache.clear()
    async with c:
        assert (await c.get("/api/auth/sessions")).status_code == 401


async def test_an_active_session_slides_its_expiry_at_most_once_a_day(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await google_session(app, make_google_token, sub=f"s-{uuid4().hex}", email=unique_email())

    async def expiry() -> datetime:
        async with engine.connect() as conn:
            return (
                await conn.execute(select(UserSession.expires_at).where(UserSession.user_id == me["id"]))
            ).scalar_one()

    async with c:
        original = await expiry()
        app.state.principal_cache.clear()
        await c.get("/api/auth/sessions")
        assert await expiry() == original  # seen moments ago: no write
        async with engine.begin() as conn:
            await conn.execute(
                update(UserSession)
                .where(UserSession.user_id == me["id"])
                .values(
                    last_seen_at=datetime.now(UTC) - timedelta(days=2),
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
        app.state.principal_cache.clear()
        await c.get("/api/auth/sessions")
    assert await expiry() > datetime.now(UTC) + timedelta(days=29)


async def test_sign_out_revokes_the_session_and_is_idempotent(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await google_session(app, make_google_token, sub=f"s-{uuid4().hex}", email=unique_email())
    async with c:
        raw = c.cookies["rm_session"]
        assert (await c.get("/api/auth/sessions")).status_code == 200
        out = await c.post("/api/auth/signout")
        assert out.status_code == 204
        assert "max-age=0" in out.headers["set-cookie"].lower()
        c.cookies.set("rm_session", raw)  # replay the old cookie: the server must refuse it
        assert (await c.get("/api/auth/sessions")).status_code == 401
        assert (await c.post("/api/auth/signout")).status_code == 204
    async with engine.connect() as conn:
        assert (
            await conn.scalar(
                select(func.count()).select_from(UserSession).where(UserSession.user_id == me["id"])
            )
            == 0
        )


async def test_the_session_list_marks_the_current_browser_and_hides_other_users(
    app: FastAPI, make_google_token: MakeToken
) -> None:
    a, me_a = await google_session(app, make_google_token, sub=f"a-{uuid4().hex}", email=unique_email())
    b, me_b = await google_session(app, make_google_token, sub=f"b-{uuid4().hex}", email=unique_email())
    async with a, b:
        rows_a = (await a.get("/api/auth/sessions")).json()
        rows_b = (await b.get("/api/auth/sessions")).json()
    assert me_a["id"] != me_b["id"]
    assert [r["current"] for r in rows_a] == [True]
    assert [r["current"] for r in rows_b] == [True]
    assert {r["id"] for r in rows_a}.isdisjoint({r["id"] for r in rows_b})


async def test_sign_out_everywhere_ends_all_my_sessions_and_nobody_elses(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email = unique_email()
    sub = f"s-{uuid4().hex}"
    laptop, me = await google_session(app, make_google_token, sub=sub, email=email)
    phone, _ = await google_session(app, make_google_token, sub=sub, email=email)
    stranger, other = await google_session(
        app, make_google_token, sub=f"s-{uuid4().hex}", email=unique_email()
    )
    async with laptop, phone, stranger:
        assert len((await laptop.get("/api/auth/sessions")).json()) == 2
        assert (await laptop.post("/api/auth/signout-all")).status_code == 204

        async def phone_is_out() -> bool:
            return (await phone.get("/api/auth/sessions")).status_code == 401

        await wait_until(phone_is_out, within=1.0)
        assert (await stranger.get("/api/auth/sessions")).status_code == 200
    async with engine.connect() as conn:
        left = await conn.scalar(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == other["id"])
        )
        gone = await conn.scalar(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == me["id"])
        )
    assert (left, gone) == (1, 0)


async def test_sign_out_everywhere_evicts_cached_sessions_in_all_processes(
    migrated_url: str, google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    """Release gate 7: signing out everywhere via process A is seen by a process B that cached the principal,
    within one second."""
    sub, email = f"s-{uuid4().hex}", unique_email()
    async with (
        running(migrated_url, google_keys) as proc_a,
        running(migrated_url, google_keys) as proc_b,
        client_for(proc_a) as via_a,
        client_for(proc_b) as via_b,
    ):
        token = make_google_token(sub=sub, email=email)
        await via_a.post("/api/auth/google", json={"credential": token})
        via_b.cookies.set("rm_session", via_a.cookies["rm_session"])
        assert (await via_b.get("/api/auth/sessions")).status_code == 200
        assert len(proc_b.state.principal_cache) == 1  # B now trusts its cache, not the database
        assert (await via_a.post("/api/auth/signout-all")).status_code == 204

        async def b_refuses() -> bool:
            return (await via_b.get("/api/auth/sessions")).status_code == 401

        elapsed = await wait_until(b_refuses, within=3.0)
    assert elapsed < 1.0, f"revocation took {elapsed:.2f}s"


async def test_a_dropped_listener_connection_flushes_the_cache_on_reconnect(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await google_session(app, make_google_token, sub=f"s-{uuid4().hex}", email=unique_email())
    async with c:
        await c.get("/api/auth/sessions")
        assert len(app.state.principal_cache) >= 1
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE query LIKE 'LISTEN%' AND pid <> pg_backend_pid()"
                )
            )

        async def cache_flushed() -> bool:
            return len(app.state.principal_cache) == 0  # missed notifications must not leave stale sessions

        await wait_until(cache_flushed, within=8.0)
        await asyncio.wait_for(app.state.notify_listener.listening.wait(), 8)


# ---------- Origin ----------
async def test_unsafe_requests_need_the_configured_origin(app: FastAPI) -> None:
    async with client_for(app, origin=None) as no_origin, client_for(app, origin="https://evil.test") as evil:
        for c in (no_origin, evil):
            r = await c.post("/api/auth/email/start", json={"email": unique_email()})
            assert r.status_code == 403
            assert r.json()["code"] == "ORIGIN_NOT_ALLOWED"
        assert (
            await no_origin.get("/api/auth/sessions")
        ).status_code == 401  # GET needs no origin, only a session
    assert app.state.email_queue.sent == []


# ---------- the real job queue ----------
async def test_the_email_queue_defers_a_job_by_task_name(
    migrated_url: str, procrastinate_schema: None, engine: AsyncEngine
) -> None:
    import procrastinate  # noqa: PLC0415
    from rm_api.queue import ProcrastinateEmailQueue  # noqa: PLC0415

    dsn = migrated_url.replace("postgresql+psycopg://", "postgresql://", 1)
    jobs = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=dsn, min_size=1, max_size=2))
    email = unique_email()
    await jobs.open_async()
    try:
        await ProcrastinateEmailQueue(jobs).send_magic_link(email=email, url=f"{ORIGIN}/login/email#t=abc")
    finally:
        await jobs.close_async()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT task_name, queue_name, args FROM procrastinate_jobs WHERE args->>'email' = :e"),
                {"e": email},
            )
        ).one()
        await conn.execute(text("DELETE FROM procrastinate_jobs WHERE args->>'email' = :e"), {"e": email})
        await conn.commit()
    assert row.task_name == "rm_worker.tasks.email.send_magic_link"
    assert row.queue_name == "ops"
    assert row.args["url"].endswith("#t=abc")


# ---------- D-13: Google must be authoritative for the address (ADR 0010) ----------
def other_domain_email() -> str:
    return f"user-{uuid4().hex[:12]}@company.example"


async def count_all(engine: AsyncEngine, email: str) -> tuple[int, int, int | None]:
    async with engine.connect() as conn:
        sessions = await conn.scalar(
            text(
                "SELECT count(*) FROM app.user_session s JOIN app.app_user u ON u.id = s.user_id "
                "WHERE u.email = :e"
            ),
            {"e": email},
        )
    return await user_count(engine, email), int(sessions or 0), await credit_balance(engine, email)


async def test_a_non_gmail_address_without_hd_creates_nothing_and_asks_for_the_magic_link(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email = other_domain_email()
    r = await http.post("/api/auth/google", json={"credential": make_google_token(email=email)})
    assert r.status_code == 401
    assert r.json()["code"] == "EMAIL_CONFIRMATION_REQUIRED"
    assert "set-cookie" not in r.headers
    assert await count_all(engine, email) == (0, 0, None)  # no user, no session, no credits


async def test_a_non_gmail_address_never_links_to_an_existing_magic_link_account(
    migrated_url: str, google_keys: GoogleKeys, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    queue, email = FakeQueue(), other_domain_email()
    async with running(migrated_url, google_keys, queue) as application:
        await (await magic_sign_in(application, queue, email)).aclose()
        async with client_for(application) as g:
            r = await g.post(
                "/api/auth/google",
                json={"credential": make_google_token(sub=f"s-{uuid4().hex}", email=email)},
            )
    assert r.status_code == 401
    assert r.json()["code"] == "EMAIL_CONFIRMATION_REQUIRED"
    assert await identities(engine, email) == [
        ("email", email)
    ]  # the attacker's Google identity did not attach


async def test_a_workspace_account_whose_hd_matches_the_address_domain_is_trusted(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    email, sub = other_domain_email(), f"s-{uuid4().hex}"
    r = await http.post(
        "/api/auth/google",
        json={"credential": make_google_token(sub=sub, email=email, extra={"hd": "company.example"})},
    )
    assert r.status_code == 200
    assert await identities(engine, email) == [("google", sub)]
    assert await credit_balance(engine, email) == 3


async def test_a_workspace_account_links_to_an_existing_magic_link_user(
    migrated_url: str, google_keys: GoogleKeys, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    queue, email, sub = FakeQueue(), other_domain_email(), f"s-{uuid4().hex}"
    async with running(migrated_url, google_keys, queue) as application:
        await (await magic_sign_in(application, queue, email)).aclose()
        async with client_for(application) as g:
            r = await g.post(
                "/api/auth/google",
                json={"credential": make_google_token(sub=sub, email=email, extra={"hd": "COMPANY.example"})},
            )
    assert r.status_code == 200
    assert await user_count(engine, email) == 1
    assert await identities(engine, email) == [("email", email), ("google", sub)]


@pytest.mark.parametrize("hd", ["evil.example", "company.example.evil.test", "", "mail.company.example"])
async def test_an_hd_that_differs_from_the_address_domain_is_not_trusted(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken, hd: str
) -> None:
    email = other_domain_email()
    r = await http.post(
        "/api/auth/google", json={"credential": make_google_token(email=email, extra={"hd": hd})}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "EMAIL_CONFIRMATION_REQUIRED"
    assert await user_count(engine, email) == 0


@pytest.mark.parametrize("domain", ["googlemail.com", "gmail.com.evil.test", "notgmail.com", "gmail.co"])
async def test_only_exactly_gmail_com_counts_as_gmail(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken, domain: str
) -> None:
    email = f"user-{uuid4().hex[:10]}@{domain}"
    r = await http.post("/api/auth/google", json={"credential": make_google_token(email=email)})
    assert r.status_code == 401
    assert await user_count(engine, email) == 0


async def test_gmail_is_matched_case_insensitively(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    local = f"user-{uuid4().hex[:10]}"
    r = await http.post(
        "/api/auth/google", json={"credential": make_google_token(email=f"{local}@GMail.COM")}
    )
    assert r.status_code == 200
    assert await user_count(engine, f"{local}@gmail.com") == 1


async def test_a_returning_google_user_still_signs_in_when_a_later_token_has_no_hd(
    http: AsyncClient, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    """Identity is the sub: once linked (while Google was authoritative), the user is never locked out."""
    email, sub = other_domain_email(), f"s-{uuid4().hex}"
    first = await http.post(
        "/api/auth/google",
        json={"credential": make_google_token(sub=sub, email=email, extra={"hd": "company.example"})},
    )
    again = await http.post("/api/auth/google", json={"credential": make_google_token(sub=sub, email=email)})
    assert first.status_code == again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
