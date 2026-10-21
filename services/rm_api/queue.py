"""Deferring background jobs from the API without importing the worker (jobs are addressed by task name)."""

import asyncio
from typing import Protocol
from uuid import UUID

import procrastinate
from procrastinate import exceptions as procrastinate_exceptions
from rm_contracts.jobs import (
    AUDIT_QUEUE,
    OPS_QUEUE,
    PROCESS_BILLING_EVENTS_TASK,
    RUN_AUDIT_TASK,
    RUN_INTERIOR_GENERATION_TASK,
    SEND_AUTH_MAIL_TASK,
    SEND_MAGIC_LINK_TASK,
)

OPEN_TIMEOUT_S = 10.0


class EmailQueue(Protocol):
    async def send_magic_link(self, *, email: str, url: str) -> None: ...

    async def send_auth_mail(self, *, kind: str, email: str, url: str | None) -> None:
        """Password-auth mail: `register` (with a link), `account_exists` (no link)."""
        ...

    async def process_billing_events(self) -> None:
        """Ask the ops worker to process pending billing events now (the sweeper is the guaranteed path)."""
        ...


class AuditQueue(Protocol):
    async def run_audit(self, audit_id: UUID) -> None: ...


class GenerationQueue(Protocol):
    async def run_interior_generation(self, generation_id: UUID) -> None: ...


class ProcrastinateEmailQueue:
    """GDPR[processor]: hands the recipient and the single-use link to the worker, which sends it via Resend
    (RM-12).

    The connection pool is opened on first use, never at startup: the API must boot and answer `/readyz`
    (reporting the failure) even when Postgres is down, so startup may not wait on the database.
    """

    def __init__(self, app: procrastinate.App) -> None:
        self._app = app
        self._open = False
        self._lock = asyncio.Lock()

    async def _ensure_open(self) -> None:
        if self._open:
            return
        async with self._lock:
            if not self._open:
                await asyncio.wait_for(self._app.open_async(), OPEN_TIMEOUT_S)
                self._open = True

    async def send_magic_link(self, *, email: str, url: str) -> None:
        await self._ensure_open()
        await self._app.configure_task(name=SEND_MAGIC_LINK_TASK, queue=OPS_QUEUE).defer_async(
            email=email, url=url
        )

    async def send_auth_mail(self, *, kind: str, email: str, url: str | None) -> None:
        await self._ensure_open()
        await self._app.configure_task(name=SEND_AUTH_MAIL_TASK, queue=OPS_QUEUE).defer_async(
            kind=kind, email=email, url=url
        )

    async def process_billing_events(self) -> None:
        await self._ensure_open()
        try:  # a lock makes a burst of notifications one job; the sweeper covers anything missed
            await self._app.configure_task(
                name=PROCESS_BILLING_EVENTS_TASK, queue=OPS_QUEUE, queueing_lock="billing-events"
            ).defer_async()
        except procrastinate_exceptions.AlreadyEnqueued:
            return

    async def run_audit(self, audit_id: UUID) -> None:
        """Defer the audit job. The lock makes a repeated defer of one audit a no-op; if this call fails after
        the audit row committed, the reconciler (#186) re-defers it."""
        await self._ensure_open()
        deferrer = self._app.configure_task(
            name=RUN_AUDIT_TASK, queue=AUDIT_QUEUE, queueing_lock=f"audit:{audit_id}"
        )
        try:
            await deferrer.defer_async(audit_id=str(audit_id))
        except procrastinate_exceptions.AlreadyEnqueued:
            return

    async def run_interior_generation(self, generation_id: UUID) -> None:
        """Defer one generation. The lock makes a repeated defer of one operation a no-op; if this fails
        after the row committed, the reconciler closes the operation at its deadline."""
        await self._ensure_open()
        deferrer = self._app.configure_task(
            name=RUN_INTERIOR_GENERATION_TASK,
            queue=OPS_QUEUE,
            queueing_lock=f"interior-generation:{generation_id}",
        )
        try:
            await deferrer.defer_async(generation_id=str(generation_id))
        except procrastinate_exceptions.AlreadyEnqueued:
            return

    async def close(self) -> None:
        if self._open:
            self._open = False
            await self._app.close_async()
