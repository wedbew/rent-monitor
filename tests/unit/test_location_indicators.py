"""LCTX-02a (RM-396): per-metric BDL indicators. Pure, no DB, test-only metric keys and thresholds.

LEGAL[third-party-data]: hand-built fictional statistics; nothing is selected or activated (B-023) (RM-396).
"""

from decimal import Decimal

import pytest
from rm_contracts.location_context import (
    BoundaryBreak,
    ChangeBasis,
    ComparisonState,
    Direction,
    GateVerdict,
    MetricDefinition,
    Observation,
    ObservationStatus,
    PublicationPolicy,
    SelectionStatus,
    TerritoryLevel,
    TerritoryRef,
)
from rm_core.bdl_metrics import BY_KEY
from rm_core.location_contracts import LocationContractError, TerritoryHierarchy
from rm_core.location_indicators import (
    Basis,
    IndicatorThresholds,
    IntensityState,
    Movement,
    ParentState,
    PeerState,
    Relation,
    TrendState,
    compare_to_parent,
    compare_to_peers,
    intensity,
    rank_indicator,
    resolve_measured,
    trend,
)
from rm_worker.tasks.location_context import BDL_BINDINGS

D = Decimal
DIGEST = "b" * 64
G, P, W, C = TerritoryLevel.gmina, TerritoryLevel.powiat, TerritoryLevel.wojewodztwo, TerritoryLevel.country
TH = IndicatorThresholds(min_peers=3, min_trend_steps=2)  # TEST-ONLY values


def ref(tid: str, teryt: str, level: TerritoryLevel, parent: str | None) -> TerritoryRef:
    return TerritoryRef(territory_id=tid, teryt=teryt, name=f"n{tid}", level=level, parent_id=parent)


def hierarchy() -> TerritoryHierarchy:
    rows = [ref("PL", "", C, None), ref("W02", "02", W, "PL")]
    rows += [ref("P0201", "0201", P, "W02"), ref("P0202", "0202", P, "W02"), ref("P0203", "0203", P, "W02")]
    rows += [ref(f"g{i}", f"020100{i}", G, "P0201") for i in range(1, 6)]
    rows += [ref("h1", "0202001", G, "P0202")]
    return TerritoryHierarchy(rows)


def metric(key: str = "test_metric", **kw: object) -> MetricDefinition:
    base: dict[str, object] = {
        "key": key,
        "version": 1,
        "name_pl": "test",
        "unit": "szt.",
        "native_level": G,
        "published_levels": frozenset({G}),
        "change_basis": ChangeBasis.percent,
        "min_value": D(0),
        "selection": SelectionStatus.selected,
        "bdl_variable_id": "TESTV1",
    }
    base.update(kw)
    return MetricDefinition.model_validate(base)


def powiat_metric(key: str = "test_metric", **kw: object) -> MetricDefinition:
    return metric(key, native_level=P, published_levels=frozenset({P, W}), **kw)


def obs(
    tid: str, value: str | None, year: int = 2024, status: str = "measured", key: str = "test_metric"
) -> Observation:
    return Observation(
        territory_id=tid,
        metric_key=key,
        metric_version=1,
        year=year,
        status=ObservationStatus(status),
        value=None if value is None else D(value),
        reason=None if status == "measured" else "test gap",
        source_digest=DIGEST,
    )


def test_bdl_bindings_are_the_reviewed_registry_and_nothing_else() -> None:
    assert len(BDL_BINDINGS) == 22
    assert {b.definition.key for b in BDL_BINDINGS.values()} == set(BY_KEY)


# --- measured unit and labels -------------------------------------------------------------------------


def test_gmina_on_powiat_metric_is_a_labelled_proxy() -> None:
    at = resolve_measured(powiat_metric(), hierarchy(), "g1")
    assert at is not None
    assert (at.basis, at.measured_territory_id, at.measured_level) == (Basis.proxy, "P0201", P)
    own = resolve_measured(powiat_metric(), hierarchy(), "P0201")
    assert own is not None
    assert own.basis is Basis.direct


