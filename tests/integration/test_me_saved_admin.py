"""`/api/me`, `/api/saved` and `/api/admin/*` on real Postgres.

Covers tenant isolation, admin-only access and idempotent credit adjustments.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from rm_api import saved as saved_module
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_core.db.models import (
    Audit,
    AuditStatus,
    ChargeSource,
    ChargeState,
    CreditAccount,
    CreditLedger,
    FeatureFlag,
    Listing,
    Plan,
    UsagePeriod,
    User,
)
from rm_core.ledger import ledger_mismatches
from rm_core.settings import Settings
from rm_core.throttle import OTODOM_HOST, trip_breaker
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import Browser, FakeCerts, FakeQueue, client_for, unique_email

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]


@pytest.fixture
async def app(migrated_url: str, google_keys: GoogleKeys) -> AsyncIterator[FastAPI]:
    settings = Settings(
        app_env="test",
        database_url=migrated_url,
        public_app_url="https://app.test",
        google_client_id=GOOGLE_AUDIENCE,
    )
    verifier = GoogleVerifier(GOOGLE_AUDIENCE, FakeCerts(google_keys.certs))
    application = create_app(settings, email_queue=FakeQueue(), google_verifier=verifier)
    async with LifespanManager(application):
        await asyncio.wait_for(application.state.notify_listener.listening.wait(), 10)
        yield application


async def sign_in(app: FastAPI, make_token: MakeToken) -> tuple[Browser, dict[str, str]]:
    c = client_for(app)
    r = await c.post(
        "/api/auth/google", json={"credential": make_token(sub=f"s-{uuid4().hex}", email=unique_email())}
    )
    assert r.status_code == 200
    return c, r.json()


async def make_admin(
    app: FastAPI, engine: AsyncEngine, make_token: MakeToken
) -> tuple[Browser, dict[str, str]]:
    c, me = await sign_in(app, make_token)
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.id == me["id"]).values(role="admin"))
    app.state.principal_cache.clear()  # the role is part of the cached principal
    return c, me


@pytest.fixture
async def plans(engine: AsyncEngine) -> AsyncIterator[None]:
    """Flags reference `plan.code`; the test DB is not seeded: create what is missing, remove only that."""
    created: list[str] = []
    async with async_sessionmaker(engine)() as s, s.begin():
        for code in ("free", "pro"):
            if await s.get(Plan, code) is None:
                s.add(Plan(code=code))
                created.append(code)
    try:
        yield
    finally:
        async with async_sessionmaker(engine)() as s, s.begin():
            for code in created:
                await s.execute(text("DELETE FROM app.plan WHERE code = :c"), {"c": code})


def new_oid() -> str:
    return "ID" + uuid4().hex[:8].upper()


async def audit_listing(engine: AsyncEngine, user_id: str, oid: str, *, age_s: int = 0) -> str:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    audit_id = uuid4()
    async with sm() as s, s.begin():
        if await s.get(Listing, oid) is None:
            s.add(Listing(otodom_id=oid, url="https://x.test"))
            await s.flush()
        s.add(
            Audit(
                id=audit_id,
                user_id=user_id,
                otodom_id=oid,
                status=AuditStatus.succeeded,
                charge_source=ChargeSource.credit,
                charge_state=ChargeState.captured,
                engine_version="t",
                schema_version=1,
                created_at=datetime.now(UTC) - timedelta(seconds=age_s),
            )
        )
    return str(audit_id)


# ---------- /api/me ----------
async def test_me_needs_a_session(app: FastAPI) -> None:
    async with client_for(app) as c:
        assert (await c.get("/api/me")).status_code == 401


async def test_me_reports_profile_plan_credits_flags_and_upstream_state(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, plans: None
) -> None:
    c, me = await sign_in(app, make_google_token)
    key_on, key_pro = f"t_on_{uuid4().hex[:6]}", f"t_pro_{uuid4().hex[:6]}"
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s, s.begin():
        s.add(FeatureFlag(key=key_on, description="on for everyone", enabled_default=True))
        s.add(FeatureFlag(key=key_pro, description="pro only", enabled_default=True, min_plan="pro"))
    try:
        async with c:
            body = (await c.get("/api/me")).json()
        assert body["email"] == me["email"]
        assert body["plan"] == {
            "code": "free",
            "is_pro": False,
            "subscription_status": None,
            "grace_until": None,
            "period": None,
        }
        assert body["credit_balance"] == 3
        assert body["flags"][key_on] is True
        assert body["flags"][key_pro] is False  # min_plan not met
        assert body["upstream"] == {"otodom_breaker_open": False, "retry_after_s": 0, "reason": None}
    finally:
        async with sm() as s, s.begin():
            await s.execute(
                text("DELETE FROM app.feature_flag WHERE key IN (:a, :b)"), {"a": key_on, "b": key_pro}
            )


async def test_me_shows_a_30_day_pass_as_pro_with_its_allowance(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    now = datetime.now(UTC)
    async with async_sessionmaker(engine)() as s, s.begin():
        s.add(
            UsagePeriod(
                user_id=me["id"],
                kind="pass",
                subscription_id=None,
                source_invoice_id=f"cs_{uuid4().hex[:12]}",
                period_start=now - timedelta(days=1),
                period_end=now + timedelta(days=29),
                allowance=40,
                used=15,
            )
        )
    async with c:
        plan = (await c.get("/api/me")).json()["plan"]
    assert plan["code"] == "pro"
    assert plan["is_pro"] is True
    assert plan["period"]["kind"] == "pass"
    assert (plan["period"]["allowance"], plan["period"]["used"], plan["period"]["remaining"]) == (40, 15, 25)


async def test_me_shows_the_otodom_circuit_breaker(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)
    sm = async_sessionmaker(engine)
    try:
        async with sm() as s, s.begin():
            await trip_breaker(s, OTODOM_HOST, "test: blocked", timedelta(minutes=5))
        async with c:
            upstream = (await c.get("/api/me")).json()["upstream"]
        assert upstream["otodom_breaker_open"] is True
        assert 1 <= upstream["retry_after_s"] <= 300
        assert upstream["reason"] == "test: blocked"
    finally:
        async with sm() as s, s.begin():
            await s.execute(
                text(
                    "UPDATE app.host_throttle SET breaker_open_until = NULL, breaker_reason = NULL "
                    "WHERE host = :h"
                ),
                {"h": OTODOM_HOST},
            )


# ---------- /api/saved ----------
async def test_saving_requires_having_audited_the_listing_and_foreign_ids_are_404(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    a, me_a = await sign_in(app, make_google_token)
    b, _ = await sign_in(app, make_google_token)
    oid = new_oid()
    await audit_listing(engine, me_a["id"], oid)
    async with a, b:
        foreign = await b.put(f"/api/saved/{oid}", json={"note": "mine now"})
        unknown = await b.put(f"/api/saved/{new_oid()}", json={"note": None})
        assert foreign.status_code == unknown.status_code == 404
        assert foreign.json()["code"] == unknown.json()["code"] == "NOT_FOUND"
        assert (
            foreign.json()["title"] == unknown.json()["title"]
        )  # indistinguishable from a listing nobody audited
        assert (await a.put(f"/api/saved/{oid}", json={"note": "good yield"})).status_code == 200
        assert (await b.get("/api/saved")).json() == []


async def test_saved_listings_keep_a_note_the_latest_audit_and_belong_to_one_user(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    a, me_a = await sign_in(app, make_google_token)
    oid = new_oid()
    await audit_listing(engine, me_a["id"], oid, age_s=3600)
    newest = await audit_listing(engine, me_a["id"], oid)
    async with a:
        saved = (await a.put(f"/api/saved/{oid}", json={"note": "call the agent"})).json()
        assert saved["otodom_id"] == oid
        assert saved["note"] == "call the agent"
        assert saved["latest_audit_id"] == newest
        again = (await a.put(f"/api/saved/{oid}", json={})).json()  # no note clears it, nothing duplicates
        assert again["note"] is None
        listed = (await a.get("/api/saved")).json()
        assert [row["otodom_id"] for row in listed] == [oid]


async def test_unsaving_is_idempotent_and_touches_only_my_rows(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    a, me_a = await sign_in(app, make_google_token)
    b, me_b = await sign_in(app, make_google_token)
    oid = new_oid()
    await audit_listing(engine, me_a["id"], oid)
    await audit_listing(engine, me_b["id"], oid)
    async with a, b:
        await a.put(f"/api/saved/{oid}", json={})
        await b.put(f"/api/saved/{oid}", json={})
        assert (await a.delete(f"/api/saved/{oid}")).status_code == 204
        assert (await a.delete(f"/api/saved/{oid}")).status_code == 204
        assert (await a.get("/api/saved")).json() == []
        assert len((await b.get("/api/saved")).json()) == 1


@pytest.mark.parametrize("path", ["abc", "x" * 17, "bad%20id", "a/b"])
async def test_saved_ids_are_validated(app: FastAPI, make_google_token: MakeToken, path: str) -> None:
    c, _ = await sign_in(app, make_google_token)
    async with c:
        assert (await c.put(f"/api/saved/{path}", json={})).status_code in {404, 422}


async def test_saved_input_is_bounded_and_strict(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    oid = new_oid()
    await audit_listing(engine, me["id"], oid)
    async with c:
        assert (await c.put(f"/api/saved/{oid}", json={"note": "x" * 2001})).status_code == 422
        assert (await c.put(f"/api/saved/{oid}", json={"note": "ok", "extra": 1})).status_code == 422
        assert (await c.get("/api/saved?limit=0")).status_code == 422
    async with client_for(app) as anonymous:
        assert (await anonymous.get("/api/saved")).status_code == 401


async def test_the_saved_list_is_bounded_per_user(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(saved_module, "MAX_SAVED", 2)
    c, me = await sign_in(app, make_google_token)
    oids = [new_oid() for _ in range(3)]
    for oid in oids:
        await audit_listing(engine, me["id"], oid)
    async with c:
        assert (await c.put(f"/api/saved/{oids[0]}", json={})).status_code == 200
        assert (await c.put(f"/api/saved/{oids[1]}", json={})).status_code == 200
        full = await c.put(f"/api/saved/{oids[2]}", json={})
        assert full.status_code == 409
        assert full.json()["code"] == "SAVED_LIMIT_REACHED"
        assert (
            await c.put(f"/api/saved/{oids[0]}", json={"note": "update"})
        ).status_code == 200  # edits still work


# ---------- /api/admin ----------
async def test_admin_routes_are_for_administrators_only(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    user, me = await sign_in(app, make_google_token)
    admin, _ = await make_admin(app, engine, make_google_token)
    probes = [
        ("GET", "/api/admin/flags", None),
        ("PUT", "/api/admin/flags/screener", {"enabled_default": True}),
        ("PUT", f"/api/admin/flags/screener/overrides/{me['id']}", {"enabled": True, "reason": "test"}),
        ("DELETE", f"/api/admin/flags/screener/overrides/{me['id']}", None),
        (
            "POST",
            "/api/admin/credits/adjust",
            {"user_id": me["id"], "delta": 1, "note": "n/a", "idempotency_key": str(uuid4())},
        ),
        ("GET", "/api/admin/jobs", None),
    ]
    async with user, admin, client_for(app) as anonymous:
        for method, path, body in probes:
            denied = await user.request(method, path, json=body)
            assert denied.status_code == 403, path
            assert denied.json()["code"] == "ADMIN_ONLY"
            assert (await anonymous.request(method, path, json=body)).status_code == 401, path
        assert (await admin.get("/api/admin/flags")).status_code == 200


async def test_admin_can_change_a_flag_and_override_it_for_one_user(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, plans: None
) -> None:
    admin, admin_me = await make_admin(app, engine, make_google_token)
    user, me = await sign_in(app, make_google_token)
    key = f"t_flag_{uuid4().hex[:6]}"
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s, s.begin():
        s.add(FeatureFlag(key=key, description="test flag", enabled_default=False))
    try:
        async with admin, user:
            assert (await user.get("/api/me")).json()["flags"][key] is False
            listed = {f["key"]: f for f in (await admin.get("/api/admin/flags")).json()}
            assert listed[key]["overrides"] == 0
            put = await admin.put(
                f"/api/admin/flags/{key}/overrides/{me['id']}",
                json={"enabled": True, "reason": "beta tester"},
            )
            assert put.status_code == 200
            assert put.json()["created_by"] == admin_me["id"]
            assert (await user.get("/api/me")).json()["flags"][key] is True
            assert {f["key"]: f for f in (await admin.get("/api/admin/flags")).json()}[key]["overrides"] == 1
            assert (await admin.delete(f"/api/admin/flags/{key}/overrides/{me['id']}")).status_code == 204
            assert (
                await admin.delete(f"/api/admin/flags/{key}/overrides/{me['id']}")
            ).status_code == 204  # idempotent
            assert (await user.get("/api/me")).json()["flags"][key] is False
            changed = await admin.put(
                f"/api/admin/flags/{key}",
                json={"enabled_default": True, "rollout_pct": 100, "min_plan": "pro"},
            )
            assert changed.json()["min_plan"] == "pro"
            cleared = await admin.put(f"/api/admin/flags/{key}", json={"clear_min_plan": True})
            assert (cleared.json()["min_plan"], cleared.json()["enabled_default"]) == (None, True)
    finally:
        async with sm() as s, s.begin():
            await s.execute(text("DELETE FROM app.feature_flag WHERE key = :k"), {"k": key})


async def test_flag_and_override_input_is_validated_and_unknowns_are_404(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    admin, _ = await make_admin(app, engine, make_google_token)
    _, me = await sign_in(app, make_google_token)
    async with admin:
        assert (
            await admin.put("/api/admin/flags/does_not_exist", json={"enabled_default": True})
        ).status_code == 404
        assert (await admin.put("/api/admin/flags/Bad-Key", json={})).status_code == 422
        assert (await admin.put("/api/admin/flags/x", json={"rollout_pct": 101})).status_code == 422
        assert (await admin.put("/api/admin/flags/x", json={"surprise": 1})).status_code == 422
        assert (
            await admin.put(
                f"/api/admin/flags/does_not_exist/overrides/{me['id']}",
                json={"enabled": True, "reason": "abc"},
            )
        ).status_code == 404
        assert (
            await admin.put("/api/admin/flags/x/overrides/nobody", json={"enabled": True, "reason": "abc"})
        ).status_code == 404
        assert (
            await admin.put(f"/api/admin/flags/x/overrides/{me['id']}", json={"enabled": True, "reason": "a"})
        ).status_code == 422


async def balance(engine: AsyncEngine, user_id: str) -> int:
    async with engine.connect() as conn:
        return int(
            await conn.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == user_id)) or 0
        )


async def test_a_credit_adjustment_is_applied_once_per_idempotency_key(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    admin, admin_me = await make_admin(app, engine, make_google_token)
    _, me = await sign_in(app, make_google_token)
    key = str(uuid4())
    body = {"user_id": me["id"], "delta": 5, "note": "goodwill", "idempotency_key": key}
    async with admin:
        first = await admin.post("/api/admin/credits/adjust", json=body)
        again = await admin.post("/api/admin/credits/adjust", json=body)
    assert first.json() == {"applied": True, "balance": 8}
    assert again.json() == {"applied": False, "balance": 8}
    assert await balance(engine, me["id"]) == 8
    async with engine.connect() as conn:
        rows = (
            await conn.execute(select(CreditLedger).where(CreditLedger.idempotency_key == f"admin:{key}"))
        ).all()
    assert len(rows) == 1
    assert admin_me["id"] in rows[0].note  # who did it is recorded
    async with async_sessionmaker(engine)() as s:
        assert me["id"] not in await ledger_mismatches(s)


async def test_concurrent_adjustments_with_one_key_apply_exactly_once(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    admin, _ = await make_admin(app, engine, make_google_token)
    _, me = await sign_in(app, make_google_token)
    raw = admin.cookies["rm_session"]
    body = {"user_id": me["id"], "delta": 2, "note": "race", "idempotency_key": str(uuid4())}

    async def attempt() -> bool:
        async with client_for(app) as c:
            c.cookies.set("rm_session", raw)
            r = await c.post("/api/admin/credits/adjust", json=body)
            assert r.status_code == 200
            return bool(r.json()["applied"])

    results = await asyncio.gather(*(attempt() for _ in range(6)))
    assert results.count(True) == 1
    assert await balance(engine, me["id"]) == 5


async def test_an_adjustment_cannot_take_the_balance_below_zero_and_leaves_no_trace(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    admin, _ = await make_admin(app, engine, make_google_token)
    _, me = await sign_in(app, make_google_token)
    key = str(uuid4())
    async with admin:
        refused = await admin.post(
            "/api/admin/credits/adjust",
            json={"user_id": me["id"], "delta": -4, "note": "too much", "idempotency_key": key},
        )
        assert refused.status_code == 409
        assert refused.json()["code"] == "CREDIT_BELOW_ZERO"
        ok = await admin.post(
            "/api/admin/credits/adjust",
            json={"user_id": me["id"], "delta": -3, "note": "exactly all", "idempotency_key": str(uuid4())},
        )
        assert ok.json() == {"applied": True, "balance": 0}
    async with engine.connect() as conn:
        assert (
            await conn.scalar(
                select(func.count())
                .select_from(CreditLedger)
                .where(CreditLedger.idempotency_key == f"admin:{key}")
            )
            == 0
        )
    async with async_sessionmaker(engine)() as s:
        assert me["id"] not in await ledger_mismatches(s)


async def test_credit_adjustment_input_is_validated(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    admin, _ = await make_admin(app, engine, make_google_token)
    _, me = await sign_in(app, make_google_token)
    base = {"user_id": me["id"], "delta": 1, "note": "valid note", "idempotency_key": str(uuid4())}
    async with admin:
        for patch in (
            {"delta": 0},
            {"delta": 1001},
            {"delta": -1001},
            {"note": "x"},
            {"idempotency_key": "not-a-uuid"},
            {"extra": 1},
        ):
            assert (
                await admin.post("/api/admin/credits/adjust", json={**base, **patch})
            ).status_code == 422, patch
        missing = await admin.post("/api/admin/credits/adjust", json={**base, "user_id": "no-such-user"})
        assert missing.status_code == 404


async def test_job_inspection_shows_metadata_and_never_the_arguments(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    procrastinate_schema: None,
    migrated_url: str,
) -> None:
    import procrastinate  # noqa: PLC0415

    admin, _ = await make_admin(app, engine, make_google_token)
    secret = f"victim-{uuid4().hex[:8]}@example.test"
    dsn = migrated_url.replace("postgresql+psycopg://", "postgresql://", 1)
    jobs = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=dsn, min_size=1, max_size=2))
    await jobs.open_async()
    try:
        job_id = await jobs.configure_task(
            name="rm_worker.tasks.email.send_magic_link", queue="ops_probe"
        ).defer_async(email=secret, url="https://app.test/login/email#t=SECRETTOKEN")
        async with admin:
            r = await admin.get("/api/admin/jobs?queue=ops_probe&status=todo")
            all_jobs = await admin.get("/api/admin/jobs")
            bad = await admin.get("/api/admin/jobs?status=nope")
            bad_queue = await admin.get("/api/admin/jobs?queue=Bad-Queue")
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM procrastinate_jobs WHERE queue_name = 'ops_probe'"))
        await jobs.close_async()
    body = r.json()
    assert [j["id"] for j in body["recent"]] == [job_id]
    assert body["recent"][0]["task"] == "rm_worker.tasks.email.send_magic_link"
    assert body["recent"][0]["status"] == "todo"
    assert body["counts"]["ops_probe"] == {"todo": 1}
    for response in (r, all_jobs):
        assert secret not in response.text
        assert "SECRETTOKEN" not in response.text
    assert bad.status_code == 422
    assert bad_queue.status_code == 422
