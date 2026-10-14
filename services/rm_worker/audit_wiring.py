"""Build the production `AuditServices` from settings, once per worker process (#187).

`AUDIT_PROVIDERS=none` (default) builds nothing: every audit then fails closed and releases its credit
(`audit_pipeline.fail_unconfigured`). `real` wires the Otodom client, the comparable-rent store, the risk-free
rate and the killable engine child.
"""

import httpx
from rm_core.ai_budget import PostgresBudgetGate
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.settings import Settings
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from rm_worker.audit_pipeline import AuditServices
from rm_worker.clients.limiter import PgAdvisoryLimiter
from rm_worker.clients.openrouter import OpenRouterClient
from rm_worker.context import MarketContext
from rm_worker.engine_child import ChildEngine
from rm_worker.importers.demand import ProcrastinateImportQueue
from rm_worker.listing_source import build_listing_source
from rm_worker.vision_stage import OpenRouterVisionStage

POOL = 2  # audit concurrency is 1; the extra connection serves the slot/breaker short transactions


def build_audit_services(settings: Settings) -> AuditServices | None:
    if settings.audit_providers != "real":
        return None
    db_engine = make_engine(settings, pool_size=POOL, max_overflow=1)
    sessionmaker = make_sessionmaker(db_engine)
    return AuditServices(
        sessionmaker=sessionmaker,
        source=build_listing_source(sessionmaker, settings),
        context=MarketContext(
            sessionmaker, risk_free=settings.risk_free_rate, import_queue=ProcrastinateImportQueue()
        ),
        timeout_s=float(settings.audit_job_timeout_s),
        engine=ChildEngine(memory_mb=settings.audit_child_memory_mb),
        vision=build_vision_stage(db_engine, sessionmaker, settings),
    )


def build_vision_stage(
    db_engine: AsyncEngine, sessionmaker: async_sessionmaker[AsyncSession], settings: Settings
) -> OpenRouterVisionStage | None:
    """No key means no vision (audits degrade); the kill switch keeps the stage but sends nothing."""
    key = settings.openrouter_api_key.get_secret_value()
    if not key:
        return None
    # LEGAL[images]: photos go to OpenRouter; GDPR[processor]: OpenRouter is a processor (RM-244).
    openrouter = OpenRouterClient(
        http=httpx.AsyncClient(),
        api_key=key,
        budget=PostgresBudgetGate(sessionmaker, monthly_cap_usd=settings.openrouter_monthly_budget_usd),
        limiter=PgAdvisoryLimiter(db_engine),
        estimate_usd=settings.openrouter_call_estimate_usd,
        base_url=settings.openrouter_base_url,
    )
    return OpenRouterVisionStage(
        openrouter=openrouter,
        images_http=httpx.AsyncClient(),
        model=settings.openrouter_vision_model,
        host_suffixes=settings.image_hosts,
        enabled=settings.legal_images_enabled,
    )
