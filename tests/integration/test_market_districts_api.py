# ruff: noqa: F811  (fixtures `app` and `market` are imported and used as parameters)
"""Districts and apartment cohorts of the market API on real Postgres through the real API (RM-439).

LEGAL[third-party-data]: hand-built asking figures; no network.

Toruń has 12 priced adverts in "centrum" (rents 2000..2550 on 50 m2, PLN/m2 40..51), 3 in "rubinkowo", and 2
the source gave no district. Gdynia's adverts carry no district at all. Every expected figure is computed by
hand here, not read back from the code under test.
"""

from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from deal_analyzer.market_stats import summarise_asking
from fastapi import FastAPI
from market_corpus_contract import obs, run
from rm_contracts.market import RunMode
from rm_core.market_corpus import PgCorpus
from rm_core.market_history import PgMarketHistory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_market_api import BOOT, NOW, TABLES, catalogue, get, ingest, make_admin
from test_me_saved_admin import MakeToken, app, client_for, sign_in  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]

CENTRUM = {"district_id": "cala-polska/torun/centrum", "district_name": "Centrum"}
RUBINKOWO = {"district_id": "cala-polska/torun/rubinkowo", "district_name": "Rubinkowo"}


@pytest.fixture
async def market(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[PgMarketHistory]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    sm = async_sessionmaker(engine, expire_on_commit=False)
    corpus = PgCorpus(sm)
    await corpus.ensure_catalogue(catalogue())
    torun = (
        [
            obs(str(100 + i), loc="torun", rent=str(2000 + 50 * i), area="50", rooms=2, **CENTRUM)
            for i in range(12)
        ]
        + [obs(str(200 + i), loc="torun", rent="3000", area="60", rooms=3, **RUBINKOWO) for i in range(3)]
        + [obs(str(300 + i), loc="torun", rent="2100", area="42", rooms=2) for i in range(2)]
    )
    await ingest(corpus, "r-torun", "torun", torun)
    plain = [obs(str(400 + i), loc="gdynia", rent=str(2500 + 20 * i), area="48", rooms=2) for i in range(12)]
    await ingest(corpus, "r-gdynia", "gdynia", plain)
    for loc in ("torun", "gdynia"):
        await ingest(
            corpus, f"n-{loc}", loc, [], seen=NOW - timedelta(hours=2), mode=RunMode.incremental, start=BOOT
        )
    history = PgMarketHistory(sm)
    app.state.clock = lambda: NOW
    for loc in ("torun", "gdynia"):
        await history.publish_day(loc, NOW.date(), now=NOW, summarise=summarise_asking)
    yield history
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def test_districts_list_each_known_district_with_hand_computed_figures(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    r = await get(c, "/api/market/locations/torun/districts")
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["coverage"], body["cohort_key"], body["price_basis"], body["source"]) == (
        "supported",
        "all",
        "asking",
        "otodom",
    )
    assert (body["offers_in_cohort"], body["offers_with_district"]) == (17, 15)  # 2 carry no district
    by_id = {d["district_id"]: d for d in body["districts"]}
    centrum = by_id[CENTRUM["district_id"]]
    # by hand: PLN/m2 40..51 -> median 45.5, quartiles 42.75 / 48.25; median rent of 2000..2550 = 2275
    assert (centrum["priced_count"], centrum["sufficient"], centrum["withheld_reason"]) == (12, True, None)
    assert (centrum["median_ppm2"], centrum["p25_ppm2"], centrum["p75_ppm2"], centrum["median_rent_pln"]) == (
        "45.50",
        "42.75",
        "48.25",
        "2275.00",
    )
    rubinkowo = by_id[
        RUBINKOWO["district_id"]
    ]  # known, but 3 priced adverts: counts kept, statistics withheld
    assert (rubinkowo["priced_count"], rubinkowo["sufficient"], rubinkowo["withheld_reason"]) == (
        3,
        False,
        "insufficient_sample",
    )
    assert rubinkowo["median_ppm2"] is None  # never zero
    assert rubinkowo["median_rent_pln"] is None
    assert [d["name"] for d in body["districts"]] == ["Centrum", "Rubinkowo"]  # deepest sample first
    assert set(body["caveats"]) == {"asking_not_achieved_rent", "not_active_stock", "not_deed_price"}


async def test_the_cohort_applies_to_districts_and_a_district_with_no_such_adverts_withholds(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await get(c, "/api/market/locations/torun/districts", cohort="rooms_3")).json()
    by_id = {d["district_id"]: d for d in body["districts"]}
    assert body["cohort_key"] == "rooms_3"
    assert by_id[RUBINKOWO["district_id"]]["priced_count"] == 3
    assert by_id[CENTRUM["district_id"]]["priced_count"] == 0  # known district, none of that size: not absent
    assert by_id[CENTRUM["district_id"]]["withheld_reason"] == "insufficient_sample"


async def test_a_place_whose_source_names_no_district_says_so_instead_of_an_empty_table(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await get(c, "/api/market/locations/gdynia/districts")).json()
    assert (body["coverage"], body["districts"], body["offers_with_district"]) == ("none", [], 0)
    assert body["offers_in_cohort"] == 12  # the place's adverts are there; none names a district


async def test_district_routes_follow_the_places_access_rules(
    app: FastAPI, market: PgMarketHistory, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)  # free: only places with a sufficient sample
    assert (await get(c, "/api/market/locations/torun/districts")).status_code == 200
    closed = await get(c, "/api/market/locations/gdansk/districts")
    assert (closed.status_code, closed.json()["code"]) == (403, "FEATURE_NOT_IN_PLAN")
    assert (await get(c, "/api/market/locations/nowhere/districts")).status_code == 404
    assert (await get(c, "/api/market/locations/torun/districts", cohort="rooms 3")).status_code == 422
    async with client_for(app) as anonymous:
        assert (await anonymous.get("/api/market/locations/torun/districts")).status_code == 401


async def test_the_overview_follows_the_chosen_cohort_for_every_place(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    whole = (await get(c, "/api/market/overview")).json()
    two = (await get(c, "/api/market/overview", cohort="rooms_2")).json()
    three = (await get(c, "/api/market/overview", cohort="rooms_3")).json()
    assert (whole["cohort_key"], two["cohort_key"], three["cohort_key"]) == ("all", "rooms_2", "rooms_3")
    torun = lambda body: next(p for p in body["items"] if p["location_id"] == "torun")  # noqa: E731
    assert torun(whole)["priced_count"] == 17
    assert torun(two)["priced_count"] == 14  # 12 + 2 two-room adverts
    assert torun(three)["priced_count"] == 3
    assert torun(three)["sufficient"] is False
    assert torun(three)["median_ppm2"] is None  # a withheld sample is never a number
    gdynia = next(p for p in two["items"] if p["location_id"] == "gdynia")
    assert gdynia["priced_count"] == 12
    assert next(p for p in three["items"] if p["location_id"] == "gdynia")["priced_count"] is None  # no row
    assert (await get(c, "/api/market/overview", cohort="BAD")).status_code == 422


async def test_rooms_of_offers_stored_without_them_are_attached_beside_the_offer_and_make_rooms_cohorts(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    """Live finding: the importer stored no rooms (the site sends a word). The sweep attaches the count in a
    sidecar; the offers themselves are untouched."""
    sm = async_sessionmaker(engine, expire_on_commit=False)
    corpus = PgCorpus(sm)
    # offers 100..111 (Toruń) already have rooms=2 in this fixture; add three stored WITHOUT rooms
    await corpus.start_run(run("r-extra", "torun", RunMode.incremental, start=BOOT))
    bare = [obs(str(900 + i), loc="torun", rent="2500", area="50", rooms=None) for i in range(3)]
    await corpus.record_offers("r-extra", bare, NOW - timedelta(hours=1))
    attached = await corpus.record_districts(
        "torun", [obs(str(900 + i), loc="torun", rent="2500", area="50", rooms=3) for i in range(3)], NOW
    )
    assert attached == 0  # no district was named; the rooms went to the sidecar
    async with engine.connect() as c:
        rows = (
            await c.execute(text("SELECT count(*), min(rooms), max(rooms) FROM app.market_offer_rooms"))
        ).one()
        stored = (
            await c.execute(text("SELECT count(*) FROM app.market_offer WHERE rooms IS NULL"))
        ).scalar_one()
    assert tuple(rows) == (3, 3, 3)
    assert stored == 3  # the offers still carry no rooms: only the sidecar does
    again = await corpus.record_districts(
        "torun", [obs(str(900), loc="torun", rent="2500", area="50", rooms=4)], NOW
    )
    assert again == 0
    async with engine.connect() as c:
        assert (
            await c.execute(text("SELECT rooms FROM app.market_offer_rooms WHERE source_offer_id = 900"))
        ).scalar_one() == 3
