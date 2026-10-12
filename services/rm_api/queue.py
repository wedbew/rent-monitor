"""Deferring background jobs from the API without importing the worker (jobs are addressed by task name)."""

import asyncio
from typing import Protocol

import procrastinate
from rm_contracts.jobs import OPS_QUEUE, SEND_MAGIC_LINK_TASK

OPEN_TIMEOUT_S = 10.0


class EmailQueue(Protocol):
    async def send_magic_link(self, *, email: str, url: str) -> None: ...


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

    async def close(self) -> None:
        if self._open:
            self._open = False
            await self._app.close_async()
