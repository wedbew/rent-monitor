"""LCTX-02a (RM-396): per-metric indicators served from published BDL releases, on real Postgres.

LEGAL[third-party-data]: exercises derivations of GUS BDL statistics; no network, hand-built rows (RM-396).

Metric keys and the variable id `TESTV1` are TEST-ONLY. No metric is selected or activated (B-023); the
publication policies below are test inputs, not owner decisions.
"""

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from rm_contracts.location_context import (
    Direction,
    MetricDefinition,
    Observation,
    ObservationStatus,
    PublicationPolicy,
    SelectionStatus,
    TerritoryLevel,
    TerritoryRef,
    ViewState,
)
from rm_core.location_contracts import TerritoryHierarchy
from rm_core.location_indicators import TrendState, load_trend, published_indicator, rank_indicator
from rm_core.location_repo import NotPublishableError, PgLocationRepo
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration]

Sessions = async_sessionmaker[AsyncSession]
TABLES = (
    "app.location_quota_stamp, app.location_publication_pointer, app.location_publication,"
    " app.location_ingest_run, app.location_observation, app.location_territory, app.location_reference"
)
G, P = TerritoryLevel.gmina, TerritoryLevel.powiat
DIGEST = "c" * 64
YEARS = (2022, 2023)
OWNER = "w1"


def territories() -> list[TerritoryRef]:
    out = [
        TerritoryRef(territory_id="PL", teryt="", name="Polska", level=TerritoryLevel.country),
        TerritoryRef(
            territory_id="W02", teryt="02", name="Woj", level=TerritoryLevel.wojewodztwo, parent_id="PL"
        ),
    ]
    out += [
        TerritoryRef(territory_id=f"P020{i}", teryt=f"020{i}", name=f"Pow{i}", level=P, parent_id="W02")
        for i in (1, 2, 3, 4)
    ]
    out += [
        TerritoryRef(territory_id="G1", teryt="0201011", name="G1", level=G, parent_id="P0201"),
        TerritoryRef(territory_id="G2", teryt="0201021", name="G2", level=G, parent_id="P0201"),
    ]
    return out


def powiat_defn() -> MetricDefinition:
    return MetricDefinition(
        key="test_density",
        version=1,
        name_pl="test",
        unit="u",
        native_level=P,
        published_levels=frozenset({P}),
        direction=Direction.higher_is_favorable,
        selection=SelectionStatus.selected,
        bdl_variable_id="TESTV1",
    )


def policy(cov: str | None, size: int | None) -> PublicationPolicy:
    return PublicationPolicy(
        metric_key="test_density",
        metric_version=1,
        min_coverage=None if cov is None else Decimal(cov),
        min_cohort_size=size,
    )


