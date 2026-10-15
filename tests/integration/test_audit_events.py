# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
"""`GET /api/audits/{id}/events`: SSE progress with `audit_event` replay (#185, blueprint §2 wire format).

Real API, Postgres (rows and NOTIFY), Procrastinate worker and engine. httpx's ASGI transport returns a
response once the app has finished it, so a stream that ends (at `done` / `error`) is read whole; the
open-ended parts (keep-alive, lost wake-up, disconnect) are tested on the stream generator itself.
"""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from rm_api.sse import KEEP_ALIVE, ProgressHub, stream_events
from rm_core.db.models import AuditEvent
from rm_core.progress import emit_stage
from rm_worker.clients.otodom import ListingGone
from sqlalchemy import delete
from test_audit_journey import (  # noqa: F401  (fixtures: `h`, the autouse `clean_up`)
    SIGNUP_CREDITS,
    Harness,
    clean_up,
    h,
    new_ref,
    sale_ad,
    submit,
)
from test_audit_recovery import (  # noqa: F401  (fixture: `broken_queue`)
    PAST_DEADLINE_S,
    age,
    broken_queue,
    reconcile,
    submit_audit,
)
from test_auth import client_for
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]


def parse(body: str) -> list[dict[str, Any]]:
    """SSE text -> [{'id': int | None, 'event': str, 'data': dict}]; comment frames are skipped."""
    frames: list[dict[str, Any]] = []
    for raw in body.split("\n\n"):
        if not raw.strip() or raw.startswith(":"):
            continue
        fields = dict(line.split(": ", 1) for line in raw.split("\n") if ": " in line)
        frames.append(
            {
                "id": int(fields["id"]) if "id" in fields else None,
                "event": fields["event"],
                "data": json.loads(fields["data"]),
            }
        )
    return frames


async def events(c: Any, audit_id: str, **headers: str) -> tuple[Any, list[dict[str, Any]]]:
    r = await c.get(f"/api/audits/{audit_id}/events", headers=headers)
    return r, parse(r.text) if r.status_code == 200 else []


# ------------------------------------------------------------------------------ replay
async def test_a_finished_audit_replays_its_whole_story(h: Harness, make_google_token: MakeToken) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await h.run_worker()

    r, got = await events(c, audit_id)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-store"
    assert [(f["event"], f["data"]["stage"]) for f in got] == [
        ("progress", "fetch"),
        ("progress", "extract"),
        ("progress", "context"),
        ("progress", "synthesize"),
        ("progress", "persist"),
        ("done", "persist"),
    ]
    ids = [f["id"] for f in got]
    assert ids == sorted(set(ids))  # strictly increasing: the SSE id is the table's bigint
    assert [f["data"]["pct"] for f in got] == [5, 15, 25, 85, 95, 100]
    assert {f["data"]["audit_id"] for f in got} == {audit_id}
    done = got[-1]["data"]
    stored = await h.audit(audit_id)
    assert done["status"] == "succeeded_degraded"
    assert done["grade"] == stored.grade
    assert done["result_url"] == f"/api/audits/{audit_id}"
    assert done["warning"] == "VISION_UNAVAILABLE"
    assert "result" not in done  # the stream never carries the result or any listing text
    assert (await c.get(done["result_url"])).json()["status"] == "succeeded_degraded"  # done => row is final


async def test_a_reconnect_resumes_after_last_event_id(h: Harness, make_google_token: MakeToken) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await h.run_worker()
    _, all_frames = await events(c, audit_id)

    _, rest = await events(c, audit_id, **{"Last-Event-ID": str(all_frames[1]["id"])})
    assert [f["id"] for f in rest] == [f["id"] for f in all_frames[2:]]  # nothing repeated, nothing skipped

    r, none_left = await events(c, audit_id, **{"Last-Event-ID": str(all_frames[-1]["id"])})
    assert r.status_code == 200
    assert none_left == []  # it already saw `done`: the stream just ends

    _, junk = await events(c, audit_id, **{"Last-Event-ID": "not-a-number"})
    assert [f["id"] for f in junk] == [
        f["id"] for f in all_frames
    ]  # a bad cursor means replay from the start


