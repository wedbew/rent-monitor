"""`curl_cffi` transport with browser TLS impersonation, timeouts and a response size cap.

LEGAL[scraping]: browser-like TLS/HTTP fingerprint when fetching a third-party site (RM-22).
"""

import asyncio
import contextlib
from typing import Any

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from rm_worker.clients.otodom import CONNECT_TIMEOUT_S, MAX_BODY_BYTES, RawResponse, UpstreamBlocked

# curl_cffi ships partial type information: treat it as an untyped boundary, convert to our own types at once.
_Session: Any = AsyncSession


class CurlCffiTransport:
    def __init__(
        self, impersonate: str = "chrome", max_redirects: int = 3, max_bytes: int = MAX_BODY_BYTES
    ) -> None:
        self._impersonate = impersonate
        self._max_redirects = max_redirects
        self._max_bytes = max_bytes

    async def get(self, url: str, *, headers: dict[str, str], total_s: float) -> RawResponse:
        """`total_s` is the TOTAL budget.

        curl_cffi's stream mode only applies a low-speed timeout, so a server that drips bytes never times
        out on its own; the outer `asyncio.timeout` is the hard deadline.
        """
        total = max(total_s, 0.1)
        try:
            async with asyncio.timeout(total):
                return await self._get(url, headers, total)
        except TimeoutError as exc:
            raise UpstreamBlocked("request exceeded its total timeout") from exc
        except RequestException as exc:
            raise UpstreamBlocked(f"transport error: {type(exc).__name__}") from exc

    async def _get(self, url: str, headers: dict[str, str], total: float) -> RawResponse:
        async with _Session(impersonate=self._impersonate) as session:
            response = await session.request(
                "GET",
                url,
                headers=headers,
                timeout=(min(CONNECT_TIMEOUT_S, total), total),
                max_redirects=self._max_redirects,
                allow_redirects=True,
                stream=True,
            )
            try:
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_content():
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise UpstreamBlocked("response exceeds the size cap", retryable=False)
                    chunks.append(bytes(chunk))
                return RawResponse(
                    status=int(response.status_code),
                    headers={str(k).lower(): str(v) for k, v in response.headers.items()},
                    body=b"".join(chunks),
                    final_url=str(response.url),
                )
            finally:
                # `aclose()` waits for the stream task, which a slow server can stretch indefinitely:
                # cancel it first so the connection is dropped now.
                task = response.astream_task
                if task is not None:
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await response.aclose()
