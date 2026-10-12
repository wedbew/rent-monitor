"""Better Stack heartbeat pings (docs/OBSERVABILITY-SPEC.md section 4).

A heartbeat URL carries its own secret, so it is held as a `SecretStr`, never logged, and a failed ping
never raises
into the job it reports on: the monitoring must not break the thing it monitors. GDPR[processor]: Better Stack
receives only the fact that a job ran; no personal data is sent.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx
import structlog

log = structlog.get_logger(__name__)
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class HeartbeatSink(Protocol):
    async def ping(self, *, ok: bool = True) -> bool: ...


@dataclass
class Heartbeat:
    """Pings `url` on success and `url/fail` on failure. An empty URL means monitoring is off: no call, no
    error."""

    http: httpx.AsyncClient
    url: str
    name: str

    async def ping(self, *, ok: bool = True) -> bool:
        if not self.url:
            return False
        target = self.url.rstrip("/") + ("" if ok else "/fail")
        try:
            response = await self.http.get(target, timeout=TIMEOUT)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("heartbeat_failed", heartbeat=self.name, error=type(exc).__name__)  # never the URL
            return False
        return True
