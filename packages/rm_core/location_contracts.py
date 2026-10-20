"""Pure BDL location logic: hierarchy, ranking, period comparison, publication gate, proxy resolution.

LCTX-01 (RM-378). No I/O, no database, no network: callers pass fully loaded observations.

LEGAL[third-party-data]: operates on GUS BDL statistics; attribution/redistribution terms unreviewed (RM-378)
GDPR[processor]: no personal data is handled (RM-378)

Rules (contract §4, §9): ranks are competition ranks (1, 2, 2, 4) with midrank percentiles; a one-unit cohort
has no percentile; parent values are never averaged from children; the expected cohort is declared by the
caller and never inferred from the rows present; thresholds left undecided (`None`) yield `undecided`, which
`require_publishable` refuses like a failure. Money-like values stay `Decimal`; there is no float here.
"""

from collections.abc import Collection, Iterable
from decimal import ROUND_HALF_EVEN, Decimal

from rm_contracts.location_context import (
    LEVEL_ORDER,
    BoundaryBreak,
    ChangeBasis,
    ComparisonState,
    Direction,
    GateResult,
    GateVerdict,
    LocationMetricView,
    MetricDefinition,
    Observation,
    ObservationStatus,
    PeriodComparison,
    PublicationPolicy,
    RankedEntry,
    RankingResult,
    SelectionStatus,
    TerritoryLevel,
    TerritoryRef,
    ViewState,
)

_PERCENTILE_QUANT = Decimal("0.0001")
_PERCENT_QUANT = Decimal("0.01")
_HALF = Decimal("0.5")


class LocationContractError(ValueError):
    """Base class: the supplied territories or observations violate the contract."""


class HierarchyError(LocationContractError):
    pass


class ConflictingObservationError(LocationContractError):
    pass


class ObservationOutOfBoundsError(LocationContractError):
    pass


class CohortError(LocationContractError):
    pass


class CoverageBelowThresholdError(LocationContractError):
    pass


class TerritoryHierarchy:
    """Validated gmina -> powiat -> wojewodztwo -> country tree. Ids are strings; levels never skip."""

    def __init__(self, territories: Iterable[TerritoryRef]) -> None:
        by_id: dict[str, TerritoryRef] = {}
        teryt_seen: set[tuple[TerritoryLevel, str]] = set()
        for ref in territories:
            if ref.territory_id in by_id:
                raise HierarchyError(f"duplicate territory id {ref.territory_id}")
            by_id[ref.territory_id] = ref
            if ref.teryt:
                key = (ref.level, ref.teryt)
                if key in teryt_seen:
                    raise HierarchyError(f"duplicate {ref.level.value} TERYT {ref.teryt}")
                teryt_seen.add(key)
        for ref in by_id.values():
            if ref.parent_id is None:
                continue
            parent = by_id.get(ref.parent_id)
            if parent is None:
                raise HierarchyError(f"{ref.territory_id}: unknown parent {ref.parent_id}")
            if LEVEL_ORDER.index(parent.level) != LEVEL_ORDER.index(ref.level) + 1:
                raise HierarchyError(f"{ref.territory_id}: parent must be one level above")
        self._by_id = by_id

    def all(self) -> list[TerritoryRef]:
        return list(self._by_id.values())

    def get(self, territory_id: str) -> TerritoryRef:
        try:
            return self._by_id[territory_id]
        except KeyError:
            raise HierarchyError(f"unknown territory {territory_id}") from None

    def ancestors(self, territory_id: str) -> list[TerritoryRef]:
        """Parents from nearest to the country, excluding the territory itself."""
        chain: list[TerritoryRef] = []
        node = self.get(territory_id)
        while node.parent_id is not None:
            node = self.get(node.parent_id)
            chain.append(node)
        return chain

    def children(self, territory_id: str) -> list[TerritoryRef]:
        self.get(territory_id)
        found = [r for r in self._by_id.values() if r.parent_id == territory_id]
        return sorted(found, key=lambda r: r.territory_id)


def _check_bounds(defn: MetricDefinition, obs: Observation) -> None:
    value = obs.value
    if obs.status is not ObservationStatus.measured or value is None:
        return
    if defn.min_value is not None and value < defn.min_value:
        raise ObservationOutOfBoundsError(f"{obs.territory_id}/{obs.metric_key}: {value} below minimum")
    if defn.max_value is not None and value > defn.max_value:
        raise ObservationOutOfBoundsError(f"{obs.territory_id}/{obs.metric_key}: {value} above maximum")


def _same_fact(a: Observation, b: Observation) -> bool:
    return (a.status, a.value, a.source_digest) == (b.status, b.value, b.source_digest)


