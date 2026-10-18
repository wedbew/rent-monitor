"""Per-metric BDL location indicators: intensity, trend, comparison, rank with coverage, suppression.

LCTX-02a (RM-396). Pure, deterministic functions over `Observation` rows plus two thin async loaders that read
through `PgLocationRepo` and serve only what a fail-closed `publish` released. There is NO composite index
here: combining metrics needs the owner's policy (B-023) and is a later slice.

LEGAL[third-party-data]: derives indicators from GUS BDL statistics; attribution/redistribution terms are
unreviewed (B-023, B-012) (RM-396)
GDPR[processor]: aggregate public statistics only, no personal data (RM-396)

Rules: values are `Decimal` and rounded half-even to a stated quantum; a powiat value shown for a gmina is
labelled `proxy` and is never substituted by anything else; a parent's value is its own published value and is
never built from its children; a thin or undecided cohort is suppressed (no ranks), not shown with a caveat;
differences are absolute and in the metric's unit (no multiplier, no property-grade conversion).
"""

from collections.abc import Collection, Iterable, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from itertools import pairwise

from pydantic import BaseModel, ConfigDict
from rm_contracts.location_context import (
    BoundaryBreak,
    ComparisonState,
    GateResult,
    GateVerdict,
    LocationMetricView,
    MetricDefinition,
    Observation,
    ObservationStatus,
    PeriodComparison,
    PublicationPolicy,
    RankingResult,
    ViewState,
)

from rm_core.location_contracts import (
    LocationContractError,
    TerritoryHierarchy,
    compare_years,
    evaluate_gate,
    rank_territories,
    view_metric,
)
from rm_core.location_repo import PgLocationRepo, PublicationRelease

INDICATOR_METHOD_VERSION = 1
_QUANT = Decimal("0.0001")
_TWO = Decimal(2)


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_EVEN)


# --- intensity -----------------------------------------------------------------------------------------


class IntensityState(StrEnum):
    computed = "computed"
    missing_input = "missing_input"
    withheld = "withheld"
    zero_denominator = "zero_denominator"


class Intensity(_M):
    territory_id: str
    year: int
    numerator_key: str
    denominator_key: str
    per: Decimal
    state: IntensityState
    value: Decimal | None = None


def intensity(numerator: Observation, denominator: Observation, *, per: Decimal = Decimal(1000)) -> Intensity:
    """`numerator / denominator * per` for one territory and year (e.g. flats per 1000 residents)."""
    if (numerator.territory_id, numerator.year) != (denominator.territory_id, denominator.year):
        raise LocationContractError("intensity inputs must share territory and year")
    if per <= 0 or not per.is_finite():
        raise LocationContractError("per must be a positive finite number")

    def out(state: IntensityState, value: Decimal | None = None) -> Intensity:
        return Intensity(
            territory_id=numerator.territory_id,
            year=numerator.year,
            numerator_key=numerator.metric_key,
            denominator_key=denominator.metric_key,
            per=per,
            state=state,
            value=value,
        )

    pair = (numerator, denominator)
    if any(o.status is ObservationStatus.withheld for o in pair):
        return out(IntensityState.withheld)
    if any(o.status is not ObservationStatus.measured or o.value is None for o in pair):
        return out(IntensityState.missing_input)
    assert numerator.value is not None  # noqa: S101  (checked above)
    assert denominator.value is not None  # noqa: S101
    if denominator.value <= 0:
        return out(IntensityState.zero_denominator)
    return out(IntensityState.computed, _q(numerator.value / denominator.value * per))


# --- trend ---------------------------------------------------------------------------------------------


class TrendState(StrEnum):
    complete = "complete"  # every year-over-year step is comparable
    partial = "partial"
    none = "none"  # no comparable step


class Trend(_M):
    metric_key: str
    territory_id: str
    state: TrendState
    steps: tuple[PeriodComparison, ...]  # consecutive years
    span: PeriodComparison  # first year to last year, matched endpoints