def test_metric_not_published_at_or_above_is_unavailable() -> None:
    assert resolve_measured(metric(), hierarchy(), "P0201") is None  # gmina-only metric, powiat asked
    out = compare_to_parent(metric(), hierarchy(), "P0201", 2024, [])
    assert out.state is ParentState.unavailable


# --- intensity ----------------------------------------------------------------------------------------


def test_intensity_is_exact_decimal_and_labelled() -> None:
    num, den = metric("test_completed"), metric("test_population")
    rows = [obs("g1", "7", key="test_completed"), obs("g1", "2000", key="test_population")]
    out = intensity(num, den, hierarchy(), "g1", 2024, observations=rows, per=1000)
    assert out.state is IntensityState.ok
    assert out.value == D("3.5000")
    assert out.basis is Basis.direct


def test_intensity_zero_denominator_missing_and_mismatch() -> None:
    num, den = metric("test_completed"), metric("test_population")
    zero = [obs("g1", "7", key="test_completed"), obs("g1", "0", key="test_population")]
    assert (
        intensity(num, den, hierarchy(), "g1", 2024, observations=zero, per=1000).state
        is IntensityState.undefined_denominator
    )
    gap = [obs("g1", "7", key="test_completed"), obs("g1", None, status="missing", key="test_population")]
    assert (
        intensity(num, den, hierarchy(), "g1", 2024, observations=gap, per=1000).state
        is IntensityState.missing_input
    )
    # numerator at powiat (proxy), denominator at gmina: different units, no ratio
    pnum = powiat_metric("test_completed")
    mixed = [obs("P0201", "7", key="test_completed"), obs("g1", "2000", key="test_population")]
    assert (
        intensity(pnum, den, hierarchy(), "g1", 2024, observations=mixed, per=1000).state
        is IntensityState.basis_mismatch
    )
    with pytest.raises(LocationContractError):
        intensity(num, den, hierarchy(), "g1", 2024, observations=zero, per=0)


def test_intensity_proxy_keeps_its_label() -> None:
    num, den = powiat_metric("test_completed"), powiat_metric("test_population")
    rows = [obs("P0201", "10", key="test_completed"), obs("P0201", "1000", key="test_population")]
    out = intensity(num, den, hierarchy(), "g2", 2024, observations=rows, per=100)
    assert (out.state, out.basis, out.measured_territory_id, out.value) == (
        IntensityState.ok,
        Basis.proxy,
        "P0201",
        D("1.0000"),
    )


# --- trend --------------------------------------------------------------------------------------------


def test_trend_steps_and_span() -> None:
    rows = [obs("g1", "100", 2022), obs("g1", "110", 2023), obs("g1", "99", 2024)]
    out = trend(metric(), hierarchy(), "g1", [2024, 2022, 2023], rows, thresholds=TH)
    assert out.state is TrendState.ok
    assert out.years == (2022, 2023, 2024)
    assert [s.percent_change for s in out.steps] == [D("10.00"), D("-10.00")]
    assert out.span is not None
    assert out.span.percent_change == D("-1.00")
    assert out.movement is Movement.down
    assert out.favorable is None  # neutral metric: no good/bad


def test_trend_direction_decides_favorable() -> None:
    rows = [obs("g1", "100", 2022), obs("g1", "110", 2023), obs("g1", "120", 2024)]
    up = trend(
        metric(direction=Direction.higher_is_favorable),
        hierarchy(),
        "g1",
        [2022, 2023, 2024],
        rows,
        thresholds=TH,
    )
    low = trend(
        metric(direction=Direction.lower_is_favorable),
        hierarchy(),
        "g1",
        [2022, 2023, 2024],
        rows,
        thresholds=TH,
    )
    assert (up.favorable, low.favorable) == (True, False)


def test_rate_like_metric_never_gets_percent() -> None:
    rows = [obs("g1", "-5", 2023), obs("g1", "3", 2024)]
    m = metric(change_basis=ChangeBasis.absolute, min_value=None)
    out = trend(
        m,
        hierarchy(),
        "g1",
        [2023, 2024],
        rows,
        thresholds=IndicatorThresholds(min_peers=1, min_trend_steps=1),
    )
    assert out.steps[0].percent_change is None
    assert out.steps[0].absolute_change == D(8)