def _index(
    defn: MetricDefinition, observations: Iterable[Observation], year: int | None = None
) -> dict[tuple[str, int], Observation]:
    """One observation per (territory, year). Exact duplicates collapse; conflicting ones raise."""
    out: dict[tuple[str, int], Observation] = {}
    for obs in observations:
        if obs.metric_key != defn.key:
            continue
        if obs.metric_version != defn.version:
            raise ConflictingObservationError(
                f"{obs.territory_id}: metric version {obs.metric_version} != definition {defn.version}"
            )
        if year is not None and obs.year != year:
            continue
        _check_bounds(defn, obs)
        key = (obs.territory_id, obs.year)
        prior = out.get(key)
        if prior is not None and not _same_fact(prior, obs):
            raise ConflictingObservationError(f"{obs.territory_id}/{obs.metric_key}/{obs.year} conflicts")
        out[key] = obs
    return out


def rank_territories(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    observations: Iterable[Observation],
    *,
    year: int,
    expected: Collection[str],
    cohort_id: str,
) -> RankingResult:
    """Rank the declared cohort on one metric and year.

    Rank 1 is the highest value, except for `lower_is_favorable` where it is the lowest. Only `measured`
    values are ranked; `withheld` counts as excluded; everything else (and absent rows) as missing.
    """
    if defn.selection is SelectionStatus.unavailable:
        raise CohortError(f"metric {defn.key} is unavailable")
    cohort = set(expected)
    if not cohort:
        raise CohortError("expected cohort is empty")
    for tid in cohort:
        if hierarchy.get(tid).level is not defn.native_level:
            raise CohortError(f"{tid}: cohort must be at the metric's native level {defn.native_level.value}")
    rows = _index(defn, observations, year)
    stray = {tid for (tid, _y) in rows} - cohort
    if stray:
        raise CohortError(f"observations outside the declared cohort: {sorted(stray)}")

    measured = {
        tid: obs.value
        for (tid, _y), obs in rows.items()
        if obs.status is ObservationStatus.measured and obs.value is not None
    }
    excluded = sum(1 for o in rows.values() if o.status is ObservationStatus.withheld)
    eligible = len(measured)
    descending = defn.direction is not Direction.lower_is_favorable
    ordered = sorted(measured.items(), key=lambda kv: (-kv[1] if descending else kv[1], kv[0]))

    def better(a: Decimal, b: Decimal) -> bool:  # is a strictly ahead of b
        return a > b if descending else a < b

    entries: list[RankedEntry] = []
    for tid, value in ordered:
        ahead = sum(1 for v in measured.values() if better(v, value))
        behind = sum(1 for v in measured.values() if better(value, v))
        equal = eligible - ahead - behind  # includes the territory itself
        percentile = None
        if eligible >= 2:
            percentile = ((Decimal(behind) + _HALF * Decimal(equal)) / Decimal(eligible)).quantize(
                _PERCENTILE_QUANT, rounding=ROUND_HALF_EVEN
            )
        entries.append(RankedEntry(territory_id=tid, value=value, rank=ahead + 1, percentile=percentile))
    return RankingResult(
        metric_key=defn.key,
        metric_version=defn.version,
        year=year,
        direction=defn.direction,
        cohort_id=cohort_id,
        level=defn.native_level,
        expected=len(cohort),
        eligible=eligible,
        missing=len(cohort) - eligible - excluded,
        excluded=excluded,
        entries=tuple(entries),
    )


def evaluate_gate(policy: PublicationPolicy, defn: MetricDefinition, ranking: RankingResult) -> GateResult:
    """Apply the owner's thresholds. A `None` threshold is undecided and never counts as a pass."""
    if (policy.metric_key, policy.metric_version) != (defn.key, defn.version):
        raise CohortError("policy does not match the metric definition version")
    if (ranking.metric_key, ranking.metric_version) != (defn.key, defn.version):
        raise CohortError("ranking does not match the metric definition version")
    coverage = (
        (Decimal(ranking.eligible) / Decimal(ranking.expected)).quantize(_PERCENTILE_QUANT)
        if ranking.expected
        else None
    )
    failures: list[str] = []
    undecided: list[str] = []
    if policy.min_coverage is None:
        undecided.append("min_coverage undecided")
    elif coverage is None or Decimal(ranking.eligible) < policy.min_coverage * Decimal(ranking.expected):
        failures.append(f"coverage {coverage} below {policy.min_coverage}")
    if policy.min_cohort_size is None:
        undecided.append("min_cohort_size undecided")
    elif ranking.eligible < policy.min_cohort_size:
        failures.append(f"eligible {ranking.eligible} below cohort minimum {policy.min_cohort_size}")
    if failures:
        verdict = GateVerdict.failed
    elif undecided:
        verdict = GateVerdict.undecided
    else:
        verdict = GateVerdict.passed
    return GateResult(
        verdict=verdict,
        eligible=ranking.eligible,
        expected=ranking.expected,
        coverage=coverage,
        reasons=tuple(failures + undecided),
    )


