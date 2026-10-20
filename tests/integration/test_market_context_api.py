# ruff: noqa: F811  (the `app` fixture is imported from test_me_saved_admin and used as a parameter)
"""`/api/market/locations/{id}/context` over real BDL releases, a stored mapping and real Postgres (RM-282).

LEGAL[third-party-data]: hand-built statistics published by the production refresh pass; no network.

Real: API, session auth, Postgres, the BDL client and refresh against a live-shaped fake, the stored mapping,
the context builder. Expected numbers are written by hand from the fake's formula (`value_for`).
"""

import dataclasses
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from bdl_live_fake import FakeBdl, value_for
from fastapi import FastAPI
from rm_contracts.location_context import TerritoryLevel
from rm_contracts.market import LocationCatalogue, LocationEntry
from rm_core.bdl_metrics import BY_KEY
from rm_core.location_mapping import MappingStatus, PlaceMapping, Relation
from rm_core.location_places import PgPlaceMapping
from rm_core.location_repo import PgLocationRepo
from rm_core.market_corpus import PgCorpus
from rm_worker.clients.bdl import BdlClient, BdlObservationValidator
from rm_worker.importers.bdl_context import refresh_context
from rm_worker.tasks.location_context import BDL_BINDINGS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_me_saved_admin import MakeToken, app, make_admin  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_location_territory, app.market_daily_summary, app.market_offer_district, app.market_district,"
    " app.market_offer, app.market_import_run,"
    " app.market_import_checkpoint, app.market_location, app.market_catalogue, app.location_quota_stamp,"
    " app.location_publication_pointer, app.location_publication, app.location_ingest_run,"
    " app.location_observation, app.location_territory, app.location_reference"
)
POP = dataclasses.replace(BY_KEY["population_total"], min_cohort=1)
PRICE = dataclasses.replace(BY_KEY["dwelling_median_price_m2"], min_cohort=1, min_coverage=Decimal("0.70"))
BOCHNIA, BOCHNIA_RURAL = "011212001011", "011212001022"
POWIAT, WOJ, COUNTRY = "011212001000", "011200000000", "000000000000"


class NoWait:
    async def acquire(self, *, max_wait_s: float) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
async def world(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    sm = async_sessionmaker(engine, expire_on_commit=False)
    fake = FakeBdl(
        years={72305: tuple(range(2010, 2026)), 1607914: tuple(range(2019, 2025))},
        unit_of={72305: "osoba", 1607914: "zł"},
    )
    await refresh_context(
        PgLocationRepo(sm),
        BdlClient(http=fake.client(), quota=NoWait(), page_size=2, sleep=no_sleep),
        reference_version=1,
        metrics=[POP, PRICE],
        validator=BdlObservationValidator(bindings={k: BDL_BINDINGS[k] for k in ("72305", "1607914")}),
        min_rows=dict.fromkeys(TerritoryLevel, 2),
    )
    corpus = PgCorpus(sm)
    await corpus.ensure_catalogue(
        LocationCatalogue.build(
            1,
            "ctx",
            [
                LocationEntry(location_id="bochnia", name="Bochnia", otodom_path="a/b/c"),
                LocationEntry(location_id="dwie", name="Bochnia (niejednoznaczna)", otodom_path="a/b/d"),
                LocationEntry(location_id="brak", name="Bez przypisania", otodom_path="a/b/e"),
            ],
        )
    )
    await PgPlaceMapping(sm).save(
        1,
        1,
        [
            PlaceMapping(
                "bochnia",
                MappingStatus.mapped,
                "name_in_powiat",
                Relation.gmina,
                BOCHNIA,
                POWIAT,
                WOJ,
                (BOCHNIA,),
            ),
            PlaceMapping(
                "dwie",
                MappingStatus.ambiguous,
                "gmina_ambiguous",
                None,
                None,
                POWIAT,
                WOJ,
                (BOCHNIA, BOCHNIA_RURAL),
            ),
            PlaceMapping("brak", MappingStatus.unmatched, "powiat_unknown"),
        ],
    )
    yield
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def test_a_mapped_place_gets_values_series_parents_and_honest_gates(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await c.get("/api/market/locations/bochnia/context")).json()
    assert body["mapping"]["status"] == "mapped"
    assert [t["name"] for t in body["chain"]] == ["Bochnia", "Powiat bocheński", "Małopolskie", "Polska"]
    assert body["chain"][0]["teryt"] == "1201011"
    assert body["published_metrics"] == 2  # only the two metrics this test refreshed have releases
    by_key = {m["key"]: m for m in body["metrics"]}
    pop = by_key["population_total"]
    assert (pop["state"], pop["year"], pop["measured"]["name"]) == ("direct", 2025, "Bochnia")
    assert Decimal(pop["value"]) == Decimal(value_for(72305, BOCHNIA, 2025))
    assert [p["year"] for p in pop["series"]] == list(range(2016, 2026))  # ten years, oldest first
    assert {p["territory"]["level"] for p in pop["parents"]} == {"powiat", "wojewodztwo", "country"}
    country = next(p for p in pop["parents"] if p["territory"]["level"] == "country")
    assert Decimal(country["value"]) == Decimal(value_for(72305, COUNTRY, 2025))  # as published, not summed
    assert pop["national"]["state"] in {
        "ok",
        "suppressed",
    }  # a thin cohort: the gate decides
    assert pop["peers"]["state"] == "suppressed"  # fewer than five eligible siblings under the powiat
    assert pop["release_id"]
    price = by_key["dwelling_median_price_m2"]  # a powiat-grain deed statistic seen from a gmina
    assert (price["state"], price["measured"]["name"], price["year"]) == ("proxy", "Powiat bocheński", 2024)
    assert price["unit"] == "zł/m²"
    other = by_key["unemployment_rate_standard"]  # never refreshed here
    assert (other["state"], other["value"], other["series"]) == ("unavailable", None, [])
    assert other["reason"]


async def test_an_ambiguous_place_lists_its_candidates_and_falls_back_to_powiat_figures(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await c.get("/api/market/locations/dwie/context")).json()
    assert body["mapping"]["status"] == "ambiguous"
    assert {t["territory_id"] for t in body["mapping"]["candidates"]} == {BOCHNIA, BOCHNIA_RURAL}
    assert [t["level"] for t in body["chain"]] == ["powiat", "wojewodztwo", "country"]  # no gmina is guessed
    pop = next(m for m in body["metrics"] if m["key"] == "population_total")
    assert (pop["state"], pop["measured"]["name"]) == ("direct", "Powiat bocheński")


async def test_an_unmapped_place_has_no_context(
    app: FastAPI, engine: AsyncEngine, world: None, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await c.get("/api/market/locations/brak/context")).json()
    assert (body["mapping"]["status"], body["chain"], body["metrics"]) == ("unmatched", [], [])
