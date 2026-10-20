"""Location context for one territory from published BDL releases (RM-282): reads, composes, never computes
money.

LEGAL[third-party-data]: presents GUS BDL statistics with their source, year, level and caveats
  (RM-282).
LEGAL[republication]: aggregates only (RM-282).
GDPR[personal-data]: none (RM-282).

Per metric it reads two small sets instead of a whole snapshot: every territory's value for the newest
published year (the national cohort and the peers need them) and the history of the measured unit and
its ancestors. The decisions (direct, proxy or unavailable; ranks only past their gates; trend only with
enough comparable steps) come from `location_indicators`; this module only assembles them into the API
shapes.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from rm_contracts.location_context import (
    MetricDefinition,
    Observation,
    ObservationStatus,
    PublicationPolicy,
    TerritoryLevel,
    TerritoryRef,
)
from rm_contracts.market_context import (
    Level,
    MetricViewOut,
    ParentValueOut,
    PointOut,
    RankOut,
    TerritoryOut,
    TrendOut,
)

from rm_core.bdl_metrics import FAMILIES, MetricSpec
from rm_core.location_contracts import TerritoryHierarchy
from rm_core.location_indicators import (
    Basis,
    IndicatorThresholds,
    ParentComparison,
    ParentState,
    PeerState,
    Trend,
    TrendState,
    compare_to_parent,
    compare_to_peers,
    rank_indicator,
    resolve_measured,
    trend,
)
from rm_core.location_repo import PgLocationRepo

THRESHOLDS = IndicatorThresholds(
    min_peers=5, min_trend_steps=3
)  # delegated policy (B-023), documented in L-045
HISTORY_POINTS = 10
RankState = Literal["ok", "suppressed", "unavailable"]


def territory_out(t: TerritoryRef) -> TerritoryOut:
    return TerritoryOut(territory_id=t.territory_id, name=t.name, level=t.level.value, teryt=t.teryt)


def _unavailable(spec: MetricSpec, reason: str) -> MetricViewOut:
    return MetricViewOut(
        key=spec.key,
        name_pl=spec.name_pl,
        family=spec.family,
        family_pl=FAMILIES[spec.family],
        unit=spec.unit_label_pl,
        note_pl=spec.note_pl,
        direction=spec.definition.direction.value,
        state="unavailable",
        reason=reason,
        measured=None,
        year=None,
        value=None,
        value_status=None,
        series=[],
        trend=None,
        parents=[],
        national=None,
        peers=None,
        release_id=None,
    )


def _rank(
    scope_level: Level,
    scope: str,
    state: RankState,
    reasons: Sequence[str],
    *,
    rank: int | None = None,
    of: int | None = None,
    percentile: Decimal | None = None,
    median: Decimal | None = None,
    coverage: Decimal | None = None,
) -> RankOut:
    return RankOut(
        scope=scope,
        scope_level=scope_level,
        state=state,
        rank=rank,
        of=of,
        percentile=percentile,
        median=median,
        coverage=coverage,
        reasons=list(reasons),
    )


def _trend_out(tr: Trend | None) -> TrendOut | None:
    if tr is None:
        return None
    span = tr.span
    return TrendOut(
        state=tr.state.value if tr.state in (TrendState.ok, TrendState.suppressed) else "unavailable",
        movement=tr.movement.value if tr.movement else None,
        favorable=tr.favorable,
        from_year=span.year_a if span else None,
        to_year=span.year_b if span else None,
        absolute_change=span.absolute_change if span else None,
        percent_change=span.percent_change if span else None,
        comparable_steps=tr.comparable_steps,
        reasons=list(tr.reasons),
    )


def _parents(
    defn: MetricDefinition,
    chain: Sequence[TerritoryRef],
    cells: dict[tuple[str, int], Observation],
    parent: ParentComparison,
    year: int,
) -> list[ParentValueOut]:
    out: list[ParentValueOut] = []
    for anc in chain[1:]:
        if anc.level not in defn.published_levels:
            continue
        c = cells.get((anc.territory_id, year))
        value = c.value if c is not None and c.status is ObservationStatus.measured else None
        nearest = parent.state is ParentState.comparable and anc.territory_id == parent.parent_territory_id
        out.append(
            ParentValueOut(
                territory=territory_out(anc),
                value=value,
                relation=parent.relation.value if nearest and parent.relation else None,
            )
        )
    return out


def _national(
    defn: MetricDefinition,
    policy: PublicationPolicy,
    hierarchy: TerritoryHierarchy,
    measured: TerritoryRef,
    latest_all: Sequence[Observation],
    *,
    year: int,
) -> RankOut:
    lvl = measured.level.value
    cohort = [t.territory_id for t in hierarchy_all(hierarchy, measured.level)]
    cohort_set = set(cohort)
    ranking = rank_indicator(
        defn,
        hierarchy,
        [o for o in latest_all if o.territory_id in cohort_set],
        year=year,
        cohort=cohort,
        cohort_id=lvl,
        policy=policy,
    )
    if ranking.suppressed or ranking.ranking is None:
        return _rank(lvl, "kraj", "suppressed", ranking.reasons, coverage=ranking.coverage.ratio)
    entries = ranking.ranking.entries
    mine = next((e for e in entries if e.territory_id == measured.territory_id), None)
    if mine is None:
        return _rank(lvl, "kraj", "unavailable", ("brak wartości dla tej jednostki",))
    values = sorted(e.value for e in entries)
    return _rank(
        lvl,
        "kraj",
        "ok",
        (),
        rank=mine.rank,
        of=len(values),
        percentile=mine.percentile,
        median=values[len(values) // 2],
        coverage=ranking.coverage.ratio,
    )


def _peers(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    measured: TerritoryRef,
    territory_id: str,
    *,
    year: int,
    obs: Sequence[Observation],
) -> RankOut:
    lvl = measured.level.value
    pc = compare_to_peers(defn, hierarchy, territory_id, year, obs, thresholds=THRESHOLDS)
    if pc.state is PeerState.ok:
        return _rank(
            lvl,
            "ten sam powiat" if lvl == "gmina" else "to samo województwo",
            "ok",
            (),
            rank=pc.rank,
            of=pc.coverage.eligible if pc.coverage else None,
            percentile=pc.percentile,
            median=pc.peer_median,
            coverage=pc.coverage.ratio if pc.coverage else None,
        )
    state: RankState = "suppressed" if pc.state is PeerState.suppressed else "unavailable"
    return _rank(lvl, "grupa porównawcza", state, pc.reasons)


async def metric_view(
    repo: PgLocationRepo,
    hierarchy: TerritoryHierarchy,
    spec: MetricSpec,
    territory_id: str,
) -> MetricViewOut:
    defn: MetricDefinition = spec.definition
    years = await repo.published_years(defn.key, defn.version)
    if not years:
        return _unavailable(spec, "Brak opublikowanych danych GUS dla tej miary.")
    year = years[-1]
    at = resolve_measured(defn, hierarchy, territory_id)
    if at is None:
        return _unavailable(spec, "Miara nie jest publikowana dla tego poziomu terytorium.")
    release = await repo.current_release(defn.key, defn.version, year)
    assert release is not None  # noqa: S101  (the year came from the pointer table)
    measured = hierarchy.get(at.measured_territory_id)
    chain = [measured, *hierarchy.ancestors(measured.territory_id)]
    window = [y for y in years if y > year - HISTORY_POINTS]
    siblings = (
        [c.territory_id for c in hierarchy.children(measured.parent_id) if c.level is measured.level]
        if measured.parent_id
        else []
    )
    latest_all = await repo.observations(defn.key, defn.version, year)
    history = await repo.observations_for(
        defn.key, defn.version, window, [t.territory_id for t in chain] + siblings
    )
    obs: list[Observation] = [*latest_all, *[o for o in history if o.year != year]]
    cells = {(o.territory_id, o.year): o for o in obs}
    own = cells.get((measured.territory_id, year))
    lvl = measured.level.value
    if measured.level is defn.native_level:
        national = _national(defn, spec.policy, hierarchy, measured, latest_all, year=year)
        peers = _peers(defn, hierarchy, measured, territory_id, year=year, obs=obs)
    else:
        # A wider unit stands in for the place (proxy or powiat fallback): ranking it against the native
        # cohort would compare unlike units, so no rank is offered.
        why = ("jednostka nadrzędna zastępuje miejsce; porównanie dotyczy poziomu źródłowego",)
        national = _rank(lvl, "kraj", "unavailable", why)
        peers = _rank(lvl, "grupa porównawcza", "unavailable", why)
    tr = (
        trend(defn, hierarchy, territory_id, window, obs, thresholds=THRESHOLDS) if len(window) >= 2 else None
    )
    measured_ok = own is not None and own.status is ObservationStatus.measured
    return MetricViewOut(
        key=spec.key,
        name_pl=spec.name_pl,
        family=spec.family,
        family_pl=FAMILIES[spec.family],
        unit=spec.unit_label_pl,
        note_pl=spec.note_pl,
        direction=defn.direction.value,
        state="direct" if at.basis is Basis.direct else "proxy",
        reason=None if measured_ok else (own.reason if own is not None else "brak wiersza źródłowego"),
        measured=territory_out(measured),
        year=year,
        value=own.value if own is not None and measured_ok else None,
        value_status=own.status.value if own is not None else "missing",
        series=[
            PointOut(year=y, value=c.value, status=c.status.value)
            for y in window
            if (c := cells.get((measured.territory_id, y))) is not None
        ],
        trend=_trend_out(tr),
        parents=_parents(
            defn, chain, cells, compare_to_parent(defn, hierarchy, territory_id, year, obs), year
        ),
        national=national,
        peers=peers,
        release_id=release.release_id,
    )


def hierarchy_all(hierarchy: TerritoryHierarchy, level: TerritoryLevel) -> list[TerritoryRef]:
    return [t for t in hierarchy.all() if t.level is level]
