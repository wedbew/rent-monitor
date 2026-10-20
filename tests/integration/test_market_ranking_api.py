# ruff: noqa: F811  (the `app` fixture is imported from test_me_saved_admin and used as a parameter)
"""`/api/market/locations/{id}/ranking` and `/api/market/ranking`: the experimental locality index (RM-439).

LEGAL[third-party-data]: hand-built statistics published by the production refresh pass; no network.

Real: API, session auth, Postgres, the BDL client and refresh against a live-shaped fake, stored place
mappings, the index. The fake's value is `1000 + (variable % 97) * 10 + int(unit[-4:-1]) + (year - 2015) * 7`,
so for every indicator the order of the four gminas follows `int(unit[-4:-1])` (rural Bochnia 102, Bochnia and
Kraków 101, Bieruń 1): the expected ranks are worked out from that, not read back.
"""

import dataclasses
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from bdl_live_fake import FakeBdl, value_for
from fastapi import FastAPI
from rm_contracts.location_context import TerritoryLevel
from rm_contracts.market import LocationCatalogue, LocationEntry
from rm_core import location_index as li
from rm_core.bdl_metrics import BY_KEY, SUPPRESSED_ATTR_IDS, VALID_ATTR_IDS
from rm_core.location_index_read import indicator_keys
from rm_core.location_mapping import MappingStatus, PlaceMapping, Relation
from rm_core.location_places import PgPlaceMapping
from rm_core.location_repo import PgLocationRepo
from rm_core.market_corpus import PgCorpus
from rm_worker.clients.bdl import BdlClient, BdlMetricBinding, BdlObservationValidator
from rm_worker.importers.bdl_context import refresh_context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_market_context_api import NoWait, no_sleep
from test_me_saved_admin import MakeToken, app, make_admin, sign_in  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_location_territory, app.market_daily_summary, app.market_offer_district, app.market_district,"
    " app.market_offer, app.market_import_run,"
    " app.market_import_checkpoint, app.market_location, app.market_catalogue, app.location_quota_stamp,"
    " app.location_publication_pointer, app.location_publication, app.location_ingest_run,"
    " app.location_observation, app.location_territory, app.location_reference"
)
BOCHNIA, RURAL, KRAKOW, BIERUN = "011212001011", "011212001022", "011212161011", "012424010013"
POWIAT_B, POWIAT_K, POWIAT_BIERUN = "011212001000", "011212161000", "012424010000"
WOJ_M, WOJ_S = "011200000000", "012400000000"


def metrics(skip: frozenset[str] = frozenset()) -> list:
    return [
        dataclasses.replace(
            BY_KEY[k], min_cohort=1, min_coverage=Decimal("0.70"), max_value=None
        )  # fake values exceed a % bound
        for k in indicator_keys()
        if k not in skip
    ]


async def publish(engine: AsyncEngine, skip: frozenset[str] = frozenset()) -> async_sessionmaker:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    ms = metrics(skip)
    fake = FakeBdl(
        years={m.variable_id: tuple(range(2016, 2026)) for m in ms},
        unit_of={m.variable_id: m.unit for m in ms},
    )
    await refresh_context(
        PgLocationRepo(sm),
        BdlClient(http=fake.client(), quota=NoWait(), page_size=2, sleep=no_sleep),
        reference_version=1,
        metrics=ms,
        validator=BdlObservationValidator(
            bindings={
                str(m.variable_id): BdlMetricBinding(
                    variable_id=str(m.variable_id),
                    definition=m.definition,
                    expected_unit=m.unit,
                    valid_attr_ids=VALID_ATTR_IDS,
                    suppressed_attr_ids=SUPPRESSED_ATTR_IDS,
                )
                for m in ms
            }
        ),
        min_rows=dict.fromkeys(TerritoryLevel, 2),
    )
    corpus = PgCorpus(sm)
    await corpus.ensure_catalogue(
        LocationCatalogue.build(
            1,
            "rank",
            [
                LocationEntry(location_id=i, name=n, otodom_path=f"a/b/{i}")
                for i, n in (
                    ("bochnia", "Bochnia"),
                    ("krakow", "Kraków"),
                    ("bierun", "Bieruń (miejsce)"),
                    ("dwie", "Bochnia dwie"),
                    ("brak", "Bez przypisania"),
                )
            ],
        )
    )
    await PgPlaceMapping(sm).save(
        1,
        1,
        [
            PlaceMapping("bochnia", MappingStatus.mapped, "m", Relation.gmina, BOCHNIA, POWIAT_B, WOJ_M, ()),
            PlaceMapping("krakow", MappingStatus.mapped, "m", Relation.gmina, KRAKOW, POWIAT_K, WOJ_M, ()),
            PlaceMapping(
                "bierun", MappingStatus.mapped, "m", Relation.within_gmina, BIERUN, POWIAT_BIERUN, WOJ_S, ()
            ),
            PlaceMapping("dwie", MappingStatus.ambiguous, "m", None, None, POWIAT_B, WOJ_M, (BOCHNIA, RURAL)),
            PlaceMapping("brak", MappingStatus.unmatched, "m"),
        ],
    )
    return sm


@pytest.fixture(autouse=True)
def small_cohorts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(li, "MIN_COHORT", 3)  # TEST-ONLY: the fake world has four gminas
    monkeypatch.setattr(li, "MIN_REGION", 2)


