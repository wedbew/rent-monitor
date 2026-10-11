"""API lifespan, readiness against a real database, and the one-session-per-request dependency."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from rm_api.app import create_app
from rm_api.deps import SessionDep
from rm_api.problems import Problem
from rm_contracts.problems import ProblemCode
from rm_core.settings import Settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration]


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")


@pytest.fixture
async def app(migrated_url: str, procrastinate_schema: None) -> AsyncIterator[FastAPI]:
    application = create_app(Settings(app_env="test", database_url=migrated_url))

    @application.post("/t/user/{email}")
    async def create_user(email: str, session: SessionDep, fail: bool = False) -> dict[str, str]:
        await session.execute(
            text("INSERT INTO app.app_user (id, email) VALUES (:i, :e)"), {"i": str(uuid4()), "e": email}
        )
        if fail:
            raise Problem(409, ProblemCode.AUDIT_IN_PROGRESS, "boom")
        return {"email": email}

    @application.post("/t/crash/{email}")
    async def crash(email: str, session: SessionDep) -> None:
        await session.execute(
            text("INSERT INTO app.app_user (id, email) VALUES (:i, :e)"), {"i": str(uuid4()), "e": email}
        )
        raise RuntimeError("after write")

    async with LifespanManager(application):
        yield application


async def _exists(engine: AsyncEngine, email: str) -> bool:
    async with engine.connect() as conn:
        return bool(
            await conn.scalar(text("SELECT count(*) FROM app.app_user WHERE email = :e"), {"e": email})
        )


async def test_readyz_is_ok_with_database_and_queue_schema(app: FastAPI) -> None:
    async with _client(app) as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"db": "ok", "queue": "ok"}}


async def test_readyz_fails_fast_when_the_database_is_unreachable() -> None:
    dead = create_app(Settings(app_env="test", database_url="postgresql+psycopg://u:p@127.0.0.1:1/none"))
    async with LifespanManager(dead), _client(dead) as c:
        r = await c.get("/readyz")
    assert r.status_code == 503
    assert r.json()["code"] == "NOT_READY"
    assert r.json()["checks"] == {"db": "fail", "queue": "fail"}
    assert "127.0.0.1" not in r.text


async def test_session_dependency_commits_on_success(app: FastAPI, engine: AsyncEngine) -> None:
    email = f"{uuid4().hex}@example.test"
    async with _client(app) as c:
        r = await c.post(f"/t/user/{email}")
    assert r.status_code == 200
    try:
        assert await _exists(engine, email)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.app_user WHERE email = :e"), {"e": email})


async def test_session_dependency_rolls_back_on_problem_and_on_crash(
    app: FastAPI, engine: AsyncEngine
) -> None:
    e1, e2 = f"{uuid4().hex}@example.test", f"{uuid4().hex}@example.test"
    async with _client(app) as c:
        r1 = await c.post(f"/t/user/{e1}", params={"fail": "true"})
        r2 = await c.post(f"/t/crash/{e2}")
    assert r1.status_code == 409
    assert r2.status_code == 500
    assert not await _exists(engine, e1)
    assert not await _exists(engine, e2)


async def test_lifespan_disposes_the_engine_and_client(migrated_url: str) -> None:
    application = create_app(Settings(app_env="test", database_url=migrated_url))
    async with LifespanManager(application):
        client = application.state.http_client
        assert not client.is_closed
    assert client.is_closed
