"""Async engine and session factory. One engine per process; sessions come from a dependency."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from rm_core.settings import Settings


def make_engine(settings: Settings, *, pool_size: int = 5, max_overflow: int = 3) -> AsyncEngine:
    """Pool 5+3 per process (blueprint §6 connection budget). `database_url` is `postgresql+psycopg://…`."""
    if not settings.database_url:
        msg = "DATABASE_URL is not set"
        raise RuntimeError(msg)
    return create_async_engine(
        settings.database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"options": "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000"},
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
