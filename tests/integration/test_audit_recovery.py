# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
"""Interrupted audits end correctly and the charge settles exactly once (#186, blueprint §2, §4.5 b).

Real Postgres, real Procrastinate worker, real engine child process. Every scenario ends with a consistent
ledger. The reconciler and a worker racing on one audit is a concurrency test, not a happy path: whichever
commits first wins, the other changes nothing, and the credit is released at most once.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import UUID

import procrastinate
import pytest
from rm_core.db.models import Audit, AuditStatus, ChargeState
from rm_core.ledger import admin_adjust
from rm_worker.app import app as worker_app
from rm_worker.audit_pipeline import Outcome, _finish
from rm_worker.engine_child import ChildEngine
from rm_worker.tasks.reconcile import (
    Reconciled,
    _fail,
    defer_run_audit,
    reconcile_audits,
)
from sqlalchemy import select, text
from test_audit_journey import (  # noqa: F401  (fixtures: `h`, the autouse `clean_up`)
    SIGNUP_CREDITS,
    Harness,
    clean_up,
    h,
    new_ref,
    sale_ad,
    submit,
)
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
TESTS_DIR = str(Path(__file__).resolve().parent.parent)
JOB_TIMEOUT_S = 900.0
PAST_DEADLINE_S = 900 + 61  # deadline + the reconciler's grace, plus a second


class DownQueue:
    """The queue is unreachable when the API tries to defer (the job never exists)."""

    async def run_audit(self, audit_id: UUID) -> None:
        raise ConnectionError("queue down")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def reconcile(h: Harness) -> Reconciled:
    connector = procrastinate.PsycopgConnector(conninfo=h.dsn, min_size=1, max_size=3)
    with worker_app.replace_connector(connector) as app:
        async with app.open_async():
            return await reconcile_audits(h.sm, defer_run_audit, job_timeout_s=JOB_TIMEOUT_S)


async def age(h: Harness, audit_id: str, *, seconds: float, status: str | None = None) -> None:
    """Move an audit's clocks into the past (and optionally its status), as if that much time had gone by."""
    async with h.engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE app.audit SET created_at = now() - make_interval(secs => :s),"
                " started_at = CASE WHEN :st = 'running' OR status = 'running'"
                "   THEN now() - make_interval(secs => :s) ELSE started_at END,"
                " status = COALESCE(CAST(:st AS app.audit_status), status) WHERE id = :id"
            ),
            {"s": seconds, "st": status, "id": audit_id},
        )


async def submit_audit(h: Harness, c: object, **ad: object) -> str:
    ref = new_ref()
    h.source.ads[ref] = sale_ad(**ad)
    r = await submit(c, ref)
    assert r.status_code == 202, r.text
    return str(r.json()["audit_id"])


@pytest.fixture
async def broken_queue(h: Harness) -> AsyncIterator[None]:
    real = h.app.state.audit_queue
    h.app.state.audit_queue = DownQueue()
    yield
    h.app.state.audit_queue = real


