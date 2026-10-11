"""FastAPI dependencies shared by routers."""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from rm_contracts.problems import ProblemCode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