def test_trend_suppressed_on_gaps_and_withheld_on_break() -> None:
    rows = [obs("g1", "100", 2022), obs("g1", None, 2023, "suppressed"), obs("g1", "120", 2024)]
    out = trend(metric(), hierarchy(), "g1", [2022, 2023, 2024], rows, thresholds=TH)
    assert out.state is TrendState.suppressed
    assert out.comparable_steps == 0
    assert out.movement is None
    full = [obs("g1", "100", 2022), obs("g1", "110", 2023), obs("g1", "120", 2024)]
    brk = BoundaryBreak(territory_id="g1", effective_year=2023, reason="test merge")
    held = trend(
        metric(),
        hierarchy(),
        "g1",
        [2022, 2023, 2024],
        full,
        thresholds=IndicatorThresholds(min_peers=1, min_trend_steps=1),
        breaks=[brk],
    )
    assert held.steps[0].state is ComparisonState.withheld
    assert held.steps[1].state is ComparisonState.comparable


def test_trend_on_proxy_names_the_measured_unit() -> None:
    rows = [obs("P0201", "100", 2023), obs("P0201", "120", 2024)]
    out = trend(
        powiat_metric(),
        hierarchy(),
        "g3",
        [2023, 2024],
        rows,
        thresholds=IndicatorThresholds(min_peers=1, min_trend_steps=1),
    )
    assert (out.basis, out.measured_territory_id) == (Basis.proxy, "P0201")


def test_trend_needs_two_years() -> None:
    with pytest.raises(LocationContractError):
        trend(metric(), hierarchy(), "g1", [2024], [], thresholds=TH)


# --- parent comparison --------------------------------------------------------------------------------


def test_parent_comparison_reads_the_published_parent_never_averages() -> None:
    m = metric(published_levels=frozenset({G, P}))
    rows = [
        obs("g1", "30"),
        obs("g2", "10"),
        obs("P0201", "40"),
    ]  # parent 40 is NOT the mean of children (20)
    out = compare_to_parent(m, hierarchy(), "g1", 2024, rows)
    assert out.state is ParentState.comparable
    assert (out.parent_territory_id, out.parent_value, out.difference) == ("P0201", D(40), D(-10))
    assert out.ratio_to_parent == D("0.7500")
    assert out.relation is Relation.below


def test_parent_comparison_missing_sides() -> None:
    m = metric(published_levels=frozenset({G, P}))
    assert (
        compare_to_parent(m, hierarchy(), "g1", 2024, [obs("P0201", "40")]).state is ParentState.missing_own
    )
    assert (
        compare_to_parent(m, hierarchy(), "g1", 2024, [obs("g1", "30")]).state is ParentState.missing_parent
    )
    zero = compare_to_parent(m, hierarchy(), "g1", 2024, [obs("g1", "3"), obs("P0201", "0")])
    assert zero.state is ParentState.comparable
    assert zero.ratio_to_parent is None  # no division by a zero parent


def test_proxy_unit_compares_to_the_next_published_ancestor() -> None:
    rows = [obs("P0201", "40"), obs("W02", "50")]
    out = compare_to_parent(powiat_metric(), hierarchy(), "g1", 2024, rows)
    assert (out.basis, out.measured_territory_id, out.parent_territory_id) == (Basis.proxy, "P0201", "W02")


# --- peers and ranking --------------------------------------------------------------------------------


def peer_rows() -> list[Observation]:
    return [
        obs("g1", "10"),
        obs("g2", "30"),
        obs("g3", "20"),
        obs("g4", "20"),
        obs("g5", None, status="missing"),
    ]


