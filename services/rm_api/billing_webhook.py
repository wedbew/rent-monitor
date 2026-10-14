"""`POST /api/webhooks/paddle`: durable receipt of Paddle notifications (docs/PADDLE-INTEGRATION.md section
5).

Order, and why: cap the body, verify the signature on the **raw bytes**, then parse; store the event
(unique by environment and event id) and commit; only then try to wake a worker. Duplicates answer 200.
A database failure answers 5xx so Paddle retries; a failed wake-up changes nothing because the worker's
sweeper finds the pending row. Nothing here calls Paddle, grants anything or reads the notification body
for amounts: processing starts from a fresh read of the transaction (`rm_core.billing_events`). This is
the only route exempt from the Origin check, and only by exact path; it authenticates by signature
instead."""

import json
from datetime import datetime
from typing import Any, cast

import structlog
from fastapi import APIRouter, Request, Response
from rm_contracts.problems import ProblemCode
from rm_core.billing_events import record_event
from rm_core.paddle_webhook import InvalidSignatureError, verify
from starlette.responses import JSONResponse

from rm_api.deps import SessionDep, SettingsDep
from rm_api.problems import Problem

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["billing"], include_in_schema=False)
MAX_BODY_BYTES = 256 * 1024


async def _read_capped(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdecimal() and int(declared) > MAX_BODY_BYTES:
        raise Problem(413, ProblemCode.VALIDATION_ERROR, "Request body too large")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            raise Problem(413, ProblemCode.VALIDATION_ERROR, "Request body too large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/paddle")
async def paddle_webhook(request: Request, db: SessionDep, settings: SettingsDep) -> Response:
    secrets = [
        settings.paddle_webhook_secret.get_secret_value(),
        settings.paddle_webhook_secret_previous.get_secret_value(),
    ]
    catalog = request.app.state.catalog
    if catalog is None or not secrets[0]:
        raise Problem(503, ProblemCode.BILLING_UNAVAILABLE, "Notifications are not accepted")
    body = await _read_capped(request)
    try:
        verify(
            request.headers.get("paddle-signature"),
            body,
            secrets,
            tolerance_s=settings.paddle_webhook_tolerance_s,
        )
    except InvalidSignatureError:
        log.warning("paddle_webhook_rejected")
        raise Problem(400, ProblemCode.INVALID_WEBHOOK_SIGNATURE, "Invalid signature") from None
    try:  # signed, so Paddle sent it; a malformed one is still not stored
        event = cast("dict[str, Any]", _parse(body))
        occurred = datetime.fromisoformat(str(event["occurred_at"])) if event.get("occurred_at") else None
        event["occurred_at"] = occurred
        if not isinstance(event.get("event_id"), str) or not isinstance(event.get("event_type"), str):
            raise ValueError("event_id and event_type are required")
    except (ValueError, KeyError, TypeError):
        raise Problem(400, ProblemCode.VALIDATION_ERROR, "Malformed notification") from None
    received = await record_event(db, environment=str(catalog.environment), event=event)
    await db.commit()  # durable before we answer
    if not received.duplicate:
        try:
            await request.app.state.email_queue.process_billing_events()
        except Exception:
            log.exception("billing_wakeup_failed")  # the sweeper finds the pending row
    return JSONResponse({"received": True})


def _parse(body: bytes) -> object:
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("not an object")
    return cast("dict[str, Any]", value)
