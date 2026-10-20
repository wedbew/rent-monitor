# ruff: noqa: F811  (fixtures `app` and `market` are imported and used as parameters)
"""`unlimited_reports` opens the whole Rynek catalogue; nobody else's access changes (RM-438).

Real API, session auth and Postgres; the market data is hand-built (see `test_market_api`). The grant goes
through the production function the staff script calls, by e-mail, once.
"""

import pytest
from fastapi import FastAPI
from rm_core.entitlement_grants import grant, revoke
from rm_core.market_history import PgMarketHistory
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_market_api import get, market  # noqa: F401  (fixture: `market`)
from test_me_saved_admin import MakeToken, app, sign_in  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]


async def test_the_entitled_account_sees_every_place_and_a_restricted_one_does_not(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    entitled, me = await sign_in(app, make_google_token)
    ordinary, _ = await sign_in(app, make_google_token)
    async with sm() as s:
        assert (await grant(s, me["email"], note="test")).outcome == "granted"

    full = (await get(entitled, "/api/market/overview")).json()
    assert (full["access"], full["total_places"], full["visible_places"]) == ("full", 4, 4)
    for path in (  # every route the free tier closes
        "/api/market/locations/gdynia",
        "/api/market/locations/gdynia/history",
        "/api/market/locations/gdynia/context",
        "/api/market/locations/gdansk",
    ):
        assert (await get(entitled, path)).status_code == 200, path
    assert [
        i["location_id"] for i in (await get(entitled, "/api/market/locations", q="gdy")).json()["items"]
    ] == ["gdynia"]

    free = (await get(ordinary, "/api/market/overview")).json()
    assert (free["access"], free["visible_places"]) == ("free", 1)
    assert (await get(ordinary, "/api/market/locations/gdynia")).json()["code"] == "FEATURE_NOT_IN_PLAN"


async def test_revoking_closes_the_catalogue_again_and_grant_is_idempotent(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    c, me = await sign_in(app, make_google_token)
    async with sm() as s:
        assert (
            await grant(s, me["email"].upper(), note="first")
        ).outcome == "granted"  # identity is normalised
        assert (await grant(s, me["email"], note="again")).outcome == "already_granted"
    assert (await get(c, "/api/market/overview")).json()["access"] == "full"
    async with sm() as s:
        assert (await revoke(s, me["email"])).outcome == "revoked"
        assert (await revoke(s, me["email"])).outcome == "already_revoked"
        assert (await grant(s, me["email"], note="back")).outcome == "restored"
    assert (await get(c, "/api/market/overview")).json()["access"] == "full"
    async with sm() as s:
        await revoke(s, me["email"])
    assert (await get(c, "/api/market/overview")).json()["access"] == "free"


async def test_granting_never_creates_an_account(engine: AsyncEngine) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        result = await grant(s, "nobody-here@example.test", note="x")
    assert (result.outcome, result.user_id) == ("no_such_account", None)
