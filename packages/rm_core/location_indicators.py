"""Per-metric BDL location indicators: intensity, trend, parent and peer comparison, rank, snapshot.

LCTX-02a (RM-396). Pure, deterministic functions over `Observation` rows; the only I/O is the read-only
`snapshot_from_release`, which reads rows through `PgLocationRepo` and refuses to run without a published
release (fail closed, B-023).

LEGAL[third-party-data]: derives comparisons from GUS BDL statistics; attribution and redistribution terms
are unreviewed (B-023, B-012) (RM-396)
GDPR[processor]: aggregate public statistics only, no personal data (RM-396)

Rules:
- NO composite index here (B-023 policy is open): every indicator is one metric, explained by its parts.
- A powiat value shown for a gmina is a labelled `proxy` (the unit actually measured is always named); it is
  never a property-grade figure and never feeds a financial multiplier. Parent values are read, never averaged
  from children.
- Thin coverage suppresses: a ranking or peer comparison below the caller's thresholds (or with an undecided
  policy) exposes no rank at all, only the coverage metadata and reasons.
- Ratios and changes are `Decimal`, quantised with ROUND_HALF_EVEN; there is no float.
- Thresholds are explicit inputs (`IndicatorThresholds`); this module decides none of them.
"""

import hashlib
import itertools
import json
from collections.abc import Collection, Iterable, Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from rm_contracts.location_context import (
    BoundaryBreak,
    ComparisonState,
    Direction,
    GateResult,
    GateVerdict,
    Key,
    MetricDefinition,
    Observation,
    ObservationStatus,
    PeriodComparison,
    PublicationPolicy,
    RankedEntry,
    RankingResult,
    TerritoryId,
    TerritoryLevel,
    TerritoryRef,
)

from rm_core.location_contracts import (
    ConflictingObservationError,
    LocationContractError,
    TerritoryHierarchy,
    compare_years,
    evaluate_gate,
    rank_territories,
)

INDICATOR_METHOD_VERSION = 1
_RATIO_QUANT = Decimal("0.0001")
_ZERO = Decimal(0)


class NoReleaseError(LocationContractError):
    """No published release exists for this metric version and year: nothing may be shown."""


class Basis(StrEnum):
    direct = "direct"  # the requested unit itself was measured
    proxy = "proxy"  # a wider unit (e.g. the powiat) was measured; context only


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IndicatorThresholds(_Model):
    """Caller-supplied suppression limits for one indicator view. No defaults: the owner decides (B-023)."""

    min_peers: int = Field(ge=1)  # eligible peers (including the unit) needed to show a peer rank
    min_trend_steps: int = Field(ge=1)  # comparable consecutive-year steps needed to show a trend


class Measured(_Model):
    requested_territory_id: TerritoryId
    measured_territory_id: TerritoryId
    measured_level: TerritoryLevel
    basis: Basis


def resolve_measured(
    defn: MetricDefinition, hierarchy: TerritoryHierarchy, territory_id: str
) -> Measured | None:
    """The unit whose number answers for `territory_id`: itself, a published ancestor (proxy) or none."""
    here = hierarchy.get(territory_id)
    target = here if here.level in defn.published_levels else None
    if target is None:
        target = next(
            (a for a in hierarchy.ancestors(territory_id) if a.level in defn.published_levels), None
        )
    if target is None:
        return None
    return Measured(
        requested_territory_id=territory_id,
        measured_territory_id=target.territory_id,
        measured_level=target.level,
        basis=Basis.direct if target.territory_id == territory_id else Basis.proxy,
    )


def _cells(defn: MetricDefinition, observations: Iterable[Observation]) -> dict[tuple[str, int], Observation]:
    """One row per (territory, year) for this metric version; exact repeats collapse, conflicts raise."""
    out: dict[tuple[str, int], Observation] = {}
    for o in observations:
        if (o.metric_key, o.metric_version) != (defn.key, defn.version):
            continue
        key = (o.territory_id, o.year)
        prior = out.get(key)
        if prior is not None and (prior.status, prior.value, prior.source_digest) != (
            o.status,
            o.value,
            o.source_digest,
        ):
            raise ConflictingObservationError(f"{o.territory_id}/{o.metric_key}/{o.year} conflicts")
        out[key] = o
    return out


def _measured_value(cells: dict[tuple[str, int], Observation], tid: str, year: int) -> Decimal | None:
    o = cells.get((tid, year))
    if o is None or o.status is not ObservationStatus.measured:
        return None
    return o.value


