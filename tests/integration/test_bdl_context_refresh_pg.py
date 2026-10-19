"""BDL context refresh end to end on real Postgres with a live-shaped fake of the source (RM-48).

Real: Postgres 17, `PgLocationRepo`, the BDL client and validator, the registry's specs, the refresh pass.
Faked, by name: the GUS BDL HTTP service (`tests/bdl_live_fake.py`, hand-built units and values). Expected
numbers are written by hand from the fake's territory, never computed by the code under test.

LEGAL[third-party-data]: exercises ingestion of hand-built public-statistics-shaped data (RM-48).
"""

import dataclasses
from decimal import Decimal

import pytest
import pytest_asyncio
from bdl_live_fake import FakeBdl, value_for
from rm_contracts.location_context import ObservationStatus, TerritoryLevel
from rm_core.bdl_metrics import BY_KEY, MetricSpec
from rm_core.location_repo import PgLocationRepo
from rm_worker.clients.bdl import BdlClient, BdlObservationValidator
from rm_worker.importers.bdl_context import RefreshReport, refresh_context
from rm_worker.tasks.location_context import BDL_BINDINGS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.location_quota_stamp, app.location_publication_pointer, app.location_publication,"
    " app.location_ingest_run, app.location_observation, app.location_territory, app.location_reference"
)
G, P = TerritoryLevel.gmina, TerritoryLevel.powiat
MIN_ROWS = {G: 3, P: 2}  # the fake territory is tiny; the real thresholds are in `bdl_context`
POP = dataclasses.replace(BY_KEY["population_total"], min_cohort=1)
PRICE = dataclasses.replace(BY_KEY["dwelling_median_price_m2"], min_cohort=1, min_coverage=Decimal("0.70"))
POP_ID, PRICE_ID = 72305, 1607914
KRAKOW_POWIAT, KRAKOW_GMINA, BOCHNIA_CITY = "011212161000", "011212161011", "011212001011"


class NoWait:
    async def acquire(self, *, max_wait_s: float) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


def source(**kw: object) -> FakeBdl:
    return FakeBdl(
        years={POP_ID: tuple(range(2010, 2026)), PRICE_ID: tuple(range(2019, 2025))},
        unit_of={POP_ID: "osoba", PRICE_ID: "zł"},
        **kw,  # type: ignore[arg-type]
    )


def client(fake: FakeBdl) -> BdlClient:
    return BdlClient(http=fake.client(), quota=NoWait(), page_size=2, sleep=no_sleep)


def validator(*specs: MetricSpec) -> BdlObservationValidator:
    return BdlObservationValidator(
        bindings={str(s.variable_id): BDL_BINDINGS[str(s.variable_id)] for s in specs}
    )


@pytest_asyncio.fixture(loop_scope="session")
async def repo(engine: AsyncEngine) -> PgLocationRepo:  # type: ignore[misc]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    yield PgLocationRepo(async_sessionmaker(engine, expire_on_commit=False))  # type: ignore[misc]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def run(repo: PgLocationRepo, fake: FakeBdl, *specs: MetricSpec) -> RefreshReport:
    return await refresh_context(
        repo,
        client(fake),
        reference_version=1,
        metrics=specs,
        validator=validator(*specs),
        min_rows=MIN_ROWS,
    )


async def test_reference_is_built_from_the_live_shaped_units_with_exact_teryt_codes(
    repo: PgLocationRepo,
) -> None:
    report = await run(repo, source(), POP)
    # 4 whole current gminas; the two parts, the district and the defunct gmina are not reference units.
    assert report.reference_counts == {"gmina": 4, "powiat": 3, "wojewodztwo": 2, "country": 1}
    reference = await repo.get_reference(1)
    assert reference is not None
    by_id = {t.territory_id: t for t in reference}
    assert by_id[BOCHNIA_CITY].teryt == "1201011"  # the TERYT of the urban gmina Bochnia
    assert by_id[KRAKOW_GMINA].teryt == "1261011"
    assert by_id[KRAKOW_GMINA].has_powiat_rights  # powiat code 61: the city has both roles
    assert not by_id[BOCHNIA_CITY].has_powiat_rights
    assert by_id[KRAKOW_POWIAT].teryt == "1261"
    assert by_id[BOCHNIA_CITY].parent_id == "011212001000"  # a gmina's parent is its powiat
    assert (
        by_id["011212001000"].parent_id == "011200000000"
    )  # a powiat's parent is the voivodeship, not the sub-region
    assert "011212999000" not in by_id  # a powiat with no value in the reference year


