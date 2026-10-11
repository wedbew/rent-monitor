"""Application factory and lifespan-owned singletons (blueprint §2 "Process model and state")."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.logging import configure_logging
from rm_core.observability import init_sentry
from rm_core.settings import Settings, get_settings

from rm_api.health import router as health_router
from rm_api.middleware import RequestContextMiddleware
from rm_api.problems import install_problem_handlers

log = structlog.get_logger(__name__)
HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HTTP_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=10)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    init_sentry(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        engine = make_engine(settings) if settings.database_url else None
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine) if engine else None
        app.state.http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT, limits=HTTP_LIMITS)
        log.info("startup", env=settings.app_env, database=engine is not None)
        try:
            yield
        finally:
            await app.state.http_client.aclose()
            if engine is not None:
                await engine.dispose()
            log.info("shutdown")

    app = FastAPI(
        title="RentMonitor API",
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.app_env == "production" else "/api/openapi.json",
    )
    app.state.engine = None  # replaced by the lifespan; set so dependencies work without one
    app.state.sessionmaker = None
    app.state.http_client = None
    app.add_middleware(RequestContextMiddleware)
    install_problem_handlers(app)
    app.include_router(health_router)
    return app
