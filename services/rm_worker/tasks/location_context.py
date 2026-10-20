"""Resumable, idempotent GUS BDL ingestion (queue `batch`, LCTX-01b part 2, RM-391).

LEGAL[third-party-data]: reads public GUS BDL statistics; source terms and attribution are unreviewed
(B-023, B-012) (RM-391)
LEGAL[scraping]: automated requests to a third-party API, under a Postgres-shared request quota, a per-request
timeout and one total deadline (RM-391)
GDPR[processor]: no personal data is sent or received; aggregate territorial statistics only (RM-391)

Policy: only variables with a reviewed binding (`BDL_BINDINGS`, built from `rm_core.bdl_metrics`) are read;
the task refuses any other variable before a request is made. Publication is a separate, fail-closed step
(`PgLocationRepo.publish`); this task never publishes. A run is the deterministic id of (variable, unit
level, years, reference version); the page cursor and the page's observations commit together, so a crash
or a retry resumes at the first unsaved page.
"""

import uuid
from dataclasses import dataclass
from typing import Final, Literal

import httpx
import procrastinate
import structlog
from rm_contracts.jobs import BATCH_QUEUE
from rm_contracts.location_context import TerritoryLevel
from rm_core.bdl_metrics import METRICS, SUPPRESSED_ATTR_IDS, VALID_ATTR_IDS
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.deadline import Deadline
from rm_core.location_repo import IngestRun, PgLocationRepo, RunStateError
from rm_core.settings import get_settings

from rm_worker.app import app
from rm_worker.clients.bdl import (
    BdlClient,
    BdlCursor,
    BdlError,
    BdlMetricBinding,
    BdlObservationValidator,
    BdlUnavailable,
    UnexpectedDataError,
    UnknownVariableError,
)
from rm_worker.clients.bdl_quota import PgQuotaGate, quota_windows

log = structlog.get_logger(__name__)

INGEST_BDL_VARIABLE_TASK: Final = "rm_worker.tasks.location_context.ingest_bdl_variable"
INGEST_DEADLINE_S = 600.0
LEASE_S = 300.0
# BDL unit levels (inferred from the public API description, unverified live: RM-391-L01).
UNIT_LEVELS: Final = {
    6: TerritoryLevel.gmina,
    5: TerritoryLevel.powiat,
    2: TerritoryLevel.wojewodztwo,
    0: TerritoryLevel.country,
}
# Reviewed variable bindings, one per metric of the registry (verified live 2026-10-20, RM-48).
BDL_BINDINGS: Final[dict[str, BdlMetricBinding]] = {
    str(m.variable_id): BdlMetricBinding(
        variable_id=str(m.variable_id),
        definition=m.definition,
        expected_unit=m.unit,
        valid_attr_ids=VALID_ATTR_IDS,
        suppressed_attr_ids=SUPPRESSED_ATTR_IDS,
    )
    for m in METRICS
}
RETRY = procrastinate.RetryStrategy(max_attempts=5, exponential_wait=300, retry_exceptions={BdlUnavailable})


@dataclass(frozen=True)
class IngestOutcome:
    status: Literal["complete", "already_complete", "busy"]
    run: IngestRun
    pages_fetched: int


async def ingest_variable(
    repo: PgLocationRepo,
    client: BdlClient,
    validator: BdlObservationValidator,
    *,
    variable_id: str,
    unit_level: int,
    years: tuple[int, ...],
    reference_version: int,
    owner: str,
    deadline: Deadline,
    lease_s: float = LEASE_S,
) -> IngestOutcome:
    """Drive one variable to completion, or as far as possible; safe to call again after any failure.

    Raises `UnknownVariableError` (no binding) before any request, `BdlUnavailable`/`BdlQuotaExhausted`
    (run stays `incomplete`, resumable), `BdlError` subclasses for bad data (run becomes `failed`).
    """
    binding = validator.bindings.get(variable_id)
    if binding is None:
        raise UnknownVariableError(f"variable {variable_id} has no reviewed binding")
    level = UNIT_LEVELS.get(unit_level)
    if level is None or level not in binding.definition.published_levels:
        raise UnexpectedDataError(f"{binding.definition.key} is not published at unit level {unit_level}")
    reference = await repo.get_reference(reference_version)
    if reference is None:
        raise LookupError(f"territorial reference {reference_version} is not stored")
    expected = {t.territory_id: t for t in reference if t.level is level}
    defn = binding.definition
    run = await repo.start_run(
        variable_id=variable_id,
        unit_level=unit_level,
        years=years,
        reference_version=reference_version,
        metric_key=defn.key,
        metric_version=defn.version,
    )
    if run.state == "complete":
        return IngestOutcome("already_complete", run, 0)
    if run.state == "failed":
        raise RunStateError(
            f"run {run.run_id} failed earlier ({run.error_category}); it needs an owner decision"
        )
    claimed = await repo.claim_run(run.run_id, owner, lease_s)
    if claimed is None:
        return IngestOutcome("busy", await repo.get_run(run.run_id), 0)
    fetched = 0
    try:
        meta = await client.variable_meta(variable_id, deadline=deadline)
        validator.check_meta(meta)
        start = BdlCursor(variable_id=variable_id, unit_level=unit_level, years=years, page=claimed.next_page)
        async for page in client.pages(start, deadline=deadline):
            subset = {u.id: expected[u.id] for u in page.body.results if u.id in expected}
            report = validator.validate(
                meta, (page,), expected=subset, years=years, ignore_unknown_units=True
            )
            await repo.record_page(
                claimed.run_id,
                owner,
                page_index=page.cursor.page,
                observations=report.observations,
                lease_s=lease_s,
            )
            fetched += 1
        gaps = validator.validate(meta, (), expected=expected, years=years)
        done = await repo.complete_run(claimed.run_id, owner, gap_observations=gaps.observations)
    except BdlUnavailable as exc:
        await repo.release_run(claimed.run_id, owner, state="incomplete", error_category=type(exc).__name__)
        raise
    except BdlError as exc:  # bad shape or bad data: retrying the same input cannot fix it
        await repo.release_run(claimed.run_id, owner, state="failed", error_category=type(exc).__name__)
        raise
    log.info(
        "bdl_ingest_complete", run_id=done.run_id, pages=fetched, legal_tags=["third-party-data", "scraping"]
    )
    return IngestOutcome("complete", done, fetched)


@app.task(name=INGEST_BDL_VARIABLE_TASK, queue=BATCH_QUEUE, retry=RETRY)
async def ingest_bdl_variable(
    variable_id: str, unit_level: int, years: list[int], reference_version: int
) -> None:
    settings = get_settings()
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        sessions = make_sessionmaker(engine)
        gate = PgQuotaGate(
            sessions,
            windows=quota_windows(settings.bdl_requests_per_second, settings.bdl_requests_per_minute),
        )
        key = settings.bdl_api_key.get_secret_value()
        async with httpx.AsyncClient(follow_redirects=False) as http:
            client = BdlClient(http=http, quota=gate, api_key=key or None)
            await ingest_variable(
                PgLocationRepo(sessions),
                client,
                BdlObservationValidator(bindings=BDL_BINDINGS),
                variable_id=variable_id,
                unit_level=unit_level,
                years=tuple(years),
                reference_version=reference_version,
                owner=uuid.uuid4().hex,
                deadline=Deadline.after(INGEST_DEADLINE_S),
            )
    finally:
        await engine.dispose()