async def test_a_live_stream_wakes_on_notify_and_ends_at_done(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    reader = asyncio.create_task(events(c, audit_id))  # connected while the audit is still queued
    await asyncio.sleep(0.5)
    assert not reader.done()
    started = time.monotonic()
    await h.run_worker()
    _, got = await asyncio.wait_for(reader, 10)
    assert time.monotonic() - started < 8  # woken by NOTIFY, not by the 15 s safety poll
    assert [f["event"] for f in got][-1] == "done"
    assert len(got) == 6


# ------------------------------------------------------------------------------ failures
async def test_a_failed_audit_ends_the_stream_with_an_error_event(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = ListingGone("404")
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker()
    _, got = await events(c, audit_id)
    assert [f["event"] for f in got] == ["progress", "error"]
    assert got[-1]["data"]["code"] == "LISTING_GONE"
    assert got[-1]["data"]["status"] == "failed_input"
    assert await h.balance(me["id"]) == SIGNUP_CREDITS  # the error event and the release are one transaction


async def test_a_rent_listing_streams_a_rejection_before_any_market_work(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad(adCategory={"type": "RENT"})
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker()
    _, got = await events(c, audit_id)
    assert [f["data"].get("stage") for f in got] == ["fetch", "extract", None]
    assert got[-1]["event"] == "error"
    assert got[-1]["data"]["code"] == "RENT_NOT_DEAL"


async def test_an_audit_the_reconciler_ended_streams_its_error(
    h: Harness, make_google_token: MakeToken, broken_queue: None
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await age(h, audit_id, seconds=PAST_DEADLINE_S, status="running")
    await reconcile(h)
    _, got = await events(c, audit_id)
    assert [f["event"] for f in got] == ["error"]
    assert got[0]["data"]["code"] == "TIMEOUT"


async def test_a_finished_audit_without_stored_events_still_reports_its_outcome(
    h: Harness, make_google_token: MakeToken
) -> None:
    """Rows older than the feature, or purged by retention: the outcome is synthesised from the audit row."""
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, c)
    await h.run_worker()
    async with h.sm() as s, s.begin():
        await s.execute(delete(AuditEvent).where(AuditEvent.audit_id == UUID(audit_id)))
    _, got = await events(c, audit_id)
    assert len(got) == 1
    assert (got[0]["event"], got[0]["id"], got[0]["data"]["status"]) == ("done", None, "succeeded_degraded")


# ------------------------------------------------------------------------------ tenancy
async def test_another_tenants_or_an_unknown_audit_is_a_404(h: Harness, make_google_token: MakeToken) -> None:
    a, _ = await sign_in(h.app, make_google_token)
    b, _ = await sign_in(h.app, make_google_token)
    audit_id = await submit_audit(h, a)
    await h.run_worker()
    assert (await events(a, audit_id))[0].status_code == 200
    foreign, unknown = (await events(b, audit_id))[0], (await events(b, str(UUID(int=7))))[0]
    assert foreign.status_code == unknown.status_code == 404  # never 403
    assert foreign.json()["code"] == unknown.json()["code"]  # indistinguishable from a missing audit
    anonymous = client_for(h.app)
    assert (await anonymous.get(f"/api/audits/{audit_id}/events")).status_code == 401


# ------------------------------------------------------------------------------ the generator itself
async def collect(gen: Any, limit_s: float) -> list[str]:
    out: list[str] = []

    async def run() -> None:
        async for chunk in gen:
            out.append(chunk)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(run(), limit_s)
    return out


async def never_disconnected() -> bool:
    return False


async def test_a_lost_notification_is_caught_by_the_safety_poll(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = UUID(await submit_audit(h, c))
    hub = ProgressHub()  # nobody feeds it: every NOTIFY is "lost"

    async def late_event() -> None:
        await asyncio.sleep(0.4)
        async with h.sm() as db, db.begin():
            await emit_stage(db, audit_id, "fetch")

    gen = stream_events(h.sm, hub, audit_id, max_seconds=30, poll_s=0.1, is_disconnected=never_disconnected)
    writer = asyncio.create_task(late_event())
    chunks = await collect(gen, 1.5)
    await writer
    assert KEEP_ALIVE in chunks  # idle polls keep proxies from closing the connection
    assert any("event: progress" in c and '"stage":"fetch"' in c for c in chunks)  # found by the poll alone


async def test_a_stream_ends_at_its_time_limit_and_on_disconnect_and_leaves_no_subscription(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    audit_id = UUID(await submit_audit(h, c))
    hub = ProgressHub()
    limited = [
        x
        async for x in stream_events(
            h.sm, hub, audit_id, max_seconds=0.3, poll_s=0.1, is_disconnected=never_disconnected
        )
    ]
    assert limited
    assert set(limited) == {KEEP_ALIVE}  # nothing happened; it ended by itself at the limit

    async def gone() -> bool:
        return True

    assert [x async for x in stream_events(h.sm, hub, audit_id, max_seconds=30, is_disconnected=gone)] == []
    assert hub._waiters == {}