def _favorable(direction: Direction, delta: Decimal) -> bool | None:
    """Is a move of sign `delta` favourable? None for neutral metrics and for no movement."""
    if direction is Direction.neutral or delta == _ZERO:
        return None
    return (delta > _ZERO) == (direction is Direction.higher_is_favorable)


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid, odd = divmod(len(ordered), 2)
    value = ordered[mid] if odd else (ordered[mid - 1] + ordered[mid]) / Decimal(2)
    return value.quantize(_RATIO_QUANT, rounding=ROUND_HALF_EVEN)


# --- intensity -------------------------------------------------------------------------------------------


class IntensityState(StrEnum):
    ok = "ok"
    missing_input = "missing_input"
    undefined_denominator = "undefined_denominator"  # zero denominator: no ratio, never infinity
    basis_mismatch = "basis_mismatch"  # numerator and denominator measured at different units


class Intensity(_Model):
    state: IntensityState
    numerator_key: Key
    denominator_key: Key
    territory_id: TerritoryId
    year: int
    per: int
    basis: Basis | None = None
    measured_territory_id: TerritoryId | None = None
    value: Decimal | None = None
    method_version: int = INDICATOR_METHOD_VERSION


def intensity(
    numerator: MetricDefinition,
    denominator: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    territory_id: str,
    year: int,
    *,
    observations: Iterable[Observation],
    per: int,
) -> Intensity:
    """`numerator / denominator * per` for the same measured unit and year (e.g. completions per 1,000).

    The two metrics must resolve to the same measured unit; otherwise the result is `basis_mismatch` rather
    than a ratio of different territories. A zero denominator is `undefined_denominator`.
    """
    if per < 1:
        raise LocationContractError("per must be positive")
    obs = list(observations)
    base: dict[str, Any] = {
        "numerator_key": numerator.key,
        "denominator_key": denominator.key,
        "territory_id": territory_id,
        "year": year,
        "per": per,
    }
    num_at = resolve_measured(numerator, hierarchy, territory_id)
    den_at = resolve_measured(denominator, hierarchy, territory_id)
    if num_at is None or den_at is None:
        return Intensity(state=IntensityState.missing_input, **base)
    if num_at.measured_territory_id != den_at.measured_territory_id:
        return Intensity(state=IntensityState.basis_mismatch, **base)
    tid = num_at.measured_territory_id
    n = _measured_value(_cells(numerator, obs), tid, year)
    d = _measured_value(_cells(denominator, obs), tid, year)
    common: dict[str, Any] = {**base, "basis": num_at.basis, "measured_territory_id": tid}
    if n is None or d is None:
        return Intensity(state=IntensityState.missing_input, **common)
    if d == _ZERO:
        return Intensity(state=IntensityState.undefined_denominator, **common)
    value = (n / d * Decimal(per)).quantize(_RATIO_QUANT, rounding=ROUND_HALF_EVEN)
    return Intensity(state=IntensityState.ok, value=value, **common)


# --- trend -----------------------------------------------------------------------------------------------


class TrendState(StrEnum):
    ok = "ok"
    suppressed = "suppressed"  # fewer comparable steps than the threshold
    unavailable = "unavailable"  # metric not published at or above this unit


class Movement(StrEnum):
    up = "up"
    down = "down"
    flat = "flat"


class Trend(_Model):
    state: TrendState
    metric_key: Key
    territory_id: TerritoryId
    basis: Basis | None = None
    measured_territory_id: TerritoryId | None = None
    years: tuple[int, ...]
    steps: tuple[PeriodComparison, ...] = ()
    comparable_steps: int = 0
    span: PeriodComparison | None = None
    movement: Movement | None = None
    favorable: bool | None = None
    reasons: tuple[str, ...] = ()
    method_version: int = INDICATOR_METHOD_VERSION


