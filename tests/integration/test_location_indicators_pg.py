"""LCTX-02a (RM-396): indicators computed from a published release, on real Postgres.

LEGAL[third-party-data]: hand-built fictional statistics, no network; metric keys and policies are TEST-ONLY.
Nothing is selected or activated (B-023).
"""

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from rm_contracts.location_context import (
    ChangeBasis,
    Direction,
    MetricDefinition,
    Observation,
    ObservationStatus,
    PublicationPolicy,
    SelectionStatus,
    TerritoryLevel,
    TerritoryRef,
)
from rm_core.location_indicators import (
    Basis,
    IndicatorThresholds,
    NoReleaseError,
    PeerState,
    TrendState,
    snapshot_from_release,
)
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
GMINAS = ("0000000001", "0000000002", "0000000003", "0000000004")
DIGEST = "c" * 64
TH = IndicatorThresholds(min_peers=3, min_trend_steps=1)  # TEST-ONLY
OK_POLICY = PublicationPolicy(
    metric_key="test_metric", metric_version=1, min_coverage=Decimal("0.5"), min_cohort_size=2
)


def territories() -> list[TerritoryRef]:
    out = [
        TerritoryRef(territory_id="PL", teryt="", name="Polska", level=TerritoryLevel.country),
        TerritoryRef(
            territory_id="W02", teryt="02", name="W", level=TerritoryLevel.wojewodztwo, parent_id="PL"
        ),
        TerritoryRef(territory_id="P0201", teryt="0201", name="P", level=P, parent_id="W02"),
    ]
    out += [
        TerritoryRef(territory_id=t, teryt=f"020101{i}", name=f"G{i}", level=G, parent_id="P0201")
        for i, t in enumerate(GMINAS, start=1)
    ]
    return out


def gmina_metric(**kw: object) -> MetricDefinition:
    base: dict[str, object] = {
        "key": "test_metric",
        "version": 1,
        "name_pl": "test",
        "unit": "szt.",
        "native_level": G,
        "published_levels": frozenset({G}),
        "change_basis": ChangeBasis.percent,
        "direction": Direction.higher_is_favorable,
        "min_value": Decimal(0),
        "selection": SelectionStatus.selected,
        "bdl_variable_id": "TESTV1",
    }
    base.update(kw)
    return MetricDefinition.model_validate(base)


def powiat_metric() -> MetricDefinition:
    return gmina_metric(key="test_metric", native_level=P, published_levels=frozenset({P}))


