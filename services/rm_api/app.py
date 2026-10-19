"""Application factory and lifespan-owned singletons (blueprint §2 "Process model and state")."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
import procrastinate
import structlog
from fastapi import FastAPI
from rm_core.billing import sync_catalog
from rm_core.billing_catalog import Catalog, CatalogError, load_catalog
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.logging import configure_logging
from rm_core.observability import init_sentry
from rm_core.paddle import PaddleClient, PaddleError, build_paddle_client
from rm_core.progress import CHANNEL as PROGRESS_CHANNEL
from rm_core.settings import Settings, get_settings

from rm_api.admin import router as admin_router
from rm_api.audits import router as audits_router
from rm_api.auth.google import GoogleCerts, GoogleVerifier
from rm_api.auth.password import router as password_router
from rm_api.auth.router import router as auth_router
from rm_api.auth.sessions import REVOKED_CHANNEL, PrincipalCache
from rm_api.billing import router as billing_router
from rm_api.billing_erasure import BillingEraser
from rm_api.billing_webhook import router as billing_webhook_router
from rm_api.health import router as health_router
from rm_api.market import router as market_router
from rm_api.me import router as me_router
from rm_api.media import router as media_router
from rm_api.middleware import RequestContextMiddleware
from rm_api.notify import NotifyListener
from rm_api.origin import OriginCheckMiddleware
from rm_api.problem_docs import install_problem_docs
from rm_api.problems import build_route_table, install_problem_handlers
from rm_api.queue import AuditQueue, EmailQueue, ProcrastinateEmailQueue
from rm_api.saved import router as saved_router
from rm_api.sse import ProgressHub

log = structlog.get_logger(__name__)
HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HTTP_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=10)


async def _init_billing(
    app: FastAPI, settings: Settings, client: PaddleClient | None, catalog: Catalog | None
) -> None:
    """Sales are off unless the owner-approved catalog loads and a client for the matching environment exists.
    A broken catalog is logged loudly and leaves billing disabled; it never stops the API from starting."""
    app.state.paddle, app.state.catalog = None, None
    try:
        catalog = catalog or load_catalog(settings)
        client = client or build_paddle_client(settings)
    except (CatalogError, PaddleError):
        log.exception("billing_disabled")
        return
    if catalog is None or client is None or app.state.sessionmaker is None:
        return
    async with app.state.sessionmaker() as session, session.begin():
        await sync_catalog(session, catalog)
    app.state.paddle, app.state.catalog = client, catalog
    log.info("billing_enabled", environment=catalog.environment, packs=len(catalog.packs))


def _start_listener(app: FastAPI, dsn: str) -> NotifyListener:
    """The one LISTEN connection of this process: session revocation and audit progress wake-ups."""
    listener = NotifyListener(dsn, [REVOKED_CHANNEL, PROGRESS_CHANNEL])
    listener.subscribe(REVOKED_CHANNEL, app.state.principal_cache.on_notify)
    listener.on_reconnect(app.state.principal_cache.clear)  # missed notifications: treat all as stale
    listener.subscribe(PROGRESS_CHANNEL, app.state.progress_hub.on_notify)
    listener.on_reconnect(app.state.progress_hub.wake_all)  # streams re-read from the table
    listener.start()
    return listener


def create_app(
    settings: Settings | None = None,
    *,
    email_queue: EmailQueue | None = None,
    audit_queue: AuditQueue | None = None,
    google_verifier: GoogleVerifier | None = None,
    billing_eraser: BillingEraser | None = None,
    paddle_client: PaddleClient | None = None,
    catalog: Catalog | None = None,
) -> FastAPI:
    """`email_queue`, `audit_queue` and `google_verifier` are test seams; production builds them in the
    lifespan."""
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    init_sentry(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        engine = make_engine(settings) if settings.database_url else None
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine) if engine else None
        app.state.http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT, limits=HTTP_LIMITS)
        app.state.google_verifier = google_verifier or GoogleVerifier(
            settings.google_client_id, GoogleCerts(app.state.http_client)
        )
        jobs: ProcrastinateEmailQueue | None = None
        if email_queue is None and settings.psycopg_dsn:
            # Two connections at most, opened on first use: the API only defers jobs (blueprint §6 budget).
            jobs = ProcrastinateEmailQueue(
                procrastinate.App(
                    connector=procrastinate.PsycopgConnector(
                        conninfo=settings.psycopg_dsn, min_size=1, max_size=2
                    )
                )
            )
        app.state.email_queue = email_queue or jobs or _NoQueue()
        app.state.audit_queue = audit_queue or jobs or _NoQueue()
        listener = _start_listener(app, settings.psycopg_dsn) if settings.psycopg_dsn else None
        app.state.notify_listener = listener
        await _init_billing(app, settings, paddle_client, catalog)
        log.info("startup", env=settings.app_env, database=engine is not None)
        try:
            yield
        finally:
            if listener is not None:
                await listener.stop()
            if jobs is not None:
                await jobs.close()
            await app.state.http_client.aclose()
            if engine is not None:
                await engine.dispose()
            log.info("shutdown")

    app = FastAPI(
        title=f"{settings.app_name} API",
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.app_env == "production" else "/api/openapi.json",
    )
    app.state.engine = None  # replaced by the lifespan; set so dependencies work without one
    app.state.sessionmaker = None
    app.state.http_client = None
    app.state.settings = settings
    app.state.principal_cache = PrincipalCache()
    app.state.notify_listener = None
    app.state.progress_hub = ProgressHub()
    app.state.paddle = None
    app.state.catalog = None
    app.state.google_verifier = google_verifier
    app.state.email_queue = email_queue
    app.state.audit_queue = audit_queue
    app.state.billing_eraser = billing_eraser  # the real Stripe eraser arrives with billing (#14)
    app.add_middleware(OriginCheckMiddleware, allowed_origin=settings.public_origin)
    app.add_middleware(RequestContextMiddleware)
    install_problem_handlers(app)
    _include_routers(app)
    install_problem_docs(app, ROUTERS)
    return app


ROUTERS = (
    health_router,
    auth_router,
    password_router,
    billing_router,
    billing_webhook_router,
    me_router,
    saved_router,
    admin_router,
    audits_router,
    media_router,
    market_router,
)


def _include_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)
    app.state.route_table = build_route_table(ROUTERS)  # for the `Allow` header of a 405 (rm_api.problems)


class _NoQueue:
    """Used when no database DSN is configured (unit tests of unrelated routes): refuses instead of dropping
    mail."""

    async def send_magic_link(self, *, email: str, url: str) -> None:
        raise RuntimeError("no job queue configured")

    async def send_auth_mail(self, *, kind: str, email: str, url: str | None) -> None:
        raise RuntimeError("no job queue configured")

    async def process_billing_events(self) -> None:
        raise RuntimeError("no job queue configured")

    async def run_audit(self, audit_id: UUID) -> None:
        raise RuntimeError("no job queue configured")
