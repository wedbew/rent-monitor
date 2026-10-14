"""Build the production `AuditServices` from settings, once per worker process (#187).

`AUDIT_PROVIDERS=none` (default) builds nothing: every audit then fails closed and releases its credit
(`audit_pipeline.fail_unconfigured`). `real` wires the Otodom client, the comparable-rent store, the risk-free
rate and the killable engine child.
"""

import httpx
import structlog
from rm_core.ai_budget import PostgresBudgetGate
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.audit_pipeline import AuditServices
from rm_worker.clients.limiter import PgAdvisoryLimiter
from rm_worker.clients.openrouter import OpenRouterClient
from rm_worker.context import MarketContext
from rm_worker.engine_child import ChildEngine
from rm_worker.importers.demand import ProcrastinateImportQueue
from rm_worker.listing_source import build_listing_source
from rm_worker.vision_stage import OpenRouterVision, VisionProvider

log = structlog.get_logger(__name__)

LIMITER_POOL = 1  # one dedicated connection per in-flight vision call; the audit lane makes one at a time
POOL = 2  # audit concurrency is 1; the extra connection serves the slot/breaker short transactions


def build_vision(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> VisionProvider | None:
    """Vision is on only with an OpenRouter key and `LEGAL_IMAGES_ENABLED`; otherwise audits end degraded.

    LEGAL[images], GDPR[processor]: see `vision_stage`. Spend is capped by the Postgres budget gate."""
    key = settings.openrouter_api_key.get_secret_value()
    if not settings.legal_images_enabled or not key:
        log.info("vision_stage_off", images_enabled=settings.legal_images_enabled, key_set=bool(key))
        return None
    client = OpenRouterClient(
        http=httpx.AsyncClient(),
        api_key=key,
        budget=PostgresBudgetGate(sessionmaker, monthly_cap_usd=settings.openrouter_monthly_budget_usd),
        limiter=PgAdvisoryLimiter(make_engine(settings, pool_size=LIMITER_POOL, max_overflow=1)),
        estimate_usd=settings.openrouter_call_estimate_usd,
        base_url=settings.openrouter_base_url,
    )
    images = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0), follow_redirects=False)
    return OpenRouterVision(
        client, images, model=settings.openrouter_vision_model, image_hosts=settings.image_hosts
    )


def build_audit_services(settings: Settings) -> AuditServices | None:
    if settings.audit_providers != "real":
        return None
    sessionmaker = make_sessionmaker(make_engine(settings, pool_size=POOL, max_overflow=1))
    return AuditServices(
        sessionmaker=sessionmaker,
        source=build_listing_source(sessionmaker, settings),
        context=MarketContext(
            sessionmaker, risk_free=settings.risk_free_rate, import_queue=ProcrastinateImportQueue()
        ),
        timeout_s=float(settings.audit_job_timeout_s),
        engine=ChildEngine(memory_mb=settings.audit_child_memory_mb),
        vision=build_vision(settings, sessionmaker),
    )
