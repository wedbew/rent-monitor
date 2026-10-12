"""Unsafe methods on /api/* need Origin == PUBLIC_APP_URL (agents.md section 4)."""

import pytest
from httpx import ASGITransport, AsyncClient
from rm_api.origin import OriginCheckMiddleware
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def ok(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def client() -> AsyncClient:
    routes = [
        Route(path, ok, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
        for path in ("/api/things", "/api/webhooks/stripe", "/healthz", "/other")
    ]
    app = Starlette(routes=routes)
    app.add_middleware(OriginCheckMiddleware, allowed_origin="https://app.example.test/")
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://app.example.test")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_unsafe_methods_without_an_origin_are_refused(method: str) -> None:
    async with client() as c:
        r = await c.request(method, "/api/things")
    assert r.status_code == 403
    assert r.json()["code"] == "ORIGIN_NOT_ALLOWED"
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example.test", "http://app.example.test", "https://app.example.test.evil.test", "null"],
)
async def test_a_foreign_origin_is_refused(origin: str) -> None:
    async with client() as c:
        r = await c.post("/api/things", headers={"Origin": origin})
    assert r.status_code == 403


@pytest.mark.parametrize(
    "origin", ["https://app.example.test", "https://APP.example.test/", "https://app.example.test/"]
)
async def test_the_configured_origin_passes_whatever_the_case_or_trailing_slash(origin: str) -> None:
    async with client() as c:
        r = await c.post("/api/things", headers={"Origin": origin})
    assert r.status_code == 200


async def test_safe_methods_never_need_an_origin() -> None:
    async with client() as c:
        assert (await c.get("/api/things")).status_code == 200
        assert (await c.head("/api/things")).status_code in {200, 405}


async def test_routes_outside_api_are_not_checked() -> None:
    async with client() as c:
        assert (await c.post("/other")).status_code == 200


async def test_webhooks_are_exempt_because_they_authenticate_by_signature() -> None:
    async with client() as c:
        assert (await c.post("/api/webhooks/stripe")).status_code == 200
