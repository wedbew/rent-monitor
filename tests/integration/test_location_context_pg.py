"""BDL persistence and resumable ingestion on real Postgres (RM-391, LCTX-01b part 2).

LEGAL[third-party-data]: exercises storage of GUS BDL statistics; no network, hand-built fixtures (RM-391).

Metric keys and the variable id `TESTV1` are TEST-ONLY. No metric is selected or activated (B-023); the
publication policies below are test inputs, not owner decisions.
"""

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import httpx
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
)
from rm_core.deadline import Deadline
from rm_core.location_repo import (
    IngestRun,
    LeaseLostError,
    NotPublishableError,
    PageOutOfOrderError,
    PgLocationRepo,
    ReferenceConflictError,
    RunStateError,
)
from rm_worker.clients.bdl import (
    BdlClient,
    BdlMetricBinding,
    BdlObservationValidator,
    BdlQuotaExhausted,
    BdlUnavailable,
    QuotaGate,
    QuotaWindow,
    UnexpectedDataError,
    UnknownVariableError,
)
from rm_worker.clients.bdl_quota import PgQuotaGate
from rm_worker.tasks.location_context import BDL_BINDINGS, IngestOutcome, ingest_variable
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration]

Sessions = async_sessionmaker[AsyncSession]
FIX = Path(__file__).parent.parent / "fixtures" / "bdl"
TABLES = (
    "app.location_quota_stamp, app.location_publication_pointer, app.location_publication,"
    " app.location_ingest_run, app.location_observation, app.location_territory, app.location_reference"
)
G = TerritoryLevel.gmina
YEARS = (2022, 2023)
GMINAS = ("0000000001", "0000000002", "0000000003")


def territories() -> list[TerritoryRef]:
    out = [
        TerritoryRef(territory_id="PL", teryt="", name="Polska", level=TerritoryLevel.country),
        TerritoryRef(
            territory_id="W02", teryt="02", name="Woj", level=TerritoryLevel.wojewodztwo, parent_id="PL"
        ),
        TerritoryRef(
            territory_id="P0201", teryt="0201", name="Pow", level=TerritoryLevel.powiat, parent_id="W02"
        ),
    ]
    out += [
        TerritoryRef(territory_id=t, teryt=f"020101{i}", name=f"G{i}", level=G, parent_id="P0201")
        for i, t in enumerate(GMINAS, start=1)
    ]
    return out


def defn() -> MetricDefinition:
    return MetricDefinition(
        key="test_population",
        version=1,
        name_pl="test",
        unit="osoba",
        native_level=G,
        published_levels=frozenset({G}),
        direction=Direction.neutral,
        selection=SelectionStatus.selected,
        bdl_variable_id="TESTV1",
        min_value=Decimal(0),
    )


def validator() -> BdlObservationValidator:
    b = BdlMetricBinding(
        variable_id="TESTV1", definition=defn(), expected_unit="osoba", suppressed_attr_ids=frozenset({2})
    )
    return BdlObservationValidator(bindings={"TESTV1": b})


class NoWait:
    async def acquire(self, *, max_wait_s: float) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


def fixture(name: str) -> str:
    return (FIX / name).read_text()


class Source:
    """Fake BDL transport: records requests, can fail chosen pages, can hold page 0 open."""

    def __init__(self, *, fail_pages: set[int] | None = None, gate: asyncio.Event | None = None) -> None:
        self.requests: list[str] = []
        self.fail_pages = fail_pages or set()
        self.gate = gate
        self.entered = asyncio.Event()

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/variables/TESTV1"):
            return httpx.Response(200, text=fixture("variable_meta.json"))
        page = int(request.url.params["page"])
        self.requests.append(f"page={page}")
        self.entered.set()
        if self.gate is not None and page == 0:
            await self.gate.wait()
        if page in self.fail_pages:
            return httpx.Response(503)
        return httpx.Response(200, text=fixture(f"data_page{page}.json"))

    def client(self, quota: QuotaGate | None = None) -> BdlClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return BdlClient(http=http, quota=quota or NoWait(), sleep=no_sleep)


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


async def run_once(
    repo: PgLocationRepo, source: Source, owner: str = "w1", *, reference_version: int = 1
) -> IngestOutcome:
    return await ingest_variable(
        repo,
        source.client(),
        validator(),
        variable_id="TESTV1",
        unit_level=6,
        years=YEARS,
        reference_version=reference_version,
        owner=owner,
        deadline=Deadline.after(30),
    )


async def the_run(repo: PgLocationRepo, reference_version: int = 1) -> IngestRun:
    return await repo.start_run(
        variable_id="TESTV1",
        unit_level=6,
        years=YEARS,
        reference_version=reference_version,
        metric_key="test_population",
        metric_version=1,
    )