def trend(
    defn: MetricDefinition,
    territory_id: str,
    years: Iterable[int],
    observations: Iterable[Observation],
    breaks: Iterable[BoundaryBreak] = (),
) -> Trend:
    """Year-over-year steps and the multi-year span for one territory; gaps are reported, never bridged."""
    ordered = sorted(set(years))
    if len(ordered) < 2:
        raise LocationContractError("a trend needs at least two distinct years")
    rows = tuple(o for o in observations if o.territory_id == territory_id)
    brks = tuple(breaks)
    steps = tuple(compare_years(defn, territory_id, a, b, rows, brks) for a, b in pairwise(ordered))
    span = compare_years(defn, territory_id, ordered[0], ordered[-1], rows, brks)
    ok = sum(1 for s in steps if s.state is ComparisonState.comparable)
    state = TrendState.complete if ok == len(steps) else TrendState.partial if ok else TrendState.none
    return Trend(metric_key=defn.key, territory_id=territory_id, state=state, steps=steps, span=span)


# --- comparison with the parent unit and peers ----------------------------------------------------------


class ContextComparison(_M):
    """One territory against its parent unit and its peers on one metric and year."""

    metric_key: str
    year: int
    own: LocationMetricView  # `direct`, or `proxy` when the source publishes only at a wider level
    parent: LocationMetricView | None  # the parent of the measured unit; its own published value only
    delta_vs_parent: Decimal | None  # own - parent, in the metric's unit
    peer_cohort_id: str | None
    peer_count: int  # measured siblings at the measured unit's level, excluding the unit itself
    peer_median: Decimal | None
    delta_vs_peer_median: Decimal | None


def _measured(view: LocationMetricView) -> Decimal | None:
    obs = view.observation
    if view.state is ViewState.unavailable or obs is None or obs.status is not ObservationStatus.measured:
        return None
    return obs.value


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return _q(ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / _TWO)


def compare_to_context(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    territory_id: str,
    year: int,
    observations: Iterable[Observation],
) -> ContextComparison:
    rows = tuple(observations)
    own = view_metric(defn, hierarchy, territory_id, year, rows)
    parent_view: LocationMetricView | None = None
    peers: list[Decimal] = []
    peer_cohort: str | None = None
    if own.measured_territory_id is not None:
        base = hierarchy.get(own.measured_territory_id)
        if base.parent_id is not None:
            candidate = view_metric(defn, hierarchy, base.parent_id, year, rows)
            # Only the parent's own value counts: a grandparent shown as the parent would mislead.
            parent_view = candidate if candidate.state is ViewState.direct else None
            peer_cohort = f"{base.level.value}:{base.parent_id}"
            for sibling in hierarchy.children(base.parent_id):
                if sibling.territory_id == base.territory_id or sibling.level is not base.level:
                    continue
                value = _measured(view_metric(defn, hierarchy, sibling.territory_id, year, rows))
                if value is not None:
                    peers.append(value)
    own_value = _measured(own)
    parent_value = _measured(parent_view) if parent_view is not None else None
    median = _median(peers)
    return ContextComparison(
        metric_key=defn.key,
        year=year,
        own=own,
        parent=parent_view,
        delta_vs_parent=own_value - parent_value
        if own_value is not None and parent_value is not None
        else None,
        peer_cohort_id=peer_cohort,
        peer_count=len(peers),
        peer_median=median,
        delta_vs_peer_median=own_value - median if own_value is not None and median is not None else None,
    )


# --- rank with coverage and suppression ----------------------------------------------------------------


class IndicatorRanking(_M):
    """A ranking that is shown only when the gate passed; otherwise the counts stay and the entries go."""

    ranking: RankingResult  # `entries` is empty when suppressed
    gate: GateResult
    suppressed: bool
    method_version: int = INDICATOR_METHOD_VERSION