def trend(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    territory_id: str,
    years: Collection[int],
    observations: Iterable[Observation],
    *,
    thresholds: IndicatorThresholds,
    breaks: Iterable[BoundaryBreak] = (),
) -> Trend:
    """Year-over-year steps between consecutive listed years plus the first-to-last span.

    Percent change appears only for percent-basis metrics with a positive base (`compare_years`). The trend
    is suppressed (no steps exposed as a conclusion) when fewer steps are comparable than the threshold.
    """
    ordered = tuple(sorted(set(years)))
    if len(ordered) < 2:
        raise LocationContractError("a trend needs at least two years")
    at = resolve_measured(defn, hierarchy, territory_id)
    if at is None:
        return Trend(
            state=TrendState.unavailable,
            metric_key=defn.key,
            territory_id=territory_id,
            years=ordered,
            reasons=("not published at this level or above",),
        )
    obs = list(observations)
    brk = list(breaks)
    tid = at.measured_territory_id
    steps = tuple(compare_years(defn, tid, a, b, obs, brk) for a, b in itertools.pairwise(ordered))
    comparable = sum(1 for s in steps if s.state is ComparisonState.comparable)
    span = compare_years(defn, tid, ordered[0], ordered[-1], obs, brk)
    common: dict[str, Any] = {
        "metric_key": defn.key,
        "territory_id": territory_id,
        "basis": at.basis,
        "measured_territory_id": tid,
        "years": ordered,
        "steps": steps,
        "comparable_steps": comparable,
    }
    if comparable < thresholds.min_trend_steps:
        return Trend(
            state=TrendState.suppressed,
            reasons=(f"{comparable} comparable steps below minimum {thresholds.min_trend_steps}",),
            **common,
        )
    movement: Movement | None = None
    favorable: bool | None = None
    if span.state is ComparisonState.comparable and span.absolute_change is not None:
        delta = span.absolute_change
        movement = Movement.flat if delta == _ZERO else (Movement.up if delta > _ZERO else Movement.down)
        favorable = _favorable(defn.direction, delta)
    return Trend(
        state=TrendState.ok,
        span=span,
        movement=movement,
        favorable=favorable,
        **common,
    )


# --- parent comparison -----------------------------------------------------------------------------------


class ParentState(StrEnum):
    comparable = "comparable"
    missing_own = "missing_own"
    missing_parent = "missing_parent"
    unavailable = "unavailable"  # no measured unit, or no published ancestor above it


class Relation(StrEnum):
    above = "above"
    below = "below"
    equal = "equal"


class ParentComparison(_Model):
    state: ParentState
    metric_key: Key
    year: int
    territory_id: TerritoryId
    basis: Basis | None = None
    measured_territory_id: TerritoryId | None = None
    parent_territory_id: TerritoryId | None = None
    own_value: Decimal | None = None
    parent_value: Decimal | None = None
    difference: Decimal | None = None
    ratio_to_parent: Decimal | None = None  # None when the parent value is not positive
    relation: Relation | None = None
    favorable: bool | None = None
    method_version: int = INDICATOR_METHOD_VERSION


def compare_to_parent(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    territory_id: str,
    year: int,
    observations: Iterable[Observation],
) -> ParentComparison:
    """Compare the measured unit with its nearest published ancestor (read, never built from children)."""
    base: dict[str, Any] = {"metric_key": defn.key, "year": year, "territory_id": territory_id}
    at = resolve_measured(defn, hierarchy, territory_id)
    if at is None:
        return ParentComparison(state=ParentState.unavailable, **base)
    parent = next(
        (a for a in hierarchy.ancestors(at.measured_territory_id) if a.level in defn.published_levels), None
    )
    common: dict[str, Any] = {**base, "basis": at.basis, "measured_territory_id": at.measured_territory_id}
    if parent is None:
        return ParentComparison(state=ParentState.unavailable, **common)
    cells = _cells(defn, observations)
    own = _measured_value(cells, at.measured_territory_id, year)
    par = _measured_value(cells, parent.territory_id, year)
    common["parent_territory_id"] = parent.territory_id
    if own is None:
        return ParentComparison(state=ParentState.missing_own, parent_value=par, **common)
    if par is None:
        return ParentComparison(state=ParentState.missing_parent, own_value=own, **common)
    diff = own - par
    relation = Relation.equal if diff == _ZERO else (Relation.above if diff > _ZERO else Relation.below)
    ratio = (own / par).quantize(_RATIO_QUANT, rounding=ROUND_HALF_EVEN) if par > _ZERO else None
    return ParentComparison(
        state=ParentState.comparable,
        own_value=own,
        parent_value=par,
        difference=diff,
        ratio_to_parent=ratio,
        relation=relation,
        favorable=_favorable(defn.direction, diff),
        **common,
    )


# --- ranking and peers -----------------------------------------------------------------------------------


class Coverage(_Model):
    expected: int
    eligible: int
    missing: int
    excluded: int
    ratio: Decimal | None