def obs(
    tid: str, value: str | None, year: int, status: str = "measured", key: str = "test_metric"
) -> Observation:
    return Observation(
        territory_id=tid,
        metric_key=key,
        metric_version=1,
        year=year,
        status=ObservationStatus(status),
        value=None if value is None else Decimal(value),
        reason=None if status == "measured" else "test gap",
        source_digest=DIGEST,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def repo(engine: AsyncEngine) -> AsyncIterator[PgLocationRepo]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    r = PgLocationRepo(async_sessionmaker(engine, expire_on_commit=False))
    await r.ensure_reference(1, "test reference", territories())
    yield r
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def load_run(
    repo: PgLocationRepo,
    rows: list[Observation],
    years: tuple[int, ...],
    *,
    variable: str = "TESTV1",
    complete: bool = True,
) -> str:
    run = await repo.start_run(
        variable_id=variable,
        unit_level=6,
        years=years,
        reference_version=1,
        metric_key="test_metric",
        metric_version=1,
    )
    assert await repo.claim_run(run.run_id, "w1", 60) is not None
    await repo.record_page(run.run_id, "w1", page_index=0, observations=rows, lease_s=60)
    if complete:
        await repo.complete_run(run.run_id, "w1", gap_observations=[])
    else:
        await repo.release_run(run.run_id, "w1", state="incomplete", error_category="outage")
    return run.run_id


def gmina_rows() -> list[Observation]:
    rows = [obs(GMINAS[0], "100", 2023), obs(GMINAS[1], "200", 2023), obs(GMINAS[2], "150", 2023)]
    rows += [obs(GMINAS[3], None, 2023, "missing")]
    rows += [obs(GMINAS[0], "110", 2024), obs(GMINAS[1], "190", 2024), obs(GMINAS[2], "150", 2024)]
    rows += [obs(GMINAS[3], "80", 2024)]
    return rows


async def test_snapshot_comes_from_the_release_and_is_reproducible(repo: PgLocationRepo) -> None:
    run_id = await load_run(repo, gmina_rows(), (2023, 2024))
    defn = gmina_metric()
    await repo.publish(run_id, defn=defn, policy=OK_POLICY, year=2024)
    first = await snapshot_from_release(
        repo, defn, territory_id=GMINAS[0], year=2024, history_years=[2023], policy=OK_POLICY, thresholds=TH
    )
    again = await snapshot_from_release(
        repo, defn, territory_id=GMINAS[0], year=2024, history_years=[2023], policy=OK_POLICY, thresholds=TH
    )
    assert first == again
    assert first.digest == again.digest
    assert first.peers.state is PeerState.ok
    assert (first.peers.rank, first.peers.coverage.eligible if first.peers.coverage else None) == (3, 4)
    assert first.cohort_rank.ranking is not None
    assert next(e.territory_id for e in first.cohort_rank.ranking.entries) == GMINAS[1]  # highest, favourable
    assert first.trend is not None
    assert first.trend.state is TrendState.ok
    assert first.trend.span is not None
    assert first.trend.span.percent_change == Decimal("10.00")
    assert first.parent.basis is Basis.direct


async def test_no_release_means_nothing_is_shown(repo: PgLocationRepo) -> None:
    defn = gmina_metric()
    with pytest.raises(NoReleaseError):
        await snapshot_from_release(
            repo, defn, territory_id=GMINAS[0], year=2024, history_years=[], policy=OK_POLICY, thresholds=TH
        )
    # observations exist but the run never completed: still no release, publish refuses (fail closed)
    run_id = await load_run(repo, gmina_rows(), (2023, 2024), complete=False)
    with pytest.raises(NotPublishableError):
        await repo.publish(run_id, defn=defn, policy=OK_POLICY, year=2024)
    with pytest.raises(NoReleaseError):
        await snapshot_from_release(
            repo, defn, territory_id=GMINAS[0], year=2024, history_years=[], policy=OK_POLICY, thresholds=TH
        )


async def test_prior_release_is_kept_after_a_failed_refresh(repo: PgLocationRepo) -> None:
    defn = gmina_metric()
    good = await load_run(repo, gmina_rows(), (2023, 2024))
    release = await repo.publish(good, defn=defn, policy=OK_POLICY, year=2024)
    before = await snapshot_from_release(
        repo, defn, territory_id=GMINAS[1], year=2024, history_years=[2023], policy=OK_POLICY, thresholds=TH
    )
    # refresh 1: a run that did not finish
    partial = await load_run(repo, [obs(GMINAS[0], "1", 2024)], (2024,), variable="TESTV2", complete=False)
    with pytest.raises(NotPublishableError):
        await repo.publish(partial, defn=defn, policy=OK_POLICY, year=2024)
    # refresh 2: complete run but the gate fails (undecided policy)
    undecided = PublicationPolicy(metric_key="test_metric", metric_version=1)
    with pytest.raises(NotPublishableError):
        await repo.publish(good, defn=defn, policy=undecided, year=2024)
    current = await repo.current_release("test_metric", 1, 2024)
    assert current == release
    after = await snapshot_from_release(
        repo, defn, territory_id=GMINAS[1], year=2024, history_years=[2023], policy=OK_POLICY, thresholds=TH
    )
    assert after.digest == before.digest


async def test_release_ids_are_versioned_by_policy_and_run(repo: PgLocationRepo) -> None:
    defn = gmina_metric()
    run_id = await load_run(repo, gmina_rows(), (2023, 2024))
    a = await repo.publish(run_id, defn=defn, policy=OK_POLICY, year=2024)
    stricter = OK_POLICY.model_copy(update={"min_coverage": Decimal("0.75")})
    b = await repo.publish(run_id, defn=defn, policy=stricter, year=2024)
    assert a.release_id != b.release_id  # a new immutable release, never an edit of the first
    assert (await repo.current_release("test_metric", 1, 2024)) == b


async def test_thin_peer_cohort_is_suppressed_from_stored_rows(repo: PgLocationRepo) -> None:
    rows = [obs(GMINAS[0], "10", 2024), obs(GMINAS[1], "20", 2024)]
    rows += [obs(GMINAS[2], None, 2024, "suppressed"), obs(GMINAS[3], None, 2024, "missing")]
    defn = gmina_metric()
    run_id = await load_run(repo, rows, (2024,))
    await repo.publish(run_id, defn=defn, policy=OK_POLICY, year=2024)
    snap = await snapshot_from_release(
        repo, defn, territory_id=GMINAS[0], year=2024, history_years=[], policy=OK_POLICY, thresholds=TH
    )
    assert snap.peers.state is PeerState.suppressed
    assert snap.peers.rank is None
    assert snap.trend is None  # a single year has no trend


async def test_gmina_on_powiat_metric_is_labelled_proxy_from_stored_rows(repo: PgLocationRepo) -> None:
    defn = powiat_metric()
    rows = [obs("P0201", "500", 2023), obs("P0201", "550", 2024)]
    run_id = await load_run(repo, rows, (2023, 2024))
    policy = PublicationPolicy(
        metric_key="test_metric", metric_version=1, min_coverage=Decimal(1), min_cohort_size=1
    )
    await repo.publish(run_id, defn=defn, policy=policy, year=2024)
    snap = await snapshot_from_release(
        repo, defn, territory_id=GMINAS[2], year=2024, history_years=[2023], policy=policy, thresholds=TH
    )
    assert snap.trend is not None
    assert (snap.trend.basis, snap.trend.measured_territory_id) == (Basis.proxy, "P0201")
    assert snap.peers.basis is Basis.proxy
    assert snap.peers.state is PeerState.suppressed  # one powiat: no peers, never borrowed from gminas
    assert snap.parent.state.value == "unavailable"  # no ancestor publishes it
