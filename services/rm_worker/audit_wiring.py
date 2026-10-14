"""Build the production `AuditServices` from settings, once per worker process (#187).

`AUDIT_PROVIDERS=none` (default) builds nothing: every audit then fails closed and releases its credit
(`audit_pipeline.fail_unconfigured`). `real` wires the Otodom client, the comparable-rent store, the risk-free
rate and the killable engine child.
"""

from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.settings import Settings

from rm_worker.audit_pipeline import AuditServices
from rm_worker.context import MarketContext
from rm_worker.engine_child import ChildEngine
from rm_worker.importers.demand import ProcrastinateImportQueue
from rm_worker.listing_source import build_listing_source

POOL = 2  # audit concurrency is 1; the extra connection serves the slot/breaker short transactions


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
    )