def require_publishable(
    policy: PublicationPolicy, defn: MetricDefinition, ranking: RankingResult
) -> GateResult:
    """Return the gate result only when it passed; fail closed on `failed` and `undecided`."""
    result = evaluate_gate(policy, defn, ranking)
    if result.verdict is not GateVerdict.passed:
        raise CoverageBelowThresholdError("; ".join(result.reasons) or result.verdict.value)
    return result


def compare_years(  # noqa: PLR0917
    defn: MetricDefinition,
    territory_id: str,
    year_a: int,
    year_b: int,
    observations: Iterable[Observation],
    breaks: Iterable[BoundaryBreak] = (),
) -> PeriodComparison:
    """Compare one territory across two years with matched endpoints.

    Percent change is given only for `percent`-basis metrics with a positive base; signed or rate-like
    metrics (and a zero or negative base) get the absolute change only.
    """
    if year_a >= year_b:
        raise LocationContractError("year_a must be before year_b")
    rows = _index(defn, (o for o in observations if o.territory_id == territory_id))
    a = rows.get((territory_id, year_a))
    b = rows.get((territory_id, year_b))

    def result(state: ComparisonState, reason: str | None, **extra: Decimal | None) -> PeriodComparison:
        return PeriodComparison(
            metric_key=defn.key,
            territory_id=territory_id,
            year_a=year_a,
            year_b=year_b,
            state=state,
            reason=reason,
            **extra,
        )

    for brk in breaks:
        if brk.territory_id == territory_id and year_a < brk.effective_year <= year_b:
            return result(ComparisonState.withheld, f"territorial break {brk.effective_year}: {brk.reason}")
    usable = (ObservationStatus.measured, ObservationStatus.withheld)
    if a is None or b is None or a.status not in usable or b.status not in usable:
        return result(ComparisonState.missing_endpoint, "an endpoint has no usable observation")
    if ObservationStatus.withheld in (a.status, b.status):
        return result(ComparisonState.withheld, "an endpoint is withheld")
    if a.value is None or b.value is None:  # unreachable by Observation validation; keeps typing honest
        return result(ComparisonState.missing_endpoint, "an endpoint has no value")
    percent: Decimal | None = None
    if defn.change_basis is ChangeBasis.percent and a.value > 0:
        percent = ((b.value - a.value) / a.value * Decimal(100)).quantize(
            _PERCENT_QUANT, rounding=ROUND_HALF_EVEN
        )
    return result(
        ComparisonState.comparable,
        None,
        value_a=a.value,
        value_b=b.value,
        absolute_change=b.value - a.value,
        percent_change=percent,
    )


def view_metric(
    defn: MetricDefinition,
    hierarchy: TerritoryHierarchy,
    territory_id: str,
    year: int,
    observations: Iterable[Observation],
) -> LocationMetricView:
    """What may be shown for a territory: its own published value, a labelled parent proxy, or nothing.

    A powiat-native metric asked for a gmina returns the powiat's value as `proxy`. A metric asked for a
    level above where it is published is `unavailable`: children are never averaged or summed here.
    """
    here = hierarchy.get(territory_id)
    if here.level in defn.published_levels:
        target = here
    else:
        target = next(
            (a for a in hierarchy.ancestors(territory_id) if a.level in defn.published_levels), None
        )
    if target is None:
        return LocationMetricView(
            requested_territory_id=territory_id,
            metric_key=defn.key,
            state=ViewState.unavailable,
            reason="not published at this level or above",
        )
    obs = _index(defn, observations, year).get((target.territory_id, year))
    base = {
        "requested_territory_id": territory_id,
        "metric_key": defn.key,
        "measured_territory_id": target.territory_id,
        "measured_level": target.level,
    }
    if obs is None or obs.status not in (ObservationStatus.measured, ObservationStatus.withheld):
        return LocationMetricView(
            **base,  # pyright: ignore[reportArgumentType]
            state=ViewState.unavailable,
            observation=obs,
            reason=obs.status.value if obs else "no observation",
        )
    state = ViewState.direct if target.territory_id == territory_id else ViewState.proxy
    return LocationMetricView(**base, state=state, observation=obs)  # pyright: ignore[reportArgumentType]