async def test_every_published_level_is_stored_and_every_passing_year_is_published(
    repo: PgLocationRepo,
) -> None:
    report = await run(repo, source(), POP, PRICE)
    pop, price = report.metrics
    assert pop.years == tuple(range(2016, 2026))  # the newest ten years the source holds
    assert price.years == tuple(range(2019, 2025))  # the series is shorter: only what exists
    assert pop.published == list(pop.years)
    assert price.published == list(price.years)
    assert pop.runs == {
        "gmina": "complete",
        "powiat": "complete",
        "wojewodztwo": "complete",
        "country": "complete",
    }
    assert price.runs == {
        "powiat": "complete",
        "wojewodztwo": "complete",
        "country": "complete",
    }  # no gmina value
    obs = {o.territory_id: o for o in await repo.observations("population_total", 1, 2025)}
    assert obs[BOCHNIA_CITY].value == Decimal(value_for(POP_ID, BOCHNIA_CITY, 2025))
    assert {BOCHNIA_CITY, KRAKOW_GMINA, "011212001022", "012424010013"} <= set(obs)  # the four whole gminas
    assert "011212001034" not in obs  # an urban part is never stored
    assert "011212161088" not in obs  # nor a district
    assert obs["000000000000"].value == Decimal(
        value_for(POP_ID, "000000000000", 2025)
    )  # published aggregate
    release = await repo.current_release("population_total", 1, 2025)
    assert release is not None
    assert (release.expected, release.eligible) == (4, 4)


async def test_a_second_pass_over_finished_runs_asks_the_source_for_no_data(repo: PgLocationRepo) -> None:
    await run(repo, source(), POP, PRICE)
    again = source()
    report = await run(repo, again, POP, PRICE)
    assert again.requests["data"] == 0  # every run is already complete
    assert again.requests["units"] == 0  # the reference is frozen per version
    assert {s for m in report.metrics for s in m.runs.values()} == {"already_complete"}
    assert report.metrics[0].published == list(report.metrics[0].years)  # publication is idempotent too


async def test_confidential_cells_are_suppressed_not_zero_and_thin_coverage_refuses_publication(
    repo: PgLocationRepo,
) -> None:
    fake = source(withheld={PRICE_ID: {KRAKOW_POWIAT}})
    report = await run(repo, fake, POP, PRICE)
    price = report.metrics[1]
    assert price.published == []  # 2 of 3 powiats measured: coverage 0.667 is under the metric's 0.70
    assert set(price.refused) == set(price.years)
    assert "coverage" in price.refused[2024].lower()
    assert await repo.current_release("dwelling_median_price_m2", 1, 2024) is None  # fail closed
    krakow = {o.territory_id: o for o in await repo.observations("dwelling_median_price_m2", 1, 2024)}[
        KRAKOW_POWIAT
    ]
    assert krakow.status is ObservationStatus.suppressed  # attribute 91: never read as a price of 0
    assert krakow.value is None
    assert report.metrics[0].published  # the other metric is unaffected


async def test_a_wrong_unit_fails_that_metric_only(repo: PgLocationRepo) -> None:
    fake = source()
    fake.unit_of[PRICE_ID] = "euro"
    report = await run(repo, fake, POP, PRICE)
    pop, price = report.metrics
    assert pop.published == list(pop.years)
    assert price.published == []
    assert all(v.startswith("error:WrongUnitError") for v in price.runs.values())