def rank_indicator(
    defn: MetricDefinition,
    policy: PublicationPolicy | None,
    hierarchy: TerritoryHierarchy,
    observations: Iterable[Observation],
    *,
    year: int,
    expected: Collection[str],
    cohort_id: str,
) -> IndicatorRanking:
    """Rank the declared cohort; suppress ranks on thin coverage, a small cohort or undecided policy."""
    ranking = rank_territories(
        defn, hierarchy, observations, year=year, expected=expected, cohort_id=cohort_id
    )
    if policy is None:
        gate = GateResult(
            verdict=GateVerdict.undecided,
            eligible=ranking.eligible,
            expected=ranking.expected,
            coverage=_q(Decimal(ranking.eligible) / Decimal(ranking.expected)),
            reasons=("no publication policy decided (B-023)",),
        )
    else:
        gate = evaluate_gate(policy, defn, ranking)
    suppressed = gate.verdict is not GateVerdict.passed
    shown = ranking.model_copy(update={"entries": ()}) if suppressed else ranking
    return IndicatorRanking(ranking=shown, gate=gate, suppressed=suppressed)


# --- loaders over a published release ------------------------------------------------------------------


class PublishedIndicator(_M):
    metric_key: str
    metric_version: int
    year: int
    release_id: str
    reference_version: int
    ranking: IndicatorRanking
    comparison: ContextComparison


async def published_indicator(
    repo: PgLocationRepo,
    defn: MetricDefinition,
    policy: PublicationPolicy | None,
    *,
    territory_id: str,
    year: int,
) -> PublishedIndicator | None:
    """Indicator for one territory from the CURRENT release; None when nothing was published (fail closed).

    The release is immutable, the observation table is not (a later run may fill a gap). If the live
    eligible count no longer matches the release, the ranks are suppressed instead of silently changing.
    """
    release = await repo.current_release(defn.key, defn.version, year)
    if release is None:
        return None
    reference = await repo.get_reference(release.reference_version)
    if reference is None:  # pragma: no cover  (FK guarantees it)
        return None
    hierarchy = TerritoryHierarchy(reference)
    observations = await repo.observations(defn.key, defn.version, year)
    cohort = [t.territory_id for t in reference if t.level is defn.native_level]
    ranking = rank_indicator(
        defn, policy, hierarchy, observations, year=year, expected=cohort, cohort_id=defn.native_level.value
    )
    ranking = _pin_to_release(ranking, release)
    return PublishedIndicator(
        metric_key=defn.key,
        metric_version=defn.version,
        year=year,
        release_id=release.release_id,
        reference_version=release.reference_version,
        ranking=ranking,
        comparison=compare_to_context(defn, hierarchy, territory_id, year, observations),
    )


def _pin_to_release(ranking: IndicatorRanking, release: PublicationRelease) -> IndicatorRanking:
    if ranking.ranking.eligible == release.eligible and ranking.ranking.expected == release.expected:
        return ranking
    gate = ranking.gate.model_copy(
        update={
            "verdict": GateVerdict.failed,
            "reasons": (*ranking.gate.reasons, "observations changed since the release"),
        }
    )
    return IndicatorRanking(
        ranking=ranking.ranking.model_copy(update={"entries": ()}), gate=gate, suppressed=True
    )


async def load_trend(
    repo: PgLocationRepo,
    defn: MetricDefinition,
    territory_id: str,
    years: Sequence[int],
    breaks: Iterable[BoundaryBreak] = (),
) -> Trend:
    observations = await repo.observation_series(defn.key, defn.version, years)
    return trend(defn, territory_id, years, observations, breaks)


__all__ = [
    "INDICATOR_METHOD_VERSION",
    "ContextComparison",
    "IndicatorRanking",
    "Intensity",
    "IntensityState",
    "PublishedIndicator",
    "Trend",
    "TrendState",
    "compare_to_context",
    "intensity",
    "load_trend",
    "published_indicator",
    "rank_indicator",
    "trend",
]
