"""One LISTEN connection per API process, shared by every subscriber (session revocation now, the SSE hub
later).

Counts as one connection in the budget (blueprint §6). If the connection drops, subscribers are told to treat
everything as stale (`on_reconnect`) because notifications sent meanwhile are lost; the principal cache TTL
(30 s)
is the stated fallback bound.
"""

import asyncio
import contextlib
from collections.abc import Callable, Sequence

import psycopg
import structlog
from psycopg import sql

log = structlog.get_logger(__name__)
CONNECT_TIMEOUT_S = 5
MAX_BACKOFF_S = 30.0


class NotifyListener:
    def __init__(self, dsn: str, channels: Sequence[str]) -> None:
        self._dsn = dsn
        self._channels = tuple(channels)
        self._subscribers: dict[str, list[Callable[[str], None]]] = {c: [] for c in channels}
        self._on_reconnect: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self.listening = asyncio.Event()  # set while LISTEN is active; tests and readiness can wait on it

    def subscribe(self, channel: str, callback: Callable[[str], None]) -> None:
        self._subscribers[channel].append(callback)

    def on_reconnect(self, callback: Callable[[], None]) -> None:
        self._on_reconnect.append(callback)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="notify-listener")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.listening.clear()

    async def _run(self) -> None:
        backoff = 1.0
        first = True
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self._dsn, autocommit=True, connect_timeout=CONNECT_TIMEOUT_S
                ) as conn:
                    for channel in self._channels:
                        await conn.execute(sql.SQL("LISTEN {}").format(sql.Identifier(channel)))
                    if not first:
                        self._fire_reconnect()
                    first = False
                    backoff = 1.0
                    self.listening.set()
                    log.info("notify_listening", channels=list(self._channels))
                    async for note in conn.notifies():
                        for callback in self._subscribers.get(note.channel, ()):
                            try:
                                callback(note.payload)
                            except Exception:
                                log.exception("notify_callback_failed", channel=note.channel)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.listening.clear()
                log.warning("notify_connection_lost", error=type(exc).__name__, retry_in_s=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_S)
                first = False  # the next successful connect must flush caches

    def _fire_reconnect(self) -> None:
        for callback in self._on_reconnect:
            try:
                callback()
            except Exception:
                log.exception("notify_reconnect_callback_failed")
