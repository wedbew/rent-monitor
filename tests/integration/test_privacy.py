"""GDPR retention, erasure and export on real Postgres (RM-30). Data is committed, so each test "
"cleans up after itself."""

import asyncio
import json
from uuid import uuid4

import pytest
from rm_core import privacy
from rm_core.privacy import (
    delete_account,
    export_user_data,
    purge_expired,
    reapply_erasures,
    user_hash,
)
from rm_core.settings import Settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration]
REMAINING = {
    "auth_identity": "SELECT count(*) FROM app.auth_identity WHERE user_id = :u",
    "credit_account": "SELECT count(*) FROM app.credit_account WHERE user_id = :u",
    "credit_ledger": "SELECT count(*) FROM app.credit_ledger WHERE user_id = :u",
    "stripe_customer": "SELECT count(*) FROM app.stripe_customer WHERE user_id = :u",
    "saved_listing": "SELECT count(*) FROM app.saved_listing WHERE user_id = :u",
    "app_user": "SELECT count(*) FROM app.app_user WHERE id = :u",
}
SETTINGS = Settings(
    retention_session_days=7,
    retention_login_token_days=1,
    retention_snapshot_days=30,
    retention_audit_event_days=30,
)


@pytest.fixture
def sm(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def _exec(engine: AsyncEngine, sql: str, **params: object) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def _count(engine: AsyncEngine, sql: str, **params: object) -> int:
    async with engine.connect() as conn:
        return int(await conn.scalar(text(sql), params) or 0)


async def _user(engine: AsyncEngine, email: str | None = None) -> str:
    uid = str(uuid4())
    await _exec(
        engine,
        "INSERT INTO app.app_user (id, email) VALUES (:i, :e)",
        i=uid,
        e=email or f"{uid}@example.test",
    )
    return uid


async def test_sessions_and_tokens_are_purged_only_after_their_retention(engine: AsyncEngine, sm) -> None:
    uid = await _user(engine)
    mark = uuid4().hex[:8]
    try:
        for name, days in (("old", 9), ("recent", 2), ("live", -5)):
            await _exec(
                engine,
                "INSERT INTO app.user_session (token_hash, user_id, expires_at) "
                "VALUES (:t, :u, now() - make_interval(days => :d))",
                t=f"{mark}{name}".ljust(64, "x"),
                u=uid,
                d=days,
            )
        for name, exp, used in (("old", 3, None), ("used", -5, 3), ("fresh", -1, None)):
            await _exec(
                engine,
                "INSERT INTO app.login_token (token_hash, email, expires_at, used_at) "
                "VALUES (:t, 'x@example.test', now() - make_interval(days => :e), "
                "CASE WHEN CAST(:u AS int) IS NULL THEN NULL ELSE now() - make_interval(days => "
                "CAST(:u AS int)) END)",
                t=f"{mark}{name}".ljust(64, "y"),
                e=exp,
                u=used,
            )
        report = await purge_expired(sm, SETTINGS)
        assert report.sessions >= 1
        assert report.login_tokens >= 2
        left = await _count(
            engine, "SELECT count(*) FROM app.user_session WHERE token_hash LIKE :m", m=f"{mark}%"
        )
        assert left == 2  # recent (expired 2 d ago, within 7 d) and live remain
        tokens = await _count(
            engine, "SELECT count(*) FROM app.login_token WHERE token_hash LIKE :m", m=f"{mark}%"
        )
        assert tokens == 1  # only `fresh` (expires in the future) remains
    finally:
        await _exec(engine, "DELETE FROM app.app_user WHERE id = :u", u=uid)
        await _exec(engine, "DELETE FROM app.login_token WHERE token_hash LIKE :m", m=f"{mark}%")


async def test_snapshots_are_deleted_or_scrubbed_and_events_expire(engine: AsyncEngine, sm) -> None:
    uid = await _user(engine)
    oid_a, oid_b, oid_c = (f"ID{uuid4().hex[:6]}" for _ in range(3))
    snap_old, snap_ref, snap_new, audit = (str(uuid4()) for _ in range(4))
    try:
        for oid in (oid_a, oid_b, oid_c):
            await _exec(
                engine, "INSERT INTO app.listing (otodom_id, url) VALUES (:o, 'https://x.test')", o=oid
            )
        for sid, oid, age in ((snap_old, oid_a, 40), (snap_ref, oid_b, 40), (snap_new, oid_c, 1)):
            await _exec(
                engine,
                "INSERT INTO app.listing_snapshot (id, otodom_id, content_sha256, payload, "
                "fetched_at) VALUES "
                '(:i, :o, :h, CAST(\'{"seller":"Jan"}\' AS jsonb), now() - make_interval(days => :a))',
                i=sid,
                o=oid,
                h=uuid4().hex.ljust(64, "0"),
                a=age,
            )
        await _exec(
            engine,
            "INSERT INTO app.audit (id, user_id, otodom_id, snapshot_id, status, charge_source, "
            "charge_state, "
            "engine_version, schema_version) VALUES (:a, :u, :o, :s, 'succeeded', 'credit', "
            "'captured', 't', 1)",
            a=audit,
            u=uid,
            o=oid_b,
            s=snap_ref,
        )
        await _exec(
            engine,
            "INSERT INTO app.audit_event (audit_id, kind, created_at) VALUES (:a, 'progress', now() "
            "- interval '45 days')",
            a=audit,
        )
        await _exec(engine, "INSERT INTO app.audit_event (audit_id, kind) VALUES (:a, 'done')", a=audit)

        report = await purge_expired(sm, SETTINGS)
        assert report.snapshots_deleted >= 1
        assert report.snapshots_scrubbed >= 1
        assert (
            await _count(engine, "SELECT count(*) FROM app.listing_snapshot WHERE id = :i", i=snap_old) == 0
        )
        payload = await _count(
            engine,
            "SELECT count(*) FROM app.listing_snapshot WHERE id = :i AND payload = '{}'::jsonb",
            i=snap_ref,
        )
        assert payload == 1  # referenced by an audit: kept, but the third-party payload is gone
        assert (
            await _count(
                engine,
                "SELECT count(*) FROM app.listing_snapshot WHERE id = :i AND payload <> '{}'::jsonb",
                i=snap_new,
            )
            == 1
        )
        assert await _count(engine, "SELECT count(*) FROM app.audit_event WHERE audit_id = :a", a=audit) == 1
        again = await purge_expired(sm, SETTINGS)
        assert again.snapshots_scrubbed == 0  # idempotent
    finally:
        await _exec(engine, "DELETE FROM app.app_user WHERE id = :u", u=uid)
        await _exec(
            engine,
            "DELETE FROM app.listing_snapshot WHERE otodom_id IN (:a, :b, :c)",
            a=oid_a,
            b=oid_b,
            c=oid_c,
        )
        await _exec(
            engine, "DELETE FROM app.listing WHERE otodom_id IN (:a, :b, :c)", a=oid_a, b=oid_b, c=oid_c
        )


async def test_purge_works_in_bounded_batches(
    engine: AsyncEngine, sm, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(privacy, "BATCH_SIZE", 3)
    uid = await _user(engine)
    mark = uuid4().hex[:8]
    try:
        for i in range(10):
            await _exec(
                engine,
                "INSERT INTO app.user_session (token_hash, user_id, expires_at) VALUES (:t, :u, "
                "now() - interval '30 days')",
                t=f"{mark}{i}".ljust(64, "z"),
                u=uid,
            )
        report = await purge_expired(sm, SETTINGS)
        assert report.sessions >= 10
        assert (
            await _count(
                engine, "SELECT count(*) FROM app.user_session WHERE token_hash LIKE :m", m=f"{mark}%"
            )
            == 0
        )
    finally:
        await _exec(engine, "DELETE FROM app.app_user WHERE id = :u", u=uid)


async def test_old_erasure_log_entries_expire(engine: AsyncEngine, sm) -> None:
    old, fresh = uuid4().hex.ljust(64, "a"), uuid4().hex.ljust(64, "b")
    try:
        await _exec(
            engine,
            "INSERT INTO app.erasure_log (user_hash, erased_at) VALUES (:h, now() - interval '80 days')",
            h=old,
        )
        await _exec(engine, "INSERT INTO app.erasure_log (user_hash) VALUES (:h)", h=fresh)
        await purge_expired(sm, SETTINGS)
        assert await _count(engine, "SELECT count(*) FROM app.erasure_log WHERE user_hash = :h", h=old) == 0
        assert await _count(engine, "SELECT count(*) FROM app.erasure_log WHERE user_hash = :h", h=fresh) == 1
    finally:
        await _exec(engine, "DELETE FROM app.erasure_log WHERE user_hash = :h", h=fresh)


# GDPR[erasure]
async def test_delete_account_erases_everything_and_only_hash_remains(engine: AsyncEngine, sm) -> None:
    uid, other = await _user(engine), await _user(engine)
    oid = f"ID{uuid4().hex[:6]}"
    try:
        await _exec(engine, "INSERT INTO app.listing (otodom_id, url) VALUES (:o, 'https://x.test')", o=oid)
        await _exec(
            engine,
            "INSERT INTO app.auth_identity (user_id, provider, subject) VALUES (:u, 'email', :s)",
            u=uid,
            s=f"{uid}@example.test",
        )
        await _exec(engine, "INSERT INTO app.credit_account (user_id, balance) VALUES (:u, 3)", u=uid)
        await _exec(
            engine,
            "INSERT INTO app.credit_ledger (user_id, delta, reason, idempotency_key) VALUES (:u, 3, "
            "'signup_grant', :k)",
            u=uid,
            k=f"signup:{uid}",
        )
        await _exec(
            engine,
            "INSERT INTO app.stripe_customer (user_id, stripe_customer_id) VALUES (:u, :c)",
            u=uid,
            c=f"cus_{uid[:8]}",
        )
        await _exec(
            engine,
            "INSERT INTO app.saved_listing (user_id, otodom_id, note) VALUES (:u, :o, 'my private note')",
            u=uid,
            o=oid,
        )
        async with sm() as s, s.begin():
            report = await delete_account(s, uid)
        assert report.deleted is True
        assert report.stripe_customer_id == f"cus_{uid[:8]}"
        for table in (
            "auth_identity",
            "credit_account",
            "credit_ledger",
            "stripe_customer",
            "saved_listing",
            "app_user",
        ):
            assert await _count(engine, REMAINING[table], u=uid) == 0, table
        assert await _count(engine, "SELECT count(*) FROM app.app_user WHERE id = :u", u=other) == 1
        assert (
            await _count(
                engine, "SELECT count(*) FROM app.erasure_log WHERE user_hash = :h", h=user_hash(uid)
            )
            == 1
        )
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text("SELECT * FROM app.erasure_log WHERE user_hash = :h"), {"h": user_hash(uid)}
                )
            ).all()
        assert uid not in json.dumps(
            [[str(c) for c in r] for r in rows]
        )  # the log holds a hash, never the id
        async with sm() as s, s.begin():
            again = await delete_account(s, uid)
        assert again.deleted is False
    finally:
        await _exec(engine, "DELETE FROM app.app_user WHERE id IN (:a, :b)", a=uid, b=other)
        await _exec(engine, "DELETE FROM app.listing WHERE otodom_id = :o", o=oid)
        await _exec(engine, "DELETE FROM app.erasure_log WHERE user_hash = :h", h=user_hash(uid))