def test_peer_rank_cohort_and_coverage() -> None:
    out = compare_to_peers(metric(), hierarchy(), "g3", 2024, peer_rows(), thresholds=TH)
    assert out.state is PeerState.ok
    assert out.cohort_id == "gmina:P0201"
    assert (out.rank, out.percentile) == (2, D("0.5000"))  # competition rank, tied with g4
    assert out.peer_median == D("20.0000")  # median of g1, g2, g4
    assert out.coverage is not None
    assert (out.coverage.expected, out.coverage.eligible, out.coverage.missing) == (5, 4, 1)
    assert out.coverage.ratio == D("0.8000")


def test_peer_rank_is_reproducible_and_order_independent() -> None:
    a = compare_to_peers(metric(), hierarchy(), "g3", 2024, peer_rows(), thresholds=TH)
    b = compare_to_peers(metric(), hierarchy(), "g3", 2024, list(reversed(peer_rows())), thresholds=TH)
    assert a == b


def test_peer_rank_suppressed_when_thin_and_never_borrows_other_parents() -> None:
    thin = compare_to_peers(
        metric(), hierarchy(), "g1", 2024, [obs("g1", "10"), obs("g2", "5")], thresholds=TH
    )
    assert thin.state is PeerState.suppressed
    assert thin.rank is None
    assert thin.coverage is not None
    assert thin.coverage.eligible == 2
    # h1 belongs to another powiat: its own cohort has one gmina only
    alone = compare_to_peers(
        metric(), hierarchy(), "h1", 2024, [*peer_rows(), obs("h1", "99")], thresholds=TH
    )
    assert alone.state is PeerState.suppressed
    assert alone.coverage is not None
    assert alone.coverage.expected == 1


def test_peer_states_for_missing_own_and_country() -> None:
    assert (
        compare_to_peers(metric(), hierarchy(), "g5", 2024, peer_rows(), thresholds=TH).state
        is PeerState.missing_own
    )
    m = metric(native_level=C, published_levels=frozenset({C}))
    assert compare_to_peers(m, hierarchy(), "g1", 2024, [], thresholds=TH).state is PeerState.unavailable


def test_withheld_value_is_not_ranked() -> None:
    rows = [*peer_rows()[:3], obs("g4", "20", status="withheld")]
    rows[3] = rows[3].model_copy(update={"reason": "break"})
    out = compare_to_peers(
        metric(),
        hierarchy(),
        "g1",
        2024,
        rows,
        thresholds=IndicatorThresholds(min_peers=1, min_trend_steps=1),
    )
    assert out.coverage is not None
    assert out.coverage.excluded == 1


def test_rank_indicator_suppresses_without_a_decided_policy_or_with_thin_coverage() -> None:
    cohort = ["g1", "g2", "g3", "g4", "g5"]
    none = rank_indicator(
        metric(), hierarchy(), peer_rows(), year=2024, cohort=cohort, cohort_id="gmina", policy=None
    )
    assert none.suppressed
    assert none.ranking is None
    assert none.gate.verdict is GateVerdict.undecided
    undecided = PublicationPolicy(metric_key="test_metric", metric_version=1)
    assert rank_indicator(
        metric(), hierarchy(), peer_rows(), year=2024, cohort=cohort, cohort_id="gmina", policy=undecided
    ).suppressed
    strict = PublicationPolicy(
        metric_key="test_metric", metric_version=1, min_coverage=D("0.9"), min_cohort_size=2
    )
    thin = rank_indicator(
        metric(), hierarchy(), peer_rows(), year=2024, cohort=cohort, cohort_id="gmina", policy=strict
    )
    assert thin.suppressed
    assert thin.ranking is None
    assert thin.gate.verdict is GateVerdict.failed
    assert thin.coverage.ratio == D("0.8000")
    ok = PublicationPolicy(
        metric_key="test_metric", metric_version=1, min_coverage=D("0.8"), min_cohort_size=2
    )
    shown = rank_indicator(
        metric(), hierarchy(), peer_rows(), year=2024, cohort=cohort, cohort_id="gmina", policy=ok
    )
    assert not shown.suppressed
    assert shown.ranking is not None
    assert next(e.territory_id for e in shown.ranking.entries) == "g2"