# ----------------------------------------------------------------------------- failed enqueue
async def test_a_failed_enqueue_is_redeferred_and_the_audit_completes(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    assert await h.audit_job_count() == 0  # accepted and charged, but no job exists
    assert (await h.audit(audit_id)).status is AuditStatus.queued
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1

    assert (await reconcile(h)).redeferred == []  # fresh: the API may still be about to defer it
    await age(h, audit_id, seconds=120)
    done = await reconcile(h)
    assert done.redeferred == [UUID(audit_id)]
    assert done.failed == []
    assert await h.audit_job_count() == 1

    again = await reconcile(h)  # the queueing lock: still one job, not two
    assert await h.audit_job_count() == 1
    assert again.failed == []

    await h.run_worker()
    got = await h.audit(audit_id)
    assert got.status is AuditStatus.succeeded_degraded
    assert got.charge_state is ChargeState.captured
    assert await h.ledger_rows(audit_id) == ["reserve"]
    await h.assert_ledger_consistent()


async def test_a_queued_audit_that_outlives_its_deadline_fails_and_releases(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await age(h, audit_id, seconds=PAST_DEADLINE_S)
    done = await reconcile(h)
    assert done.failed == [UUID(audit_id)]
    assert done.redeferred == []
    got = await h.audit(audit_id)
    assert (got.status, got.error_code, got.charge_state) == (
        AuditStatus.failed_internal,
        "TIMEOUT",
        ChargeState.released,
    )
    assert got.finished_at is not None
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    assert await h.ledger_rows(audit_id) == ["reserve", "release"]
    assert await h.audit_job_count() == 0
    await h.assert_ledger_consistent()


# ----------------------------------------------------------------------------- worker death
async def test_an_audit_orphaned_by_a_dead_worker_is_failed_and_released(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await age(h, audit_id, seconds=PAST_DEADLINE_S, status="running")  # claimed, then the worker was killed
    done = await reconcile(h)
    assert done.failed == [UUID(audit_id)]
    got = await h.audit(audit_id)
    assert (got.status, got.error_code, got.charge_state) == (
        AuditStatus.failed_internal,
        "TIMEOUT",
        ChargeState.released,
    )
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    await h.assert_ledger_consistent()


async def test_a_healthy_running_audit_is_left_alone(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await age(h, audit_id, seconds=300, status="running")  # slow, but well inside its 900 s deadline
    done = await reconcile(h)
    assert (done.failed, done.redeferred) == ([], [])
    got = await h.audit(audit_id)
    assert (got.status, got.charge_state) == (AuditStatus.running, ChargeState.reserved)
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1


async def test_the_reconciler_is_idempotent(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await age(h, audit_id, seconds=PAST_DEADLINE_S, status="running")
    first, second, third = await asyncio.gather(reconcile(h), reconcile(h), reconcile(h))
    assert sorted(len(r.failed) for r in (first, second, third)) == [0, 0, 1]
    assert await h.ledger_rows(audit_id) == ["reserve", "release"]  # released once, however many ran
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    assert (await reconcile(h)).failed == []
    await h.assert_ledger_consistent()


# ----------------------------------------------------------------------------- the race
async def test_a_worker_and_the_reconciler_racing_on_one_audit_settle_it_once(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    """The worker finishes (captures) as the reconciler gives up (releases). Exactly one wins, and the ledger
    agrees with the final status, every time."""
    c, me = await sign_in(h.app, make_google_token)
    async with h.sm() as s, s.begin():
        await admin_adjust(s, me["id"], 20, key=f"race-{me['id']}", note="race test")
    winners: dict[str, int] = {"worker": 0, "reconciler": 0}
    for _ in range(12):
        audit_id = await submit_audit(h, c)
        await age(h, audit_id, seconds=PAST_DEADLINE_S, status="running")
        calls = [
            _finish(h.sm, UUID(audit_id), Outcome(AuditStatus.succeeded)),
            _fail(h.sm, UUID(audit_id), JOB_TIMEOUT_S),
            _fail(h.sm, UUID(audit_id), JOB_TIMEOUT_S),
            _finish(h.sm, UUID(audit_id), Outcome(AuditStatus.succeeded)),
        ]
        results = await asyncio.gather(*calls)
        assert results.count(True) == 1, results  # one settlement, never two, never none
        got = await h.audit(audit_id)
        if got.status is AuditStatus.succeeded:
            winners["worker"] += 1
            assert got.charge_state is ChargeState.captured
            assert await h.ledger_rows(audit_id) == ["reserve"]
        else:
            winners["reconciler"] += 1
            assert (got.status, got.error_code) == (AuditStatus.failed_internal, "TIMEOUT")
            assert got.charge_state is ChargeState.released
            assert await h.ledger_rows(audit_id) == ["reserve", "release"]
        await h.assert_ledger_consistent()
    assert sum(winners.values()) == 12


async def test_a_late_worker_cannot_settle_an_audit_the_reconciler_already_ended(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await age(h, audit_id, seconds=PAST_DEADLINE_S, status="running")
    assert (await reconcile(h)).failed == [UUID(audit_id)]
    assert await _finish(h.sm, UUID(audit_id), Outcome(AuditStatus.succeeded)) is False  # too late
    got = await h.audit(audit_id)
    assert (got.status, got.charge_state) == (AuditStatus.failed_internal, ChargeState.released)
    assert await h.ledger_rows(audit_id) == ["reserve", "release"]
    assert await h.balance(me["id"]) == SIGNUP_CREDITS


# ----------------------------------------------------------------------------- the killable engine
@pytest.fixture
def child_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("PYTHONPATH", TESTS_DIR)
    pid_file = tmp_path / "pids"
    monkeypatch.setenv("ENGINE_PID_FILE", str(pid_file))
    return pid_file


@pytest.mark.parametrize(
    ("target", "code"),
    [("engine_targets:hang", "TIMEOUT"), ("engine_targets:crash", "INTERNAL")],
    ids=["engine-never-returns", "engine-dies"],
)
async def test_a_blocked_or_dying_engine_ends_the_audit_and_releases_the_credit(
    h: Harness, make_google_token: MakeToken, child_env: Path, target: str, code: str
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await h.run_worker(timeout_s=5.0, engine=ChildEngine(target=target))
    got = await h.audit(audit_id)
    assert (got.status, got.error_code, got.charge_state) == (
        AuditStatus.failed_internal,
        code,
        ChargeState.released,
    )
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    assert await h.ledger_rows(audit_id) == ["reserve", "release"]
    await h.assert_ledger_consistent()
    if code == "TIMEOUT":
        pids = [int(x) for x in (await asyncio.to_thread(child_env.read_text)).split()]
        assert pids
        assert not any(_alive(pid) for pid in pids)  # the hung engine process was killed, not abandoned


async def test_an_audit_is_not_reassigned_after_a_terminal_state(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await h.run_worker()
    await age(h, audit_id, seconds=PAST_DEADLINE_S)  # finished long ago: never "stale"
    assert (await reconcile(h)).failed == []
    async with h.sm() as s:
        status = await s.scalar(select(Audit.status).where(Audit.id == UUID(audit_id)))
    assert status is AuditStatus.succeeded_degraded
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