async def count(engine: AsyncEngine, table: str, where: str = "true") -> int:
    async with engine.connect() as c:
        return int(await c.scalar(text(f"SELECT count(*) FROM app.{table} WHERE {where}")) or 0)  # noqa: S608  (test helper, constants only)


# --- reference ---------------------------------------------------------------------------------------


async def test_reference_round_trips_and_is_idempotent(repo: PgLocationRepo) -> None:
    stored = await repo.get_reference(1)
    assert stored is not None
    assert {t.territory_id for t in stored} == {"PL", "W02", "P0201", *GMINAS}
    assert next(t for t in stored if t.territory_id == GMINAS[0]).teryt == "0201011"  # string, no int cast
    await repo.ensure_reference(1, "test reference", territories())  # same content: no-op
    with pytest.raises(ReferenceConflictError):
        await repo.ensure_reference(1, "test reference", territories()[:-1])


async def test_reference_rows_are_immutable(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    async with engine.connect() as c:
        with pytest.raises(DBAPIError, match="immutable"):
            await c.execute(text("UPDATE app.location_territory SET name = 'x'"))


_INSERT_TERRITORY = (
    "INSERT INTO app.location_territory (reference_version, territory_id, teryt, name, level, parent_id)"
    " VALUES (1, :id, :teryt, 'n', 'gmina', :parent)"
)


async def test_orphan_parent_is_refused_by_the_database(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    async with engine.connect() as c:
        with pytest.raises(IntegrityError):
            await c.execute(text(_INSERT_TERRITORY), {"id": "X1", "teryt": "0299999", "parent": "NOPE"})


async def test_duplicate_teryt_at_one_level_is_refused(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    async with engine.connect() as c:
        with pytest.raises(IntegrityError):
            await c.execute(text(_INSERT_TERRITORY), {"id": "X2", "teryt": "0201011", "parent": "P0201"})


# --- ingestion ---------------------------------------------------------------------------------------


async def test_full_run_persists_typed_observations_and_gaps(
    engine: AsyncEngine, repo: PgLocationRepo
) -> None:
    out = await run_once(repo, Source())
    assert out.status == "complete"
    assert out.pages_fetched == 2
    rows = [
        *await repo.observations("test_population", 1, 2022),
        *await repo.observations("test_population", 1, 2023),
    ]
    obs = {(o.territory_id, o.year): o for o in rows}
    assert obs[(GMINAS[0], 2022)].value == Decimal(1200)
    assert obs[(GMINAS[1], 2022)].status is ObservationStatus.measured  # a genuine zero is a value
    assert obs[(GMINAS[1], 2022)].value == Decimal(0)
    assert obs[(GMINAS[1], 2023)].status is ObservationStatus.suppressed  # attrId 2
    assert obs[(GMINAS[2], 2023)].status is ObservationStatus.missing  # source returned no row
    assert len(obs) == 6  # every expected (territory, year) has exactly one typed row
    assert await count(engine, "location_observation") == 6


async def test_observations_have_no_price_columns(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    async with engine.connect() as c:
        cols = {
            r[0]
            for r in await c.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema='app' AND table_name='location_observation'"
                )
            )
        }
    assert not {"price_basis", "price", "asking", "deed"} & cols  # invariant 2: no price semantics here


async def test_resume_after_partial_failure_starts_at_the_cursor(
    engine: AsyncEngine, repo: PgLocationRepo
) -> None:
    with pytest.raises(BdlUnavailable):
        await run_once(repo, Source(fail_pages={1}))
    run = await the_run(repo)
    assert (run.state, run.next_page, run.lease_owner) == ("incomplete", 1, None)
    assert await count(engine, "location_observation") == 4  # page 0 survived the failure

    second = Source()
    out = await run_once(repo, second, owner="w2")
    assert out.status == "complete"
    assert second.requests == ["page=1"]  # page 0 was not fetched again
    assert await count(engine, "location_observation") == 6


async def test_rerun_after_completion_is_a_no_op(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    await run_once(repo, Source())
    again = Source()
    out = await run_once(repo, again)
    assert out.status == "already_complete"
    assert again.requests == []
    assert await count(engine, "location_observation") == 6


async def test_two_concurrent_runs_do_not_both_write(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    gate = asyncio.Event()
    holder = Source(gate=gate)
    first = asyncio.create_task(run_once(repo, holder, owner="w1"))
    await holder.entered.wait()  # w1 holds the lease and waits on page 0
    rival = Source()
    out = await run_once(repo, rival, owner="w2")
    assert out.status == "busy"
    assert rival.requests == []  # the rival never touched the network
    gate.set()
    assert (await first).status == "complete"
    assert await count(engine, "location_observation") == 6
    assert await count(engine, "location_ingest_run", "state = 'complete'") == 1


async def test_expired_lease_is_taken_over_and_the_old_owner_cannot_write(
    engine: AsyncEngine, repo: PgLocationRepo
) -> None:
    run = await the_run(repo)
    assert await repo.claim_run(run.run_id, "w1", 300) is not None
    assert await repo.claim_run(run.run_id, "w2", 300) is None
    async with engine.begin() as c:
        await c.execute(
            text("UPDATE app.location_ingest_run SET lease_expires_at = now() - interval '1 second'")
        )
    assert await repo.claim_run(run.run_id, "w2", 300) is not None
    with pytest.raises(LeaseLostError):
        await repo.record_page(run.run_id, "w1", page_index=0, observations=[], lease_s=300)


async def test_page_replay_is_idempotent_and_skipping_is_refused(repo: PgLocationRepo) -> None:
    run = await the_run(repo)
    await repo.claim_run(run.run_id, "w1", 300)
    obs = [
        Observation(
            territory_id=GMINAS[0],
            metric_key="test_population",
            metric_version=1,
            year=2022,
            status=ObservationStatus.measured,
            value=Decimal(5),
            source_digest="a" * 64,
        )
    ]
    first = await repo.record_page(run.run_id, "w1", page_index=0, observations=obs, lease_s=300)
    again = await repo.record_page(run.run_id, "w1", page_index=0, observations=obs, lease_s=300)
    assert (first.inserted, again.replayed, again.inserted) == (1, True, 0)
    with pytest.raises(PageOutOfOrderError):
        await repo.record_page(run.run_id, "w1", page_index=5, observations=[], lease_s=300)
    changed = [obs[0].model_copy(update={"source_digest": "b" * 64, "value": Decimal(6)})]
    report = await repo.record_page(run.run_id, "w1", page_index=1, observations=changed, lease_s=300)
    assert (report.inserted, report.conflicts) == (0, 1)
    assert (await repo.observations("test_population", 1, 2022))[0].value == Decimal(5)  # first fact stays


async def test_units_outside_the_reference_are_ignored_not_fatal(
    engine: AsyncEngine, repo: PgLocationRepo
) -> None:
    """BDL lists urban/rural parts, districts and defunct gminas next to the current whole ones; the reference
    holds only the latter, so the rest is skipped and the run still completes (live finding, RM-48)."""
    await repo.ensure_reference(2, "smaller", territories()[:-1])  # gmina 3 is unknown to this reference
    outcome = await run_once(repo, Source(), reference_version=2)
    assert outcome.status == "complete"
    stored = {o.territory_id for y in YEARS for o in await repo.observations("test_population", 1, y)}
    assert GMINAS[2] not in stored  # never stored for a territory the reference does not know


async def test_bad_data_fails_the_run_terminally(engine: AsyncEngine, repo: PgLocationRepo) -> None:
    with pytest.raises(UnexpectedDataError):  # the fixture carries a year this run did not ask for
        await ingest_variable(
            repo,
            Source().client(),
            validator(),
            variable_id="TESTV1",
            unit_level=6,
            years=(YEARS[0],),
            reference_version=1,
            owner="w1",
            deadline=Deadline.after(30),
        )
    async with engine.connect() as c:
        state = await c.scalar(
            text("SELECT state FROM app.location_ingest_run WHERE years = CAST(:y AS integer[])"),
            {"y": [YEARS[0]]},
        )
    assert state == "failed"
    with pytest.raises(RunStateError):  # a failed run is not silently retried
        await ingest_variable(
            repo,
            Source().client(),
            validator(),
            variable_id="TESTV1",
            unit_level=6,
            years=(YEARS[0],),
            reference_version=1,
            owner="w1",
            deadline=Deadline.after(30),
        )


async def test_no_binding_means_no_request(repo: PgLocationRepo) -> None:
    assert "TESTV1" not in BDL_BINDINGS  # test-only ids are never part of the shipped registry
    source = Source()
    with pytest.raises(UnknownVariableError):
        await ingest_variable(
            repo,
            source.client(),
            BdlObservationValidator(bindings={}),
            variable_id="TESTV1",
            unit_level=6,
            years=YEARS,
            reference_version=1,
            owner="w1",
            deadline=Deadline.after(30),
        )
    assert source.requests == []


# --- publication -------------------------------------------------------------------------------------


def policy(coverage: str | None, size: int | None) -> PublicationPolicy:
    return PublicationPolicy(
        metric_key="test_population",
        metric_version=1,
        min_coverage=None if coverage is None else Decimal(coverage),
        min_cohort_size=size,
    )


async def test_publication_fails_closed_without_a_decided_policy(
    engine: AsyncEngine, repo: PgLocationRepo
) -> None:
    out = await run_once(repo, Source())
    rid = out.run.run_id
    with pytest.raises(NotPublishableError):
        await repo.publish(rid, defn=defn(), policy=None, year=2022)
    with pytest.raises(NotPublishableError):  # undecided thresholds are not a pass
        await repo.publish(rid, defn=defn(), policy=policy(None, None), year=2022)
    assert await repo.current_release("test_population", 1, 2022) is None
    assert await count(engine, "location_publication_pointer") == 0


async def test_publication_needs_a_complete_run(repo: PgLocationRepo) -> None:
    with pytest.raises(BdlUnavailable):
        await run_once(repo, Source(fail_pages={1}))
    run = await the_run(repo)
    with pytest.raises(NotPublishableError, match="incomplete"):
        await repo.publish(run.run_id, defn=defn(), policy=policy("0.5", 1), year=2022)


async def test_publish_moves_the_pointer_and_a_failed_gate_keeps_the_previous_release(
    repo: PgLocationRepo,
) -> None:
    out = await run_once(repo, Source())
    rid = out.run.run_id
    first = await repo.publish(rid, defn=defn(), policy=policy("0.6", 2), year=2022)  # 3 of 3 measured
    assert (first.expected, first.eligible) == (3, 3)
    again = await repo.publish(rid, defn=defn(), policy=policy("0.6", 2), year=2022)
    assert again.release_id == first.release_id  # idempotent
    with pytest.raises(NotPublishableError):  # 2023: one measured of three, below 0.6
        await repo.publish(rid, defn=defn(), policy=policy("0.6", 2), year=2023)
    assert await repo.current_release("test_population", 1, 2023) is None
    with pytest.raises(NotPublishableError):  # a stricter policy on 2022 fails and leaves the pointer alone
        await repo.publish(rid, defn=defn(), policy=policy("1.0", 4), year=2022)
    current = await repo.current_release("test_population", 1, 2022)
    assert current is not None
    assert current.release_id == first.release_id


async def test_failed_refresh_leaves_the_prior_publication(repo: PgLocationRepo) -> None:
    out = await run_once(repo, Source())
    first = await repo.publish(out.run.run_id, defn=defn(), policy=policy("0.6", 2), year=2022)
    await repo.ensure_reference(3, "next vintage", territories())
    with pytest.raises(BdlUnavailable):
        await run_once(repo, Source(fail_pages={0, 1}), reference_version=3)
    current = await repo.current_release("test_population", 1, 2022)
    assert current is not None
    assert current.release_id == first.release_id


# --- shared quota ------------------------------------------------------------------------------------


async def test_quota_is_shared_across_gate_instances(sessions: Sessions, repo: PgLocationRepo) -> None:
    windows = (QuotaWindow(limit=2, seconds=60.0),)
    a = PgQuotaGate(sessions, windows=windows)
    b = PgQuotaGate(sessions, windows=windows)  # another worker process, same database
    await a.acquire(max_wait_s=0)
    await b.acquire(max_wait_s=0)
    with pytest.raises(BdlQuotaExhausted) as info:
        await a.acquire(max_wait_s=0)
    assert 0 < info.value.retry_after_s <= 60
    with pytest.raises(BdlQuotaExhausted):
        await b.acquire(max_wait_s=0)


async def test_quota_concurrent_acquires_never_exceed_the_limit(
    engine: AsyncEngine, sessions: Sessions, repo: PgLocationRepo
) -> None:
    gates = [PgQuotaGate(sessions, windows=(QuotaWindow(limit=3, seconds=60.0),)) for _ in range(8)]
    results = await asyncio.gather(*(g.acquire(max_wait_s=0) for g in gates), return_exceptions=True)
    assert sum(r is None for r in results) == 3
    assert all(isinstance(r, BdlQuotaExhausted) for r in results if r is not None)
    assert await count(engine, "location_quota_stamp") == 3


async def test_quota_waits_for_a_slot_within_the_budget(sessions: Sessions, repo: PgLocationRepo) -> None:
    gate = PgQuotaGate(sessions, windows=(QuotaWindow(limit=1, seconds=0.5),))
    await gate.acquire(max_wait_s=0)
    await gate.acquire(max_wait_s=5)  # sleeps about half a second, then takes the next slot


async def test_ingestion_shares_the_quota_with_other_workers(
    sessions: Sessions, repo: PgLocationRepo
) -> None:
    windows = (QuotaWindow(limit=2, seconds=60.0),)
    await PgQuotaGate(sessions, windows=windows).acquire(max_wait_s=0)  # another worker used one slot
    source = Source()
    with pytest.raises(BdlQuotaExhausted):  # meta, page 0 and page 1 need 3 slots; only 1 is left
        await ingest_variable(
            repo,
            source.client(PgQuotaGate(sessions, windows=windows)),
            validator(),
            variable_id="TESTV1",
            unit_level=6,
            years=YEARS,
            reference_version=1,
            owner="w1",
            deadline=Deadline.after(30),
        )
    assert (await the_run(repo)).state == "incomplete"