async def test_parallel_deletions_report_one_winner(engine: AsyncEngine, sm) -> None:
    uid = await _user(engine)

    async def one() -> bool:
        async with sm() as s, s.begin():
            return (await delete_account(s, uid)).deleted

    try:
        results = await asyncio.gather(*(one() for _ in range(6)))
        assert results.count(True) == 1
        assert (
            await _count(
                engine, "SELECT count(*) FROM app.erasure_log WHERE user_hash = :h", h=user_hash(uid)
            )
            == 1
        )
    finally:
        await _exec(engine, "DELETE FROM app.erasure_log WHERE user_hash = :h", h=user_hash(uid))


async def test_restore_from_an_old_backup_is_re_erased_from_the_exported_log(engine: AsyncEngine, sm) -> None:
    uid, keeper = await _user(engine), await _user(engine)
    exported = [user_hash(uid), "not-a-hash", "G" * 64]
    try:
        async with sm() as s, s.begin():
            n = await reapply_erasures(s, exported)
        assert n == 1
        assert await _count(engine, "SELECT count(*) FROM app.app_user WHERE id = :u", u=uid) == 0
        assert await _count(engine, "SELECT count(*) FROM app.app_user WHERE id = :u", u=keeper) == 1
        async with sm() as s, s.begin():
            assert await reapply_erasures(s, []) == 0
    finally:
        await _exec(engine, "DELETE FROM app.app_user WHERE id = :u", u=keeper)
        await _exec(engine, "DELETE FROM app.erasure_log WHERE user_hash = :h", h=user_hash(uid))