class IndicatorRanking(_Model):
    """A cohort ranking that exposes entries only when its publication gate passed."""

    suppressed: bool
    cohort_id: Annotated[str, StringConstraints(max_length=64)]
    coverage: Coverage
    gate: GateResult
    reasons: tuple[str, ...] = ()
    ranking: RankingResult | None = None  # None when suppressed: no rank from thin or undecided data
    method_version: int = INDICATOR_METHOD_VERSION


def rank_indicator(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    observations: Iterable[Observation],
    *,
    year: int,
    cohort: Collection[str],
    cohort_id: str,
    policy: PublicationPolicy | None,
) -> IndicatorRanking:
    """Rank a declared cohort and attach coverage; suppress it when the gate is not `passed`.

    Unlike `require_publishable` this does not raise: a thin cohort is a normal outcome with reasons.
    A missing policy is `undecided` and suppresses (B-023).
    """
    ranking = rank_territories(defn, hierarchy, observations, year=year, expected=cohort, cohort_id=cohort_id)
    if policy is None:
        gate = GateResult(
            verdict=GateVerdict.undecided,
            eligible=ranking.eligible,
            expected=ranking.expected,
            coverage=None,
            reasons=("no publication policy decided",),
        )
    else:
        gate = evaluate_gate(policy, defn, ranking)
    coverage = Coverage(
        expected=ranking.expected,
        eligible=ranking.eligible,
        missing=ranking.missing,
        excluded=ranking.excluded,
        ratio=(Decimal(ranking.eligible) / Decimal(ranking.expected)).quantize(_RATIO_QUANT)
        if ranking.expected
        else None,
    )
    passed = gate.verdict is GateVerdict.passed
    return IndicatorRanking(
        suppressed=not passed,
        cohort_id=cohort_id,
        coverage=coverage,
        gate=gate,
        reasons=gate.reasons,
        ranking=ranking if passed else None,
    )


class PeerState(StrEnum):
    ok = "ok"
    suppressed = "suppressed"
    missing_own = "missing_own"
    unavailable = "unavailable"


class PeerComparison(_Model):
    state: PeerState
    metric_key: Key
    year: int
    territory_id: TerritoryId
    basis: Basis | None = None
    measured_territory_id: TerritoryId | None = None
    cohort_id: str | None = None
    coverage: Coverage | None = None
    rank: int | None = None
    percentile: Decimal | None = None
    peer_median: Decimal | None = None
    reasons: tuple[str, ...] = ()
    method_version: int = INDICATOR_METHOD_VERSION


def compare_to_peers(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    territory_id: str,
    year: int,
    observations: Iterable[Observation],
    *,
    thresholds: IndicatorThresholds,
) -> PeerComparison:
    """Rank the measured unit among its siblings (same level, same parent) with cohort and coverage metadata.

    Shown only when enough peers carry a measured value; a thin cohort reports coverage and reasons, no rank.
    """
    base: dict[str, Any] = {"metric_key": defn.key, "year": year, "territory_id": territory_id}
    at = resolve_measured(defn, hierarchy, territory_id)
    if at is None:
        return PeerComparison(state=PeerState.unavailable, **base)
    me = hierarchy.get(at.measured_territory_id)
    if me.parent_id is None:
        return PeerComparison(
            state=PeerState.unavailable,
            reasons=("the country has no peers",),
            **base,
        )
    peers = [c.territory_id for c in hierarchy.children(me.parent_id) if c.level is me.level]
    cohort_id = f"{me.level.value}:{me.parent_id}"
    obs = list(observations)
    cells = _cells(defn, obs)
    in_cohort = [o for o in obs if o.territory_id in set(peers)]
    ranking = rank_territories(defn, hierarchy, in_cohort, year=year, expected=peers, cohort_id=cohort_id)
    coverage = Coverage(
        expected=ranking.expected,
        eligible=ranking.eligible,
        missing=ranking.missing,
        excluded=ranking.excluded,
        ratio=(Decimal(ranking.eligible) / Decimal(ranking.expected)).quantize(_RATIO_QUANT),
    )
    common: dict[str, Any] = {
        **base,
        "basis": at.basis,
        "measured_territory_id": me.territory_id,
        "cohort_id": cohort_id,
        "coverage": coverage,
    }
    if _measured_value(cells, me.territory_id, year) is None:
        return PeerComparison(state=PeerState.missing_own, **common)
    if ranking.eligible < thresholds.min_peers:
        return PeerComparison(
            state=PeerState.suppressed,
            reasons=(f"eligible {ranking.eligible} below peer minimum {thresholds.min_peers}",),
            **common,
        )
    mine: RankedEntry = next(e for e in ranking.entries if e.territory_id == me.territory_id)
    others = [e.value for e in ranking.entries if e.territory_id != me.territory_id]
    return PeerComparison(
        state=PeerState.ok,
        rank=mine.rank,
        percentile=mine.percentile,
        peer_median=_median(others) if others else None,
        **common,
    )


