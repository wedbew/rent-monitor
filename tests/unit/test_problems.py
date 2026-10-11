import json
import re
from collections.abc import AsyncIterator

import pytest
import sentry_sdk
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict
from rm_api.app import create_app
from rm_api.problems import Problem
from rm_contracts.problems import ProblemCode
from rm_core.settings import Settings


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


def _app() -> FastAPI:
    app = create_app(Settings(app_env="test", database_url="", log_json=True))

    @app.get("/t/problem")
    async def raise_problem() -> None:
        raise Problem(402, ProblemCode.QUOTA_EXHAUSTED, "Quota exhausted", upgrade_url="/billing")

    @app.get("/t/foreign")
    async def foreign() -> None:
        raise Problem.not_found("Audit")

    @app.get("/t/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals: password=hunter2")

    @app.post("/t/body")
    async def body(payload: Body) -> dict[str, int]:
        return {"count": payload.count}

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_problem_shape_is_rfc9457_with_stable_code(client: AsyncClient) -> None:
    r = await client.get("/t/problem")
    assert r.status_code == 402
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["code"] == "QUOTA_EXHAUSTED"
    assert body["status"] == 402
    assert body["title"] == "Quota exhausted"
    assert body["type"] == "urn:rentmonitor:problem:QUOTA_EXHAUSTED"
    assert body["instance"] == "/t/problem"
    assert body["upgrade_url"] == "/billing"
    assert body["request_id"] == r.headers["x-request-id"]


async def test_foreign_resource_is_404_not_403(client: AsyncClient) -> None:
    r = await client.get("/t/foreign")
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"
    assert r.json()["title"] == "Audit not found"


async def test_unknown_route_is_a_404_problem(client: AsyncClient) -> None:
    r = await client.get("/nope")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["code"] == "NOT_FOUND"


async def test_wrong_method_is_an_http_error_problem(client: AsyncClient) -> None:
    r = await client.delete("/t/problem")
    assert r.status_code == 405
    assert r.json()["code"] == "HTTP_ERROR"


async def test_validation_errors_do_not_echo_input(client: AsyncClient) -> None:
    r = await client.post("/t/body", json={"count": "not-a-number-SECRET", "extra": "SECRET2"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert {e["type"] for e in body["errors"]} >= {"int_parsing", "extra_forbidden"}
    assert "SECRET" not in json.dumps(body)


async def test_unhandled_exception_is_a_generic_500_and_reported(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[BaseException] = []
    monkeypatch.setattr(sentry_sdk, "capture_exception", lambda exc=None, **_: captured.append(exc))  # type: ignore[arg-type]
    r = await client.get("/t/boom")
    assert r.status_code == 500
    assert r.json()["code"] == "INTERNAL"
    assert "hunter2" not in r.text
    assert r.headers["x-request-id"] == r.json()["request_id"]
    assert len(captured) == 1


async def test_request_id_is_echoed_when_valid_and_replaced_when_not(client: AsyncClient) -> None:
    ok = await client.get("/api/health", headers={"x-request-id": "abc-12345678"})
    assert ok.headers["x-request-id"] == "abc-12345678"
    for bad in ("short", "x" * 65, "has space in it!!"):
        r = await client.get("/api/health", headers={"x-request-id": bad})
        assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-request-id"])


async def test_liveness_endpoints_touch_no_database(client: AsyncClient) -> None:
    for path in ("/api/health", "/healthz"):
        r = await client.get(path)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


async def test_readyz_without_a_database_is_503(client: AsyncClient) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["code"] == "NOT_READY"
    assert r.json()["checks"] == {"db": "fail", "queue": "fail"}
