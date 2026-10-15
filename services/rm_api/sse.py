"""Server-sent progress for one audit (blueprint §2 *SSE wire format*, §4.5 b; #185).

`audit_event` rows are the truth; NOTIFY is a wake-up. The stream replays every event after the client's
`Last-Event-ID`, then waits for a wake-up (or a safety poll) and reads again, so a reconnect, a lost
notification or a listener restart can delay an event but never lose one. The terminal event (`done` or
`error`) ends the stream. A finished audit with no stored terminal event (rows older than this feature, or
purged by retention) gets one synthesised from the audit row, so a late client always learns the outcome.

Connections: the stream holds no database session while it waits (each read is a short session), and every
process shares the one LISTEN connection of `NotifyListener` (blueprint §6 budget).
"""

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

import structlog
from rm_core.db.models import Audit, AuditEvent, AuditStatus
from rm_core.progress import KIND_DONE, KIND_ERROR, TERMINAL_KINDS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = structlog.get_logger(__name__)
POLL_S = 15.0  # safety poll and keep-alive interval
BATCH = 200
SUCCESS = (AuditStatus.succeeded, AuditStatus.succeeded_degraded)
ACTIVE = (AuditStatus.queued, AuditStatus.running)


class ProgressHub:
    """Fan-out of the shared NOTIFY connection to the streams of this process. An `asyncio.Event` per stream
    coalesces wake-ups, so a burst can never overflow anything."""

    def __init__(self) -> None:
        self._waiters: dict[str, set[asyncio.Event]] = defaultdict(set)

    def on_notify(self, payload: str) -> None:  # payload = "<audit_id>:<event_id>"
        for event in self._waiters.get(payload.split(":", 1)[0], ()):
            event.set()

    def wake_all(self) -> None:
        """The LISTEN connection was re-established: notifications sent meanwhile are lost, so re-read."""
        for events in self._waiters.values():
            for event in events:
                event.set()

    def subscribe(self, audit_id: UUID) -> asyncio.Event:
        event = asyncio.Event()
        self._waiters[str(audit_id)].add(event)
        return event

    def unsubscribe(self, audit_id: UUID, event: asyncio.Event) -> None:
        waiters = self._waiters.get(str(audit_id))
        if waiters is not None:
            waiters.discard(event)
            if not waiters:
                del self._waiters[str(audit_id)]


def frame(event_id: int | None, kind: str, data: dict[str, object]) -> str:
    out = f"id: {event_id}\n" if event_id is not None else ""
    return out + f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'), ensure_ascii=False)}\n\n"


KEEP_ALIVE = ": keep-alive\n\n"


def _data(audit_id: UUID, ev: AuditEvent) -> dict[str, object]:
    return {"audit_id": str(audit_id), "stage": ev.stage, "pct": ev.pct, **ev.payload}


async def _read(sm: async_sessionmaker[AsyncSession], audit_id: UUID, cursor: int) -> list[AuditEvent]:
    async with sm() as db:
        rows = await db.scalars(
            select(AuditEvent)
            .where(AuditEvent.audit_id == audit_id, AuditEvent.id > cursor)
            .order_by(AuditEvent.id)
            .limit(BATCH)
        )
        return list(rows)


async def _outcome(
    sm: async_sessionmaker[AsyncSession], audit_id: UUID
) -> tuple[AuditStatus, str | None] | None:
    async with sm() as db:
        row = (
            await db.execute(select(Audit.status, Audit.error_code).where(Audit.id == audit_id))
        ).one_or_none()
    return None if row is None else (row[0], row[1])


async def _terminal_synthesised(
    sm: async_sessionmaker[AsyncSession], audit_id: UUID, cursor: int
) -> str | None:
    """A frame for a finished audit whose terminal event is not in the table (and not already delivered)."""
    outcome = await _outcome(sm, audit_id)
    if outcome is None or outcome[0] in ACTIVE:
        return None
    status, code = outcome
    async with sm() as db:
        delivered = await db.scalar(
            select(AuditEvent.id)
            .where(AuditEvent.audit_id == audit_id, AuditEvent.kind.in_(TERMINAL_KINDS))
            .limit(1)
        )
    if delivered is not None:
        return None  # it exists: the normal path sends it (or the client already has it)
    if status in SUCCESS:
        done: dict[str, object] = {"audit_id": str(audit_id), "status": status.value}
        done["result_url"] = f"/api/audits/{audit_id}"
        return frame(None, KIND_DONE, done)
    return frame(None, KIND_ERROR, {"audit_id": str(audit_id), "status": status.value, "code": code})


async def stream_events(
    sm: async_sessionmaker[AsyncSession],
    hub: ProgressHub,
    audit_id: UUID,
    *,
    last_event_id: int = 0,
    max_seconds: float,
    poll_s: float = POLL_S,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    cursor = last_event_id
    wake = hub.subscribe(audit_id)
    deadline = asyncio.get_running_loop().time() + max_seconds
    try:
        while not await is_disconnected():
            wake.clear()  # before reading, so a notification during the read is not lost
            events = await _read(sm, audit_id, cursor)
            for ev in events:
                cursor = ev.id
                yield frame(ev.id, ev.kind, _data(audit_id, ev))
                if ev.kind in TERMINAL_KINDS:
                    return
            if not events:
                final = await _terminal_synthesised(sm, audit_id, cursor)
                if final is not None:
                    yield final
                    return
                outcome = await _outcome(sm, audit_id)
                if outcome is not None and outcome[0] not in ACTIVE:
                    return  # finished, and the client has already seen its terminal event
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return  # the client reconnects with Last-Event-ID
            try:
                await asyncio.wait_for(wake.wait(), timeout=min(poll_s, remaining))
            except TimeoutError:
                yield KEEP_ALIVE
    finally:
        hub.unsubscribe(audit_id, wake)