async def test_export_contains_the_users_data_and_nobody_elses(engine: AsyncEngine, sm) -> None:
    uid, other = await _user(engine), await _user(engine)
    oid = f"ID{uuid4().hex[:6]}"
    try:
        await _exec(engine, "INSERT INTO app.listing (otodom_id, url) VALUES (:o, 'https://x.test')", o=oid)
        await _exec(
            engine,
            "INSERT INTO app.user_session (token_hash, user_id, expires_at, ip, user_agent) VALUES "
            "(:t, :u, now() + interval '1 day', '203.0.113.9', 'UA/1')",
            t=uuid4().hex.ljust(64, "q"),
            u=uid,
        )
        await _exec(engine, "INSERT INTO app.credit_account (user_id, balance) VALUES (:u, 2)", u=uid)
        await _exec(
            engine,
            "INSERT INTO app.credit_ledger (user_id, delta, reason, idempotency_key) VALUES (:u, 3, "
            "'signup_grant', :k)",
            u=uid,
            k=f"signup:{uid}",
        )
        await _exec(
            engine,
            "INSERT INTO app.saved_listing (user_id, otodom_id, note) VALUES (:u, :o, 'note-A')",
            u=uid,
            o=oid,
        )
        await _exec(
            engine,
            "INSERT INTO app.saved_listing (user_id, otodom_id, note) VALUES (:u, :o, 'note-OTHER')",
            u=other,
            o=oid,
        )
        await _exec(
            engine,
            "INSERT INTO app.audit (user_id, otodom_id, status, charge_source, charge_state, "
            "engine_version, schema_version, "
            "result, asking_price_pln) VALUES (:u, :o, 'succeeded', 'credit', 'captured', 't', 1, "
            'CAST(\'{"grade":"B"}\' AS jsonb), 450000.50)',
            u=uid,
            o=oid,
        )
        async with sm() as s:
            data = await export_user_data(s, uid)
            assert await export_user_data(s, str(uuid4())) is None
        assert data is not None
        assert data.profile.id == uid
        assert data.credit_balance == 2
        assert [e.delta for e in data.credit_ledger] == [3]
        assert data.sessions[0].ip == "203.0.113.9"
        assert [x.note for x in data.saved_listings] == ["note-A"]
        assert data.audits[0].result == {"grade": "B"}
        text_out = data.model_dump_json()
        assert "note-OTHER" not in text_out
        assert "token_hash" not in text_out
        assert other not in text_out
        assert '"asking_price_pln":"450000.50"' in text_out  # Decimal stays exact
    finally:
        await _exec(engine, "DELETE FROM app.app_user WHERE id IN (:a, :b)", a=uid, b=other)
        await _exec(engine, "DELETE FROM app.listing WHERE otodom_id = :o", o=oid)
