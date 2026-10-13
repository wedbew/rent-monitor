"""Audit progress events (blueprint §2 *SSE wire format*, §4.5 b; #185).

`audit_event` is the truth: an append-only table whose bigint `id` is the SSE `id`. A `pg_notify` in the same
transaction is only a wake-up for the API processes (delivered on commit, so a listener never wakes for a row
it cannot yet read); a lost wake-up is covered by the stream's safety poll and replay from `Last-Event-ID`.

Writers: the worker pipeline (stages, `done`, `error`) and the reconciler (`error` for an audit it ended). The
terminal event is written in the same transaction as the terminal status and the credit settlement, so a
client that sees `done` or `error` can trust the audit row and the charge already agree.

Payloads never contain listing text, personal data or the result itself, only ids, stage names, status and
problem codes.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import AuditEvent

CHANNEL = "audit_progress"
KIND_PROGRESS = "progress"
KIND_DONE = "done"
KIND_ERROR = "error"
TERMINAL_KINDS = frozenset({KIND_DONE, KIND_ERROR})

# Fixed stage percentages (CONTEXT.md §7). A stage the pipeline does not run yet (vision, ocr, anchors) is
# simply never emitted.
STAGE_PCT = {
    "fetch": 5,
    "extract": 15,
    "context": 25,
    "vision": 35,
    "ocr": 60,
    "anchors": 70,
    "synthesize": 85,
    "persist": 95,
}


async def emit(
    db: AsyncSession,
    audit_id: UUID,
    *,
    kind: str,
    stage: str | None = None,
    pct: int | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    """Append one event and wake listeners on commit. Returns the event id. Call inside the caller's
    transaction (the caller commits)."""
    event = AuditEvent(audit_id=audit_id, kind=kind, stage=stage, pct=pct, payload=payload or {})
    db.add(event)
    await db.flush()
    await db.execute(select(func.pg_notify(CHANNEL, f"{audit_id}:{event.id}")))
    return event.id


async def emit_stage(db: AsyncSession, audit_id: UUID, stage: str, message: str = "") -> int:
    return await emit(
        db, audit_id, kind=KIND_PROGRESS, stage=stage, pct=STAGE_PCT[stage], payload={"message": message}
    )
