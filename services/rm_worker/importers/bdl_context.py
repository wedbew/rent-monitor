"""GUS BDL location-context refresh: reference, ingestion of every reviewed metric, fail-closed publication.

LEGAL[third-party-data]: reads public GUS BDL statistics under the Postgres-shared request quota; source
terms and attribution are with counsel (B-012) (RM-48)
LEGAL[scraping]: automated requests to a third-party API, quota-gated, per-request timeout and total
deadline (RM-48)
GDPR[processor]: no personal data is sent or received; aggregate territorial statistics only (RM-48)

One pass, safe to repeat: the territorial reference is built once per version from the live unit lists; each
metric reads its newest ten years that the source actually holds, at every level it publishes; a run is the
deterministic id of (variable, level, years, reference), so a finished run is `already_complete` and a
crashed one resumes at its first unsaved page; publication per (metric, year) refuses when the run is
incomplete or coverage is below the metric's threshold, and the previous release stays valid (never a
partial national publication).
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

import structlog
from rm_contracts.location_context import TerritoryLevel
from rm_core.bdl_metrics import HISTORY_YEARS, METRICS, MetricSpec
from rm_core.bdl_reference import ReferenceBuild, UnitRow, build_reference
from rm_core.deadline import Deadline
from rm_core.location_repo import NotPublishableError, PgLocationRepo, run_id_for

from rm_worker.clients.bdl import BdlClient, BdlError, BdlObservationValidator
from rm_worker.tasks.location_context import IngestOutcome, ingest_variable

log = structlog.get_logger(__name__)

ANCHOR_VARIABLE: Final = "72305"  # population, in every year: a unit that has none did not exist then
ANCHOR_MIN_UNITS: Final = 3000  # a gmina-level year with fewer rows is not yet a published year
BDL_LEVEL: Final = {
    TerritoryLevel.gmina: 6,
    TerritoryLevel.powiat: 5,
    TerritoryLevel.wojewodztwo: 2,
    TerritoryLevel.country: 0,
}
MIN_ROWS_FOR_YEAR: Final = {TerritoryLevel.gmina: 1000, TerritoryLevel.powiat: 100}


@dataclass
class MetricOutcome:
    key: str
    years: tuple[int, ...] = ()
    # level -> complete | already_complete | busy | error:<kind>
    runs: dict[str, str] = field(default_factory=dict[str, str])
    published: list[int] = field(default_factory=list[int])
    refused: dict[int, str] = field(default_factory=dict[int, str])


@dataclass
class RefreshReport:
    reference_version: int
    reference_counts: dict[str, int]
    metrics: list[MetricOutcome]

    @property
    def published(self) -> int:
        return sum(len(m.published) for m in self.metrics)


async def ensure_reference(
    repo: PgLocationRepo,
    client: BdlClient,
    version: int,
    *,
    deadline: Deadline,
    min_rows: Mapping[TerritoryLevel, int] = MIN_ROWS_FOR_YEAR,
) -> dict[str, int]:
    """Build and store reference `version` once; later calls only report its counts."""
    stored = await repo.get_reference(version)
    if stored is not None:
        counts = {level.value: 0 for level in TerritoryLevel}
        for t in stored:
            counts[t.level.value] += 1
        return counts
    units = {
        level: tuple(
            UnitRow(u.id, u.name, u.level, u.parent_id) for u in await client.units(level, deadline=deadline)
        )
        for level in (0, 2, 5, 6)
    }
    meta = await client.variable_meta(ANCHOR_VARIABLE, deadline=deadline)
    year = await _latest_year(
        client, ANCHOR_VARIABLE, TerritoryLevel.gmina, meta.years, deadline, min_rows=min_rows
    )
    if year is None:
        raise BdlError("the anchor variable has no usable year")
    active = {
        5: await client.unit_ids_with_values(ANCHOR_VARIABLE, 5, year, deadline=deadline),
        6: await client.unit_ids_with_values(ANCHOR_VARIABLE, 6, year, deadline=deadline),
    }
    build: ReferenceBuild = build_reference(units, active)
    await repo.ensure_reference(version, f"gus-bdl:units+population:{year}", build.territories)
    log.info(
        "bdl_reference_built",
        version=version,
        year=year,
        counts=build.counts(),
        excluded={k: len(v) for k, v in build.excluded.items()},
    )
    return build.counts()


async def _latest_year(
    client: BdlClient,
    variable_id: str,
    level: TerritoryLevel,
    years: Sequence[int],
    deadline: Deadline,
    *,
    min_rows: Mapping[TerritoryLevel, int],
) -> int | None:
    """Newest year (of the newest four) that has enough unit rows at the level to be a published year."""
    needed = min_rows.get(level, 1)
    for year in sorted(years, reverse=True)[:4]:
        if await client.record_count(variable_id, BDL_LEVEL[level], year, deadline=deadline) >= needed:
            return year
    return None


async def plan_years(
    client: BdlClient,
    spec: MetricSpec,
    deadline: Deadline,
    min_rows: Mapping[TerritoryLevel, int] = MIN_ROWS_FOR_YEAR,
) -> tuple[int, ...]:
    meta = await client.variable_meta(str(spec.variable_id), deadline=deadline)
    latest = await _latest_year(
        client, str(spec.variable_id), spec.native, meta.years, deadline, min_rows=min_rows
    )
    if latest is None:
        return ()
    return tuple(sorted(y for y in meta.years if latest - HISTORY_YEARS < y <= latest))


async def refresh_context(
    repo: PgLocationRepo,
    client: BdlClient,
    *,
    reference_version: int,
    metrics: Sequence[MetricSpec] = METRICS,
    validator: BdlObservationValidator,
    per_run_deadline_s: float = 900.0,
    min_rows: Mapping[TerritoryLevel, int] = MIN_ROWS_FOR_YEAR,
) -> RefreshReport:
    """Reference, then every metric at every published level, then publication of each year that passes."""
    counts = await ensure_reference(
        repo, client, reference_version, deadline=Deadline.after(900.0), min_rows=min_rows
    )
    owner = uuid.uuid4().hex
    outcomes: list[MetricOutcome] = []
    for spec in metrics:
        outcome = MetricOutcome(spec.key)
        outcomes.append(outcome)
        try:
            outcome.years = await plan_years(client, spec, Deadline.after(120.0), min_rows)
        except BdlError as exc:
            outcome.runs["plan"] = f"error:{type(exc).__name__}"
            continue
        if not outcome.years:
            outcome.runs["plan"] = "error:no_year_with_data"
            continue
        native_run: str | None = None
        for level in sorted(spec.published_levels, key=lambda lv: (lv is not spec.native, BDL_LEVEL[lv])):
            variable = str(spec.variable_id)
            try:
                done: IngestOutcome = await ingest_variable(
                    repo,
                    client,
                    validator,
                    variable_id=variable,
                    unit_level=BDL_LEVEL[level],
                    years=outcome.years,
                    reference_version=reference_version,
                    owner=owner,
                    deadline=Deadline.after(per_run_deadline_s),
                )
                outcome.runs[level.value] = done.status
                if level is spec.native:
                    native_run = run_id_for(variable, BDL_LEVEL[level], outcome.years, reference_version)
            except BdlError as exc:
                outcome.runs[level.value] = f"error:{type(exc).__name__}"
                log.warning(
                    "bdl_metric_level_failed", metric=spec.key, level=level.value, kind=type(exc).__name__
                )
        if native_run is None:
            continue
        for year in outcome.years:
            try:
                await repo.publish(native_run, defn=spec.definition, policy=spec.policy, year=year)
                outcome.published.append(year)
            except NotPublishableError as exc:
                outcome.refused[year] = str(exc)[:160]
    report = RefreshReport(reference_version, counts, outcomes)
    log.info(
        "bdl_refresh_done",
        legal_tags=["third-party-data", "scraping"],
        reference_version=reference_version,
        metrics=len(outcomes),
        published=report.published,
    )
    return report
