"""Ledger check, queue/connection monitor and old-job cleanup against real Postgres and Procrastinate."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import uuid4

import procrastinate
import pytest
from rm_core.db.models import CreditAccount, User
from rm_worker import monitors
from rm_worker.tasks import maintenance
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]


class FakeHeartbeat:
    def __init__(self) -> None:
        self.pings: list[bool] = []

    async def ping(self, *, ok: bool = True) -> bool:
        self.pings.append(ok)
        return True


@pytest.fixture
async def jobs(migrated_url: str, procrastinate_schema: None) -> AsyncIterator[procrastinate.App]:
    dsn = migrated_url.replace("postgresql+psycopg://", "postgresql://", 1)
    app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=dsn, min_size=1, max_size=2))
    await app.open_async()
    try:
        yield app
    finally:
        await app.close_async()


async def make_job(
    jobs: procrastinate.App, engine: AsyncEngine, queue: str, *, age_hours: float, status: str = "todo"
) -> int:
    job_id = await jobs.configure_task(name="noop", queue=queue).defer_async()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE procrastinate_jobs SET status = CAST(:s AS procrastinate_job_status) WHERE id = :i"),
            {"s": status, "i": job_id},
        )
        await conn.execute(
            text("UPDATE procrastinate_events SET at = now() - :h * interval '1 hour' WHERE job_id = :i"),
            {"h": age_hours, "i": job_id},
        )
    return int(job_id)


async def job_exists(engine: AsyncEngine, job_id: int) -> bool:
    async with engine.connect() as conn:
        return bool(
            await conn.scalar(text("SELECT count(*) FROM procrastinate_jobs WHERE id = :i"), {"i": job_id})
        )


async def drop_jobs(engine: AsyncEngine, *queues: str) -> None:
    async with engine.begin() as conn:
        for queue in queues:
            await conn.execute(text("DELETE FROM procrastinate_jobs WHERE queue_name = :q"), {"q": queue})


# ---------- ledger check ----------
async def test_a_clean_ledger_pings_the_heartbeat_with_success(engine: AsyncEngine) -> None:
    hb = FakeHeartbeat()
    mismatched = await maintenance.run_ledger_check(async_sessionmaker(engine), hb)
    assert mismatched == []
    assert hb.pings == [True]


async def test_a_balance_that_differs_from_the_ledger_alerts_and_fails_the_heartbeat(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        maintenance.sentry_sdk,
        "capture_message",
        lambda message, level=None, **_k: sent.append((message, level or "")),
    )
    user_id = str(uuid4())
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s, s.begin():
        s.add(User(id=user_id, email=f"{user_id}@example.test"))
        await s.flush()
        s.add(CreditAccount(user_id=user_id, balance=5))  # five credits and no ledger row: corrupt on purpose
    hb = FakeHeartbeat()
    try:
        mismatched = await maintenance.run_ledger_check(sm, hb)
    finally:
        async with sm() as s, s.begin():  # other tests assert an empty global mismatch list
            await s.execute(delete(User).where(User.id == user_id))
    assert mismatched == [user_id]
    assert hb.pings == [False]
    assert sent == [("ledger mismatch on 1 account(s)", "error")]
    assert user_id not in sent[0][0]  # the message carries a count, never an id or an address


# ---------- monitor ----------
async def test_queue_lag_is_measured_per_queue_and_ignores_future_jobs(
    jobs: procrastinate.App, engine: AsyncEngine
) -> None:
    lagging, fresh, later = (f"q-{uuid4().hex[:8]}" for _ in range(3))
    try:
        await make_job(jobs, engine, lagging, age_hours=0.5)  # 30 minutes
        await make_job(jobs, engine, fresh, age_hours=0.0)
        scheduled = await jobs.configure_task(
            name="noop", queue=later, schedule_in={"hours": 5}
        ).defer_async()
        assert scheduled
        async with async_sessionmaker(engine)() as s:
            ages = await monitors.queue_ages(s)
        assert 1790 <= ages[lagging] <= 1900
        assert ages[fresh] < 30
        assert later not in ages  # a job scheduled for later is not waiting yet
    finally:
        await drop_jobs(engine, lagging, fresh, later)


async def test_the_monitor_reports_a_lagging_queue_to_sentry(
    jobs: procrastinate.App, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = f"q-{uuid4().hex[:8]}"
    sent: list[str] = []
    monkeypatch.setattr(maintenance.sentry_sdk, "capture_message", lambda message, **_k: sent.append(message))
    try:
        await make_job(jobs, engine, queue, age_hours=1.0)
        alerts = await maintenance.run_monitor(async_sessionmaker(engine))
    finally:
        await drop_jobs(engine, queue)
    assert f"queue_lag:{queue}" in {a.key for a in alerts}
    assert any(queue in message for message in sent)


async def test_the_connection_count_includes_our_own_backends(engine: AsyncEngine) -> None:
    async with async_sessionmaker(engine)() as s:
        assert await monitors.connection_count(s) >= 1


# ---------- cleanup of old jobs (L-011) ----------
async def test_ops_jobs_go_after_a_day_and_other_queues_after_a_week(
    jobs: procrastinate.App, engine: AsyncEngine
) -> None:
    context = SimpleNamespace(app=jobs)
    old_ops = await make_job(jobs, engine, "ops", age_hours=30, status="failed")
    fresh_ops = await make_job(jobs, engine, "ops", age_hours=2, status="failed")
    done_ops = await make_job(jobs, engine, "ops", age_hours=30, status="succeeded")
    audit_3d = await make_job(jobs, engine, "audit", age_hours=72, status="failed")
    audit_9d = await make_job(jobs, engine, "audit", age_hours=216, status="failed")
    waiting = await make_job(jobs, engine, "ops", age_hours=48, status="todo")
    try:
        await maintenance.remove_old_jobs_ops(context, 0)  # type: ignore[arg-type]
        await maintenance.remove_old_jobs_other(context, 0)  # type: ignore[arg-type]
        assert not await job_exists(engine, old_ops)
        assert not await job_exists(engine, done_ops)
        assert await job_exists(engine, fresh_ops)
        assert await job_exists(engine, audit_3d)
        assert not await job_exists(engine, audit_9d)
        assert await job_exists(engine, waiting)  # never delete work that has not run
    finally:
        await drop_jobs(engine, "ops", "audit")