@pytest.fixture
async def world(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    await publish(engine)
    app.state.__dict__.pop("index_cache", None)
    yield
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def test_a_mapped_place_gets_a_scored_ranked_index_with_every_component_explained(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await c.get("/api/market/locations/bochnia/ranking")).json()
    idx = body["index"]
    assert (body["name"], body["mapping"]["status"], idx["state"]) == ("Bochnia", "mapped", "ok")
    assert (idx["method_version"], idx["higher_is_better"], idx["gmina"]["name"]) == (1, True, "Bochnia")
    assert idx["score"] is not None
    assert idx["weight_coverage"] == "1.00"
    national = next(p for p in idx["positions"] if p["scope"] == "national")
    assert national["of"] == 4  # all four fictional gminas are scored
    comps = {x["key"]: x for x in idx["components"]}
    assert set(comps) == {c.key for c in li.COMPONENTS}
    unemployment = comps["unemployment_share"]  # lower is better: Bieruń (1) first, Bochnia 101 ties Kraków
    assert (unemployment["national_rank"], unemployment["national_of"]) == (2, 4)
    assert unemployment["favourable_pl"] == "Niższa wartość = korzystniej"
    assert Decimal(unemployment["score"]) == Decimal("66.67")  # (4 - 2) / 3 * 100
    earnings = comps["earnings"]  # a powiat statistic: labelled as such and naming the unit measured
    assert (earnings["basis"], earnings["measured"]["name"]) == ("proxy", "Powiat bocheński")
    migration = comps["net_migration_per_1000"]
    expected = Decimal(value_for(1365234, BOCHNIA, 2025)) / Decimal(value_for(72305, BOCHNIA, 2025)) * 1000
    assert Decimal(migration["value"]) == expected.quantize(Decimal("0.01"))
    assert migration["year"] == 2025
    assert sum(Decimal(x["points"]) for x in idx["components"]) == pytest.approx(
        Decimal(idx["score"]), abs=Decimal("0.05")
    )
    assert idx["newest_year"] == 2025
    assert "Nie jest wyceną" in idx["caveat_pl"]
    assert body["source"]["name"] == "GUS BDL"


async def test_a_place_inside_a_gmina_describes_that_gmina_and_says_so(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await c.get("/api/market/locations/bierun/ranking")).json()
    assert body["mapping"]["relation"] == "within_gmina"
    assert body["index"]["gmina"]["name"] == "Bieruń"  # the gmina's statistics, named as the gmina
    comps = {x["key"]: x for x in body["index"]["components"]}
    assert comps["unemployment_share"]["national_rank"] == 1  # the lowest value of the four
    assert Decimal(comps["unemployment_share"]["score"]) == Decimal("100.00")


async def test_an_ambiguous_or_unmapped_place_has_no_index_and_no_guess(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    for place, word in (("dwie", "kilku gmin"), ("brak", "nie udało się")):
        idx = (await c.get(f"/api/market/locations/{place}/ranking")).json()["index"]
        assert (idx["state"], idx["score"], idx["components"], idx["positions"]) == (
            "unavailable",
            None,
            [],
            [],
        )
        assert word in idx["reasons"][0]


async def test_the_overview_ranks_places_best_first_and_lists_the_unscored_last(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await c.get("/api/market/ranking")).json()
    assert (body["scored_gminas"], body["total_places"], body["visible_places"]) == (4, 5, 5)
    ranks = [(i["location_id"], i["rank"]) for i in body["items"]]
    scored = [r for _, r in ranks if r is not None]
    assert scored == sorted(scored)
    assert [i["state"] for i in body["items"][-2:]] == ["unavailable", "unavailable"]  # ambiguous, unmatched
    assert {i["location_id"] for i in body["items"][-2:]} == {"dwie", "brak"}
    assert all(i["of"] == 4 for i in body["items"] if i["rank"] is not None)


async def test_a_missing_indicator_family_makes_the_index_not_scored_with_reasons(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES}"))
    await publish(engine, skip=frozenset({"regon_entities_per_10k"}))  # the whole business pillar
    app.state.__dict__.pop("index_cache", None)
    try:
        c, _ = await make_admin(app, engine, make_google_token)
        idx = (await c.get("/api/market/locations/bochnia/ranking")).json()["index"]
        assert (idx["state"], idx["score"], idx["positions"]) == ("not_scored", None, [])
        assert any("Przedsiębiorczość" in r for r in idx["reasons"])
        assert "Podmioty gospodarcze (REGON) na 10 tys. mieszkańców" in idx["missing"]
        assert next(x for x in idx["components"] if x["key"] == "business_density")["value"] is None
        overview = (await c.get("/api/market/ranking")).json()
        assert overview["scored_gminas"] == 0
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {TABLES}"))


async def test_the_ranking_follows_the_places_access_rules(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(
        app, make_google_token
    )  # a free account: no market data published, so nothing visible
    assert (await c.get("/api/market/locations/bochnia/ranking")).status_code == 403
    assert (await c.get("/api/market/locations/nowhere/ranking")).status_code == 404
    overview = (await c.get("/api/market/ranking")).json()
    assert (overview["access"], overview["visible_places"]) == ("free", 0)