def row(tid: str, year: int, value: str | None) -> Observation:
    measured = value is not None
    return Observation(
        territory_id=tid,
        metric_key="test_density",
        metric_version=1,
        year=year,
        status=ObservationStatus.measured if measured else ObservationStatus.suppressed,
        value=Decimal(value) if value is not None else None,
        reason=None if measured else "source withholds",
        source_digest=DIGEST,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def sessions(engine: AsyncEngine) -> AsyncIterator[Sessions]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


@pytest_asyncio.fixture(loop_scope="session")
async def repo(sessions: Sessions) -> PgLocationRepo:
    r = PgLocationRepo(sessions)
    await r.ensure_reference(1, "test reference", territories())
    return r


async def seed(repo: PgLocationRepo, rows: list[Observation], *, complete: bool = True) -> str:
    run = await repo.start_run(
        variable_id="TESTV1",
        unit_level=5,
        years=YEARS,
        reference_version=1,
        metric_key="test_density",
        metric_version=1,
    )
    claimed = await repo.claim_run(run.run_id, OWNER, 60)
    assert claimed is not None
    await repo.record_page(run.run_id, OWNER, page_index=0, observations=rows, lease_s=60)
    if complete:
        await repo.complete_run(run.run_id, OWNER, gap_observations=[])
    else:
        await repo.release_run(run.run_id, OWNER, state="incomplete", error_category="test")
    return run.run_id


FULL_2023 = [
    row("P0201", 2023, "10"),
    row("P0202", 2023, "30"),
    row("P0203", 2023, "20"),
    row("P0204", 2023, "40"),
]
FULL_2022 = [
    row("P0201", 2022, "8"),
    row("P0202", 2022, "30"),
    row("P0203", 2022, "25"),
    row("P0204", 2022, "36"),
]


async def test_published_indicator_has_reproducible_rank_components_and_labels(repo: PgLocationRepo) -> None:
    rid = await seed(repo, [*FULL_2022, *FULL_2023])
    await repo.publish(rid, defn=powiat_defn(), policy=policy("0.75", 3), year=2023)
    first = await published_indicator(repo, powiat_defn(), policy("0.75", 3), territory_id="P0203", year=2023)
    again = await published_indicator(repo, powiat_defn(), policy("0.75", 3), territory_id="P0203", year=2023)
    assert first is not None
    assert first == again  # same inputs, same output
    ranks = {e.territory_id: e.rank for e in first.ranking.ranking.entries}
    assert ranks == {"P0204": 1, "P0202": 2, "P0203": 3, "P0201": 4}
    assert (first.ranking.ranking.expected, first.ranking.ranking.eligible) == (4, 4)
    assert first.ranking.gate.coverage == Decimal("1.0000")
    assert first.comparison.own.state is ViewState.direct
    assert first.comparison.peer_count == 3
    assert first.comparison.peer_median == Decimal("30.0000")
    assert first.comparison.delta_vs_peer_median == Decimal(-10)


async def test_a_gmina_is_shown_the_powiat_value_labelled_as_proxy(repo: PgLocationRepo) -> None:
    rid = await seed(repo, FULL_2023)
    await repo.publish(rid, defn=powiat_defn(), policy=policy("0.75", 3), year=2023)
    out = await published_indicator(repo, powiat_defn(), policy("0.75", 3), territory_id="G1", year=2023)
    assert out is not None
    assert out.comparison.own.state is ViewState.proxy
    assert out.comparison.own.measured_territory_id == "P0201"
    assert out.comparison.own.measured_level is P


async def test_nothing_is_served_before_a_release_exists(repo: PgLocationRepo) -> None:
    await seed(repo, FULL_2023, complete=False)
    assert (
        await published_indicator(repo, powiat_defn(), policy("0.5", 1), territory_id="P0201", year=2023)
        is None
    )


async def test_incomplete_run_cannot_be_published(repo: PgLocationRepo) -> None:
    rid = await seed(repo, FULL_2023, complete=False)
    with pytest.raises(NotPublishableError):
        await repo.publish(rid, defn=powiat_defn(), policy=policy("0.5", 1), year=2023)
    assert await repo.current_release("test_density", 1, 2023) is None


async def test_thin_coverage_is_suppressed_and_not_publishable(repo: PgLocationRepo) -> None:
    thin = [
        row("P0201", 2023, "10"),
        row("P0202", 2023, None),
        row("P0203", 2023, None),
        row("P0204", 2023, None),
    ]
    rid = await seed(repo, thin)
    with pytest.raises(NotPublishableError):
        await repo.publish(rid, defn=powiat_defn(), policy=policy("0.75", 3), year=2023)
    # Even if a caller asks directly, the pure layer suppresses the ranks instead of showing them.
    ref = await repo.get_reference(1)
    assert ref is not None
    ranked = rank_indicator(
        powiat_defn(),
        policy("0.75", 3),
        TerritoryHierarchy(ref),
        await repo.observations("test_density", 1, 2023),
        year=2023,
        expected=["P0201", "P0202", "P0203", "P0204"],
        cohort_id="powiat",
    )
    assert ranked.suppressed
    assert ranked.ranking.entries == ()
    assert (ranked.ranking.eligible, ranked.ranking.expected) == (1, 4)


async def test_prior_release_is_kept_after_a_failed_refresh(repo: PgLocationRepo) -> None:
    rid = await seed(repo, [*FULL_2022, *FULL_2023])
    first = await repo.publish(rid, defn=powiat_defn(), policy=policy("0.75", 3), year=2023)
    with pytest.raises(NotPublishableError):
        await repo.publish(rid, defn=powiat_defn(), policy=policy("1.0", 9), year=2023)  # cohort too small
    current = await repo.current_release("test_density", 1, 2023)
    assert current is not None
    assert current.release_id == first.release_id
    served = await published_indicator(
        repo, powiat_defn(), policy("0.75", 3), territory_id="P0201", year=2023
    )
    assert served is not None
    assert served.release_id == first.release_id


async def test_late_rows_after_a_release_suppress_instead_of_changing_ranks(repo: PgLocationRepo) -> None:
    rid = await seed(repo, FULL_2023[:3])  # P0204 has no row: 3 of 4 eligible
    release = await repo.publish(rid, defn=powiat_defn(), policy=policy("0.75", 3), year=2023)
    before = await published_indicator(
        repo, powiat_defn(), policy("0.75", 3), territory_id="P0201", year=2023
    )
    assert before is not None
    assert not before.ranking.suppressed
    assert len(before.ranking.ranking.entries) == 3
    # A later run fills the gap; the release is immutable, so the served ranks must not silently change.
    later = await repo.start_run(
        variable_id="TESTV1",
        unit_level=5,
        years=(2023,),
        reference_version=1,
        metric_key="test_density",
        metric_version=1,
    )
    assert await repo.claim_run(later.run_id, OWNER, 60) is not None
    await repo.record_page(later.run_id, OWNER, page_index=0, observations=[FULL_2023[3]], lease_s=60)
    after = await published_indicator(repo, powiat_defn(), policy("0.75", 3), territory_id="P0201", year=2023)
    assert after is not None
    assert after.release_id == release.release_id
    assert after.ranking.suppressed
    assert after.ranking.ranking.entries == ()


async def test_trend_reads_the_stored_series(repo: PgLocationRepo) -> None:
    await seed(repo, [*FULL_2022, *FULL_2023])
    t = await load_trend(repo, powiat_defn(), "P0201", [2022, 2023])
    assert t.state is TrendState.complete
    assert t.span.absolute_change == Decimal(2)
