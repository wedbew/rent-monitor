"""The real curl_cffi transport against a local HTTP server: redirects, size cap, timeouts, headers."""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from rm_worker.clients.otodom import UpstreamBlocked
from rm_worker.clients.otodom_transport import CurlCffiTransport

pytestmark = [pytest.mark.integration]
Handler = Callable[[str], bytes | Awaitable[bytes]]


async def _serve(handler: Handler) -> tuple[asyncio.Server, str]:
    async def on_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request = await reader.readuntil(b"\r\n\r\n")
        path = request.split(b" ", 2)[1].decode()
        result = handler(path)
        data = await result if isinstance(result, Awaitable) else result
        writer.write(data)
        try:
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(on_conn, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"http://127.0.0.1:{port}"


def http(status: int, body: bytes = b"", **headers: str) -> bytes:
    head = f"HTTP/1.1 {status} X\r\nContent-Length: {len(body)}\r\nConnection: close\r\n"
    head += "".join(f"{k.replace('_', '-')}: {v}\r\n" for k, v in headers.items())
    return head.encode() + b"\r\n" + body


@pytest.fixture
async def local() -> AsyncIterator[Callable[[Handler], Awaitable[str]]]:
    servers: list[asyncio.Server] = []

    async def start(handler: Handler) -> str:
        server, base = await _serve(handler)
        servers.append(server)
        return base

    yield start
    for s in servers:
        s.close()
        await s.wait_closed()


async def test_returns_status_lowercased_headers_body_and_final_url(
    local: Callable[[Handler], Awaitable[str]],
) -> None:
    base = await local(lambda _p: http(200, b"hello", Retry_After="9", X_Thing="y"))
    raw = await CurlCffiTransport().get(f"{base}/pl/oferta/x", headers={"accept": "*/*"}, total_s=5)
    assert (raw.status, raw.body) == (200, b"hello")
    assert raw.headers["retry-after"] == "9"
    assert raw.final_url.endswith("/pl/oferta/x")


async def test_follows_redirects_and_reports_the_final_url(
    local: Callable[[Handler], Awaitable[str]],
) -> None:
    base = await local(lambda p: http(301, b"", Location="/final") if p != "/final" else http(200, b"ok"))
    raw = await CurlCffiTransport().get(f"{base}/start", headers={}, total_s=5)
    assert raw.status == 200
    assert raw.final_url.endswith("/final")


async def test_redirect_loops_are_bounded(local: Callable[[Handler], Awaitable[str]]) -> None:
    base = await local(lambda _p: http(302, b"", Location="/again"))
    with pytest.raises(UpstreamBlocked, match=r"transport error"):
        await CurlCffiTransport(max_redirects=3).get(f"{base}/x", headers={}, total_s=5)


async def test_oversized_bodies_are_cut_off(local: Callable[[Handler], Awaitable[str]]) -> None:
    base = await local(lambda _p: http(200, b"x" * 50_000))
    with pytest.raises(UpstreamBlocked, match="size cap") as err:
        await CurlCffiTransport(max_bytes=10_000).get(f"{base}/big", headers={}, total_s=5)
    assert err.value.retryable is False


async def test_slow_servers_time_out(local: Callable[[Handler], Awaitable[str]]) -> None:
    async def slow(_p: str) -> bytes:
        await asyncio.sleep(5)
        return http(200, b"late")

    base = await local(slow)
    started = time.monotonic()
    with pytest.raises(UpstreamBlocked, match=r"timeout|transport error"):
        await CurlCffiTransport().get(f"{base}/slow", headers={}, total_s=0.5)
    assert time.monotonic() - started < 3


async def test_a_server_that_drips_bytes_still_hits_the_total_deadline(
    local: Callable[[Handler], Awaitable[str]],
) -> None:
    async def on_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n")
        try:
            for _ in range(200):
                writer.write(b"x")
                await writer.drain()
                await asyncio.sleep(0.2)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(on_conn, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    started = time.monotonic()
    try:
        with pytest.raises(UpstreamBlocked, match=r"timeout|transport error"):
            await CurlCffiTransport().get(f"http://127.0.0.1:{port}/drip", headers={}, total_s=1.0)
    finally:
        server.close()
    assert time.monotonic() - started < 4


async def test_connection_refused_is_a_typed_error() -> None:
    with pytest.raises(UpstreamBlocked, match=r"transport error"):
        await CurlCffiTransport().get("http://127.0.0.1:1/x", headers={}, total_s=2)
