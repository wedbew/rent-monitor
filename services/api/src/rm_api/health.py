"""Liveness and readiness (blueprint §2, §4.7).

`/healthz` and `/readyz` are internal only: Caddy blocks them externally.
"""

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from rm_contracts.problems import ProblemCode
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from rm_api.problems import problem_response

router = APIRouter()
CHECK_TIMEOUT_S = 2.0
log = structlog.get_logger(__name__)


@router.get("/api/health", include_in_schema=False)
async def public_health() -> dict[str, str]:
    """Public liveness for the uptime monitor; touches no database (blueprint §4.7)."""
    return {"status": "ok"}


@router.get("/healthz", include_in_schema=False)
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


async def _check_db(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_queue(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        ok = await conn.scalar(text("SELECT to_regclass('public.procrastinate_jobs') IS NOT NULL"))
    if not ok:
        raise RuntimeError("procrastinate schema is not applied")


async def _run(name: str, check: Callable[[AsyncEngine], Awaitable[None]], engine: AsyncEngine) -> bool:
    try:
        await asyncio.wait_for(check(engine), CHECK_TIMEOUT_S)
    except Exception as exc:
        log.warning("readiness_check_failed", check=name, error_type=type(exc).__name__)
        return False
    return True


@router.get("/readyz", include_in_schema=False)
async def readiness(request: Request) -> JSONResponse:
    engine: AsyncEngine | None = request.app.state.engine
    if engine is None:
        results = {"db": False, "queue": False}
    else:
        db_ok, queue_ok = await asyncio.gather(
            _run("db", _check_db, engine), _run("queue", _check_queue, engine)
        )
        results = {"db": db_ok, "queue": queue_ok}
    checks = {name: "ok" if ok else "fail" for name, ok in results.items()}
    if all(results.values()):
        return JSONResponse({"status": "ok", "checks": checks})
    return problem_response(
        request,
        status=503,
        code=ProblemCode.NOT_READY,
        title="Not ready",
        checks=checks,
    )