# --- snapshot from a published release -------------------------------------------------------------------


class IndicatorSnapshot(_Model):
    """Everything shown for one (territory, metric, year), reproducible from one immutable release."""

    release_id: str
    metric_key: Key
    metric_version: int
    year: int
    reference_version: int
    territory_id: TerritoryId
    cohort_rank: IndicatorRanking
    peers: PeerComparison
    parent: ParentComparison
    trend: Trend | None
    digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    method_version: int = INDICATOR_METHOD_VERSION


def snapshot_digest(parts: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class _Repo(Protocol):
    async def current_release(self, metric_key: str, metric_version: int, year: int) -> "_Release | None": ...
    async def get_reference(self, version: int) -> tuple[TerritoryRef, ...] | None: ...
    async def observations_for_years(
        self, metric_key: str, metric_version: int, years: Collection[int]
    ) -> tuple[Observation, ...]: ...


class _Release(Protocol):
    @property
    def release_id(self) -> str: ...
    @property
    def reference_version(self) -> int: ...


async def snapshot_from_release(
    repo: _Repo,
    defn: MetricDefinition,
    *,
    territory_id: str,
    year: int,
    history_years: Collection[int],
    policy: PublicationPolicy | None,
    thresholds: IndicatorThresholds,
    breaks: Iterable[BoundaryBreak] = (),
) -> IndicatorSnapshot:
    """Compute the indicator view from the CURRENT published release only.

    No release means `NoReleaseError`: a run that is incomplete, undecided or failed never published, so the
    previous release (if any) keeps answering. Rows are insert-once, so the result is reproducible.
    """
    release = await repo.current_release(defn.key, defn.version, year)
    if release is None:
        raise NoReleaseError(f"no published release for {defn.key} v{defn.version} {year}")
    reference = await repo.get_reference(release.reference_version)
    if reference is None:  # pragma: no cover  (FK guarantees it)
        raise NoReleaseError("release reference vanished")
    hierarchy = TerritoryHierarchy(reference)
    years = sorted({year, *history_years})
    obs = await repo.observations_for_years(defn.key, defn.version, years)
    cohort = [t.territory_id for t in reference if t.level is defn.native_level]
    rank = rank_indicator(
        defn,
        hierarchy,
        [o for o in obs if o.year == year],
        year=year,
        cohort=cohort,
        cohort_id=defn.native_level.value,
        policy=policy,
    )
    peers = compare_to_peers(defn, hierarchy, territory_id, year, obs, thresholds=thresholds)
    parent = compare_to_parent(defn, hierarchy, territory_id, year, obs)
    tr = (
        trend(defn, hierarchy, territory_id, years, obs, thresholds=thresholds, breaks=breaks)
        if len(years) >= 2
        else None
    )
    parts = {
        "release": release.release_id,
        "rank": rank.model_dump(mode="json"),
        "peers": peers.model_dump(mode="json"),
        "parent": parent.model_dump(mode="json"),
        "trend": tr.model_dump(mode="json") if tr else None,
        "method": INDICATOR_METHOD_VERSION,
    }
    return IndicatorSnapshot(
        release_id=release.release_id,
        metric_key=defn.key,
        metric_version=defn.version,
        year=year,
        reference_version=release.reference_version,
        territory_id=territory_id,
        cohort_rank=rank,
        peers=peers,
        parent=parent,
        trend=tr,
        digest=snapshot_digest(parts),
    )


__all__ = [
    "INDICATOR_METHOD_VERSION",
    "Basis",
    "Coverage",
    "IndicatorRanking",
    "IndicatorSnapshot",
    "IndicatorThresholds",
    "Intensity",
    "IntensityState",
    "Measured",
    "Movement",
    "NoReleaseError",
    "ParentComparison",
    "ParentState",
    "PeerComparison",
    "PeerState",
    "Relation",
    "Trend",
    "TrendState",
    "compare_to_parent",
    "compare_to_peers",
    "intensity",
    "rank_indicator",
    "resolve_measured",
    "snapshot_from_release",
    "trend",
]
