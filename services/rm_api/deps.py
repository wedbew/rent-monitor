"""FastAPI dependencies shared by routers."""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from rm_contracts.problems import ProblemCode
from rm_core.principal import Principal
from rm_core.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_api.auth.sessions import PrincipalCache, resolve_principal
from rm_api.problems import Problem


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request: committed on success, rolled back on any exception.

    Route code never commits (agents.md §3). Used with `scope="function"` so a failing commit is a 500,
    not a silent error after the response was already sent.
    """
    sessionmaker: async_sessionmaker[AsyncSession] | None = request.app.state.sessionmaker
    if sessionmaker is None:
        raise Problem(503, ProblemCode.NOT_READY, "Database is not configured")
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


def get_http_client(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient = request.app.state.http_client
    return client


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def optional_principal(
    request: Request, session: "SessionDep", settings: SettingsDep
) -> Principal | None:
    """The signed-in caller, or None. Cookie to principal through the 30 s in-process cache."""
    token = request.cookies.get(settings.cookie_name)
    if not token or len(token) > 128:
        return None
    cache: PrincipalCache = request.app.state.principal_cache
    return await resolve_principal(session, token, cache, settings)


async def current_principal(principal: Annotated[Principal | None, Depends(optional_principal)]) -> Principal:
    if principal is None:
        raise Problem.unauthorized(ProblemCode.UNAUTHENTICATED, "Sign in required")
    return principal


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
PrincipalDep = Annotated[Principal, Depends(current_principal)]
OptionalPrincipalDep = Annotated[Principal | None, Depends(optional_principal)]
