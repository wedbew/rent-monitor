"""LCTX-02a (RM-396): per-metric BDL indicators (intensity, trend, comparison, rank, suppression). No DB.

LEGAL[third-party-data]: exercises derivations of GUS BDL statistics with hand-built values (RM-396).

Metric keys are TEST-ONLY; no metric is selected or activated (B-023) and the policies are test inputs.
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
    TerritoryLevel,
    TerritoryRef,
    ViewState,
)
from rm_core.location_contracts import CohortError, LocationContractError, TerritoryHierarchy
from rm_core.location_indicators import (
    IntensityState,
    TrendState,
    compare_to_context,
    intensity,
    rank_indicator,
    trend,
)

D = Decimal
DIGEST = "b" * 64
G, P, W, C = TerritoryLevel.gmina, TerritoryLevel.powiat, TerritoryLevel.wojewodztwo, TerritoryLevel.country


def hierarchy() -> TerritoryHierarchy:
    refs = [
        TerritoryRef(territory_id="PL", teryt="", name="PL", level=C),
        TerritoryRef(territory_id="W02", teryt="02", name="W", level=W, parent_id="PL"),
        TerritoryRef(territory_id="P1", teryt="0201", name="P1", level=P, parent_id="W02"),
        TerritoryRef(territory_id="P2", teryt="0202", name="P2", level=P, parent_id="W02"),
        TerritoryRef(territory_id="P3", teryt="0203", name="P3", level=P, parent_id="W02"),
    ]
    refs += [
        TerritoryRef(
            territory_id=f"G{i}",
            teryt=f"020{1 + i // 3}01{i % 3}",
            name=f"G{i}",
            level=G,
            parent_id=f"P{1 + i // 3}",
        )
        for i in range(1, 9)
    ]
    return TerritoryHierarchy(refs)


def defn(
    key: str = "test_metric",
    *,
    native: TerritoryLevel = G,
    published: frozenset[TerritoryLevel] | None = None,
    direction: Direction = Direction.higher_is_favorable,
    basis: ChangeBasis = ChangeBasis.percent,
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        version=1,
        name_pl="test",
        unit="u",
        native_level=native,
        published_levels=published or frozenset({native}),
        direction=direction,
        change_basis=basis,
    )


def obs(
    tid: str,
    year: int,
    value: str | None,
    status: ObservationStatus = ObservationStatus.measured,
    key: str = "test_metric",
) -> Observation:
    return Observation(
        territory_id=tid,
        metric_key=key,
        metric_version=1,
        year=year,
        status=status,
        value=None if value is None else D(value),
        reason=None if status is ObservationStatus.measured else "test",
        source_digest=DIGEST,
    )


def policy(cov: str | None, size: int | None, key: str = "test_metric") -> PublicationPolicy:
    return PublicationPolicy(
        metric_key=key, metric_version=1, min_coverage=None if cov is None else D(cov), min_cohort_size=size
    )


# --- intensity -----------------------------------------------------------------------------------------


def test_intensity_is_exact_and_rounded_half_even() -> None:
    r = intensity(obs("G1", 2023, "5", key="flats"), obs("G1", 2023, "1200", key="people"))
    assert (r.state, r.value) == (IntensityState.computed, D("4.1667"))
    r2 = intensity(obs("G1", 2023, "1", key="num_a"), obs("G1", 2023, "8", key="den_b"), per=D(1))
    assert r2.value == D("0.1250")


def test_intensity_gaps_never_become_zero() -> None:
    num = obs("G1", 2023, "5", key="num_a")
    gap = obs("G1", 2023, None, ObservationStatus.suppressed, key="den_b")
    assert intensity(num, gap).state is IntensityState.missing_input
    assert intensity(num, obs("G1", 2023, "0", key="den_b")).state is IntensityState.zero_denominator
    held = obs("G1", 2023, "7", ObservationStatus.withheld, key="den_b")
    assert intensity(num, held).state is IntensityState.withheld
    assert intensity(num, obs("G1", 2023, "0", key="den_b")).value is None


def test_intensity_refuses_mismatched_inputs() -> None:
    num, den = obs("G1", 2023, "5", key="num_a"), obs("G1", 2023, "5", key="den_b")
    with pytest.raises(LocationContractError):
        intensity(num, obs("G2", 2023, "5", key="den_b"))
    with pytest.raises(LocationContractError):
        intensity(obs("G1", 2022, "5", key="num_a"), den)
    with pytest.raises(LocationContractError):
        intensity(num, den, per=D(0))


# --- trend ---------------------------------------------------------------------------------------------


def test_trend_has_year_over_year_steps_and_a_span() -> None:
    rows = [obs("G1", 2021, "100"), obs("G1", 2022, "110"), obs("G1", 2023, "121")]
    t = trend(defn(), "G1", [2023, 2021, 2022, 2022], rows)
    assert t.state is TrendState.complete
    assert [s.percent_change for s in t.steps] == [D("10.00"), D("10.00")]
    assert (t.span.year_a, t.span.year_b, t.span.absolute_change, t.span.percent_change) == (
        2021,
        2023,
        D(21),
        D("21.00"),
    )


def test_trend_reports_gaps_and_breaks_instead_of_bridging() -> None:
    rows = [obs("G1", 2021, "100"), obs("G1", 2023, "130")]
    t = trend(defn(), "G1", [2021, 2022, 2023], rows)
    assert t.state is TrendState.none
    assert {s.state for s in t.steps} == {ComparisonState.missing_endpoint}
    assert t.span.state is ComparisonState.comparable  # matched endpoints exist
    brk = BoundaryBreak(territory_id="G1", effective_year=2023, reason="merge")
    t2 = trend(defn(), "G1", [2021, 2022, 2023], [*rows, obs("G1", 2022, "110")], [brk])
    assert t2.state is TrendState.partial
    assert t2.span.state is ComparisonState.withheld


def test_trend_signed_metric_has_no_percent_and_needs_two_years() -> None:
    d = defn(basis=ChangeBasis.absolute)
    t = trend(d, "G1", [2022, 2023], [obs("G1", 2022, "-5"), obs("G1", 2023, "3")])
    assert t.span.absolute_change == D(8)
    assert t.span.percent_change is None
    with pytest.raises(LocationContractError):
        trend(d, "G1", [2022, 2022], [])


# --- comparison against the parent unit and peers -------------------------------------------------------


def test_direct_value_compares_to_parent_and_peer_median() -> None:
    d = defn(published=frozenset({G, W}))
    rows = [
        obs("G1", 2023, "10"),
        obs("G2", 2023, "20"),
        obs("G3", 2023, "30"),
        obs("G4", 2023, "40"),
        obs("W02", 2023, "25"),
    ]
    # Fixture layout: G1 and G2 sit under P1; G3..G5 under P2. Peers are siblings under the same parent.
    c = compare_to_context(d, hierarchy(), "G1", 2023, rows)
    assert c.own.state is ViewState.direct
    assert c.parent is None  # the parent powiat is not published for this metric; no grandparent stand-in
    assert c.delta_vs_parent is None
    assert c.peer_cohort_id == "gmina:P1"
    assert (c.peer_count, c.peer_median, c.delta_vs_peer_median) == (1, D("20.0000"), D(-10))


def test_parent_value_is_its_own_never_built_from_children() -> None:
    d = defn(published=frozenset({G, P}))
    rows = [obs("G1", 2023, "10"), obs("G2", 2023, "30"), obs("P1", 2023, "99")]
    c = compare_to_context(d, hierarchy(), "G1", 2023, rows)
    assert c.parent is not None
    assert c.parent.measured_territory_id == "P1"
    assert c.delta_vs_parent == D(10) - D(99)  # P1's own number, not the 20 that averaging children gives
    no_parent = compare_to_context(d, hierarchy(), "G1", 2023, rows[:2])
    assert no_parent.parent is None  # an unmeasured parent is not replaced by anything
    assert no_parent.delta_vs_parent is None


def test_powiat_native_metric_is_labelled_proxy_for_a_gmina() -> None:
    d = defn(native=P)
    rows = [obs("P1", 2023, "50"), obs("P2", 2023, "70"), obs("P3", 2023, "90")]
    c = compare_to_context(d, hierarchy(), "G1", 2023, rows)
    assert c.own.state is ViewState.proxy
    assert (c.own.measured_territory_id, c.own.measured_level) == ("P1", P)
    assert c.peer_cohort_id == "powiat:W02"
    assert c.peer_count == 2
    assert c.peer_median == D("80.0000")
    assert c.delta_vs_peer_median == D(50) - D(80)


def test_withheld_and_missing_peers_are_excluded_from_the_median() -> None:
    d = defn(native=P)
    rows = [
        obs("P1", 2023, "50"),
        obs("P2", 2023, "70", ObservationStatus.withheld),
        obs("P3", 2023, None, ObservationStatus.missing),
    ]
    c = compare_to_context(d, hierarchy(), "P1", 2023, rows)
    assert c.own.state is ViewState.direct
    assert (c.peer_count, c.peer_median, c.delta_vs_peer_median) == (0, None, None)


def test_a_withheld_own_value_has_no_delta() -> None:
    d = defn(native=P)
    rows = [obs("P1", 2023, "50", ObservationStatus.withheld), obs("P2", 2023, "70")]
    c = compare_to_context(d, hierarchy(), "P1", 2023, rows)
    assert c.delta_vs_peer_median is None
    assert c.peer_median == D("70.0000")


# --- rank, cohort and coverage, suppression ------------------------------------------------------------


COHORT = ["P1", "P2", "P3"]


def rows3() -> list[Observation]:
    return [obs("P1", 2023, "5"), obs("P2", 2023, "9"), obs("P3", 2023, "9")]


def test_rank_is_reproducible_with_cohort_and_coverage_metadata() -> None:
    d = defn(native=P)
    a = rank_indicator(d, policy("0.6", 2), hierarchy(), rows3(), year=2023, expected=COHORT, cohort_id="W02")
    b = rank_indicator(
        d, policy("0.6", 2), hierarchy(), list(reversed(rows3())), year=2023, expected=COHORT, cohort_id="W02"
    )
    assert a == b  # input order does not matter
    assert not a.suppressed
    assert a.gate.verdict is GateVerdict.passed
    assert [(e.territory_id, e.rank) for e in a.ranking.entries] == [("P2", 1), ("P3", 1), ("P1", 3)]
    assert (a.ranking.cohort_id, a.ranking.expected, a.ranking.eligible, a.gate.coverage) == (
        "W02",
        3,
        3,
        D("1.0000"),
    )


def test_thin_coverage_suppresses_ranks_but_keeps_the_counts() -> None:
    d = defn(native=P)
    rows = [obs("P1", 2023, "5"), obs("P2", 2023, None, ObservationStatus.suppressed)]
    r = rank_indicator(d, policy("0.9", 1), hierarchy(), rows, year=2023, expected=COHORT, cohort_id="W02")
    assert r.suppressed
    assert r.gate.verdict is GateVerdict.failed
    assert r.ranking.entries == ()
    assert (r.ranking.eligible, r.ranking.expected, r.ranking.missing) == (1, 3, 2)


def test_small_cohort_is_suppressed() -> None:
    r = rank_indicator(
        defn(native=P), policy("0.1", 4), hierarchy(), rows3(), year=2023, expected=COHORT, cohort_id="W02"
    )
    assert r.suppressed
    assert r.ranking.entries == ()


@pytest.mark.parametrize("pol", [None, policy(None, None), policy("0.5", None), policy(None, 1)])
def test_undecided_policy_suppresses_instead_of_passing(pol: PublicationPolicy | None) -> None:
    r = rank_indicator(defn(native=P), pol, hierarchy(), rows3(), year=2023, expected=COHORT, cohort_id="W02")
    assert r.suppressed
    assert r.gate.verdict is GateVerdict.undecided
    assert r.ranking.entries == ()


def test_withheld_values_are_excluded_not_ranked() -> None:
    rows = [obs("P1", 2023, "5"), obs("P2", 2023, "9", ObservationStatus.withheld), obs("P3", 2023, "7")]
    r = rank_indicator(
        defn(native=P), policy("0.5", 2), hierarchy(), rows, year=2023, expected=COHORT, cohort_id="W02"
    )
    assert (r.ranking.excluded, r.ranking.eligible) == (1, 2)
    assert [e.territory_id for e in r.ranking.entries] == ["P3", "P1"]


def test_cohort_must_sit_at_the_native_level() -> None:
    with pytest.raises(CohortError):
        rank_indicator(
            defn(native=P), policy("0.5", 1), hierarchy(), [], year=2023, expected=["G1"], cohort_id="x"
        )
