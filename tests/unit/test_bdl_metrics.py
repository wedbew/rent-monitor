"""LCTX-01 (RM-378): BDL territory, metric and observation contracts and pure comparison logic. No DB."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
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
    RankingResult,
    SelectionStatus,
    TerritoryLevel,
    TerritoryRef,
    ViewState,
)
from rm_core.location_contracts import (
    CohortError,
    ConflictingObservationError,
    CoverageBelowThresholdError,
    HierarchyError,
    LocationContractError,
    ObservationOutOfBoundsError,
    TerritoryHierarchy,
    compare_years,
    evaluate_gate,
    rank_territories,
    require_publishable,
    view_metric,
)

D = Decimal
DIGEST = "a" * 64
G, P, W, C = TerritoryLevel.gmina, TerritoryLevel.powiat, TerritoryLevel.wojewodztwo, TerritoryLevel.country


def ref(tid: str, teryt: str, level: TerritoryLevel, parent: str | None, **kw: bool) -> TerritoryRef:
    return TerritoryRef(territory_id=tid, teryt=teryt, name=f"n{tid}", level=level, parent_id=parent, **kw)


def tree() -> list[TerritoryRef]:
    out = [
        ref("PL", "", C, None),
        ref("W02", "02", W, "PL"),
        ref("P0201", "0201", P, "W02"),
        ref("P0202", "0202", P, "W02"),
    ]
    out += [ref(f"g{i}", f"020100{i}", G, "P0201") for i in range(1, 6)]
    return out


def metric(**kw: object) -> MetricDefinition:
    base: dict[str, object] = {
        "key": "dwellings_completed",
        "version": 1,
        "name_pl": "Mieszkania oddane",
        "unit": "szt.",
        "native_level": G,
        "published_levels": frozenset({G}),
        "change_basis": ChangeBasis.percent,
        "min_value": D(0),
        "selection": SelectionStatus.selected,
        "bdl_variable_id": "test-var",
    }
    base.update(kw)
    return MetricDefinition.model_validate(base)


def obs(  # noqa: PLR0917
    tid: str,
    value: str | None,
    year: int = 2025,
    status: str = "measured",
    key: str = "dwellings_completed",
    reason: str | None = None,
) -> Observation:
    return Observation(
        territory_id=tid,
        metric_key=key,
        metric_version=1,
        year=year,
        status=ObservationStatus(status),
        value=None if value is None else D(value),
        reason=reason,
        source_digest=DIGEST,
    )


GMINAS = [f"g{i}" for i in range(1, 6)]


# ---- hierarchy and territory contracts -------------------------------------------------------------


def test_hierarchy_ancestry_and_children() -> None:
    h = TerritoryHierarchy(tree())
    assert [a.territory_id for a in h.ancestors("g1")] == ["P0201", "W02", "PL"]
    assert [c.territory_id for c in h.children("P0201")] == GMINAS


def test_teryt_keeps_leading_zeros_and_length_is_enforced() -> None:
    assert ref("x", "0201001", G, "P0201").teryt == "0201001"
    with pytest.raises(ValidationError):
        ref("x", "201001", G, "P0201")  # leading zero lost


def test_only_country_has_no_parent_and_powiat_rights_is_a_gmina_role() -> None:
    with pytest.raises(ValidationError):
        ref("x", "0201", P, None)
    with pytest.raises(ValidationError):
        ref("x", "0201", P, "W02", has_powiat_rights=True)
    assert ref("g9", "0201019", G, "P0201", has_powiat_rights=True).has_powiat_rights


def test_hierarchy_rejects_skipped_level_unknown_parent_and_duplicates() -> None:
    with pytest.raises(HierarchyError):
        TerritoryHierarchy([ref("PL", "", C, None), ref("P1", "0201", P, "PL")])
    with pytest.raises(HierarchyError):
        TerritoryHierarchy([ref("W02", "02", W, "PL")])
    with pytest.raises(HierarchyError):
        TerritoryHierarchy([ref("PL", "", C, None), ref("PL", "", C, None)])
    with pytest.raises(HierarchyError):
        TerritoryHierarchy([ref("PL", "", C, None), ref("a", "02", W, "PL"), ref("b", "02", W, "PL")])


def test_same_name_territories_stay_distinct_by_id() -> None:
    a = TerritoryRef(territory_id="a", teryt="0201011", name="Dobra", level=G, parent_id="P0201")
    b = TerritoryRef(territory_id="b", teryt="0202011", name="Dobra", level=G, parent_id="P0202")
    h = TerritoryHierarchy([*tree(), a, b])
    assert h.get("a").parent_id != h.get("b").parent_id


def test_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TerritoryRef.model_validate(
            {
                "territory_id": "x",
                "teryt": "02",
                "name": "n",
                "level": "wojewodztwo",
                "parent_id": "PL",
                "z": 1,
            }
        )


# ---- metric and observation validation -------------------------------------------------------------


def test_metric_definition_consistency() -> None:
    with pytest.raises(ValidationError):
        metric(published_levels=frozenset({P}))  # native not published
    with pytest.raises(ValidationError):
        metric(min_value=D(5), max_value=D(1))
    with pytest.raises(ValidationError):
        metric(bdl_variable_id=None)  # selected needs reviewed signature
    assert (
        metric(selection=SelectionStatus.unavailable, bdl_variable_id=None).selection.value == "unavailable"
    )


def test_observation_gaps_are_distinct_from_zero() -> None:
    assert obs("g1", "0").value == D(0)  # genuine zero is a measured value
    with pytest.raises(ValidationError):
        obs("g1", None)  # measured needs a value
    with pytest.raises(ValidationError):
        obs("g1", "1", status="missing", reason="no row")  # a gap carries no value
    with pytest.raises(ValidationError):
        obs("g1", None, status="suppressed")  # a gap needs a reason
    with pytest.raises(ValidationError):
        obs("g1", "NaN")
    assert obs("g1", "7", status="withheld", reason="boundary").status is ObservationStatus.withheld


def test_digest_must_be_sha256_hex() -> None:
    with pytest.raises(ValidationError):
        Observation(
            territory_id="g1",
            metric_key="m_x",
            metric_version=1,
            year=2025,
            status=ObservationStatus.measured,
            value=D(1),
            source_digest="nope",
        )


# ---- ranking ---------------------------------------------------------------------------------------


def test_rank_territories_orders_and_gives_percentiles() -> None:
    h = TerritoryHierarchy(tree())
    rows = [obs(t, v) for t, v in zip(GMINAS, ["10", "50", "30", "40", "20"], strict=True)]
    r = rank_territories(metric(), h, rows, year=2025, expected=GMINAS, cohort_id="P0201")
    assert [(e.territory_id, e.rank) for e in r.entries] == [
        ("g2", 1),
        ("g4", 2),
        ("g3", 3),
        ("g5", 4),
        ("g1", 5),
    ]
    assert [e.percentile for e in r.entries] == [D("0.9"), D("0.7"), D("0.5"), D("0.3"), D("0.1")]
    assert (r.expected, r.eligible, r.missing, r.excluded) == (5, 5, 0, 0)


def test_ties_use_competition_rank_and_midrank_percentile() -> None:
    h = TerritoryHierarchy(tree())
    rows = [obs(t, v) for t, v in zip(GMINAS, ["9", "5", "5", "1", "0"], strict=True)]
    r = rank_territories(metric(), h, rows, year=2025, expected=GMINAS, cohort_id="c")
    assert [e.rank for e in r.entries] == [1, 2, 2, 4, 5]
    tied = [e for e in r.entries if e.value == D(5)]
    # behind=2, equal=2 (incl. self): (2 + 0.5 * 2) / 5 = 0.6 for both tied territories
    assert {e.percentile for e in tied} == {D("0.6")}


def test_lower_is_favorable_reverses_order() -> None:
    h = TerritoryHierarchy(tree())
    rows = [obs(t, v, key="unemployment") for t, v in zip(GMINAS, ["3", "1", "2", "5", "4"], strict=True)]
    m = metric(key="unemployment", direction=Direction.lower_is_favorable)
    r = rank_territories(m, h, rows, year=2025, expected=GMINAS, cohort_id="c")
    assert r.entries[0].territory_id == "g2"
    assert r.entries[0].rank == 1


def test_rank_excludes_withheld_and_counts_gaps() -> None:
    h = TerritoryHierarchy(tree())
    rows = [
        obs("g1", "10"),
        obs("g2", "20", status="withheld", reason="boundary break"),
        obs("g3", None, status="suppressed", reason="source suppressed"),
        obs("g4", "0"),  # genuine zero is ranked
    ]
    r = rank_territories(metric(), h, rows, year=2025, expected=GMINAS, cohort_id="c")
    assert [e.territory_id for e in r.entries] == ["g1", "g4"]
    assert (r.eligible, r.excluded, r.missing) == (2, 1, 2)  # g3 suppressed + g5 absent


def test_one_unit_cohort_has_no_percentile() -> None:
    h = TerritoryHierarchy(tree())
    r = rank_territories(metric(), h, [obs("g1", "4")], year=2025, expected=["g1"], cohort_id="c")
    assert r.entries[0].percentile is None
    assert r.entries[0].rank == 1


def test_other_years_are_ignored_but_conflicts_and_stray_rows_raise() -> None:
    h = TerritoryHierarchy(tree())
    r = rank_territories(
        metric(), h, [obs("g1", "1"), obs("g1", "99", year=2024)], year=2025, expected=GMINAS, cohort_id="c"
    )
    assert r.eligible == 1
    with pytest.raises(ConflictingObservationError):
        rank_territories(
            metric(), h, [obs("g1", "1"), obs("g1", "2")], year=2025, expected=GMINAS, cohort_id="c"
        )
    with pytest.raises(CohortError):
        rank_territories(metric(), h, [obs("g1", "1")], year=2025, expected=["g2"], cohort_id="c")
    # an exact duplicate (same digest and value) collapses
    r2 = rank_territories(
        metric(), h, [obs("g1", "1"), obs("g1", "1")], year=2025, expected=GMINAS, cohort_id="c"
    )
    assert r2.eligible == 1


def test_mixed_metric_versions_raise() -> None:
    h = TerritoryHierarchy(tree())
    with pytest.raises(ConflictingObservationError):
        rank_territories(metric(version=2), h, [obs("g1", "1")], year=2025, expected=GMINAS, cohort_id="c")


def test_metric_bounds_enforced() -> None:
    h = TerritoryHierarchy(tree())
    with pytest.raises(ObservationOutOfBoundsError):
        rank_territories(metric(), h, [obs("g1", "-1")], year=2025, expected=GMINAS, cohort_id="c")


def test_powiat_native_metric_cannot_rank_gminas_and_unavailable_metric_refuses() -> None:
    h = TerritoryHierarchy(tree())
    m = metric(key="median_price", native_level=P, published_levels=frozenset({P}))
    with pytest.raises(CohortError):
        rank_territories(m, h, [], year=2025, expected=GMINAS, cohort_id="c")
    r = rank_territories(
        m,
        h,
        [obs("P0201", "9000", key="median_price")],
        year=2025,
        expected=["P0201", "P0202"],
        cohort_id="W02",
    )
    assert r.level is P
    assert r.missing == 1
    with pytest.raises(CohortError):
        rank_territories(
            metric(selection=SelectionStatus.unavailable, bdl_variable_id=None),
            h,
            [],
            year=2025,
            expected=GMINAS,
            cohort_id="c",
        )
    with pytest.raises(CohortError):
        rank_territories(metric(), h, [], year=2025, expected=[], cohort_id="c")


# ---- publication gate ------------------------------------------------------------------------------


def _ranking(eligible: int) -> RankingResult:
    h = TerritoryHierarchy(tree())
    rows = [obs(t, str(i)) for i, t in enumerate(GMINAS[:eligible])]
    return rank_territories(metric(), h, rows, year=2025, expected=GMINAS, cohort_id="c")


def test_coverage_threshold_check_raises_below_threshold() -> None:
    pol = PublicationPolicy(
        metric_key="dwellings_completed", metric_version=1, min_coverage=D("0.5"), min_cohort_size=1
    )
    low = _ranking(2)  # 40 %
    assert evaluate_gate(pol, metric(), low).verdict is GateVerdict.failed
    with pytest.raises(CoverageBelowThresholdError):
        require_publishable(pol, metric(), low)
    ok = require_publishable(pol, metric(), _ranking(3))
    assert ok.verdict is GateVerdict.passed
    assert ok.coverage == D("0.6")


def test_undecided_policy_is_never_a_pass() -> None:
    pol = PublicationPolicy(metric_key="dwellings_completed", metric_version=1)
    res = evaluate_gate(pol, metric(), _ranking(5))
    assert res.verdict is GateVerdict.undecided
    with pytest.raises(CoverageBelowThresholdError):
        require_publishable(pol, metric(), _ranking(5))
    half = PublicationPolicy(metric_key="dwellings_completed", metric_version=1, min_coverage=D("0.5"))
    assert evaluate_gate(half, metric(), _ranking(1)).verdict is GateVerdict.failed


def test_gate_rejects_mismatched_policy_version() -> None:
    pol = PublicationPolicy(metric_key="dwellings_completed", metric_version=2)
    with pytest.raises(LocationContractError):
        evaluate_gate(pol, metric(), _ranking(1))


# ---- period comparison -----------------------------------------------------------------------------


def test_compare_years_calculates_change() -> None:
    rows = [obs("g1", "80", year=2025 - 1), obs("g1", "100", year=2026 - 1 + 1)]
    c = compare_years(metric(), "g1", 2024, 2026, rows)
    assert c.state is ComparisonState.comparable
    assert (c.absolute_change, c.percent_change) == (D("20"), D("25.00"))


def test_signed_metrics_get_no_percent_and_zero_base_gets_none() -> None:
    m = metric(key="net_migration", change_basis=ChangeBasis.absolute, min_value=None)
    rows = [obs("g1", "-10", year=2024, key="net_migration"), obs("g1", "5", year=2025, key="net_migration")]
    c = compare_years(m, "g1", 2024, 2025, rows)
    assert c.absolute_change == D("15")
    assert c.percent_change is None
    zero = compare_years(metric(), "g1", 2024, 2025, [obs("g1", "0", year=2024), obs("g1", "5")])
    assert zero.percent_change is None
    assert zero.absolute_change == D("5")


def test_compare_years_missing_withheld_and_boundary_break() -> None:
    m = metric()
    assert compare_years(m, "g1", 2024, 2025, [obs("g1", "1")]).state is ComparisonState.missing_endpoint
    gap = [obs("g1", None, year=2024, status="missing", reason="none"), obs("g1", "1")]
    assert compare_years(m, "g1", 2024, 2025, gap).state is ComparisonState.missing_endpoint
    held = [obs("g1", "1", year=2024, status="withheld", reason="review"), obs("g1", "2")]
    assert compare_years(m, "g1", 2024, 2025, held).state is ComparisonState.withheld
    ok = [obs("g1", "1", year=2024), obs("g1", "2")]
    brk = BoundaryBreak(territory_id="g1", effective_year=2025, reason="split")
    c = compare_years(m, "g1", 2024, 2025, ok, [brk])
    assert c.state is ComparisonState.withheld
    assert "split" in (c.reason or "")
    other = BoundaryBreak(territory_id="g2", effective_year=2025, reason="x")
    assert compare_years(m, "g1", 2024, 2025, ok, [other]).state is ComparisonState.comparable
    with pytest.raises(LocationContractError):
        compare_years(m, "g1", 2025, 2025, ok)


# ---- direct, proxy and unavailable views -----------------------------------------------------------


def test_powiat_metric_for_gmina_is_a_labelled_proxy() -> None:
    h = TerritoryHierarchy(tree())
    m = metric(key="median_price", native_level=P, published_levels=frozenset({P}))
    v = view_metric(m, h, "g1", 2025, [obs("P0201", "9000", key="median_price")])
    assert v.state is ViewState.proxy
    assert (v.measured_territory_id, v.measured_level) == ("P0201", P)
    own = view_metric(m, h, "P0201", 2025, [obs("P0201", "9000", key="median_price")])
    assert own.state is ViewState.direct


def test_children_are_never_aggregated_into_a_parent() -> None:
    h = TerritoryHierarchy(tree())
    rows = [obs(t, "10") for t in GMINAS]
    v = view_metric(metric(), h, "P0201", 2025, rows)  # gmina-only metric asked for the powiat
    assert v.state is ViewState.unavailable
    assert v.observation is None


def test_missing_or_suppressed_parent_value_is_unavailable_not_a_neighbour() -> None:
    h = TerritoryHierarchy(tree())
    m = metric(key="median_price", native_level=P, published_levels=frozenset({P}))
    assert view_metric(m, h, "g1", 2025, []).state is ViewState.unavailable
    sup = obs("P0201", None, key="median_price", status="suppressed", reason="source")
    v = view_metric(m, h, "g1", 2025, [sup])
    assert v.state is ViewState.unavailable
    assert v.reason == "suppressed"
    # a sibling powiat's value is never substituted
    assert (
        view_metric(m, h, "g1", 2025, [obs("P0202", "1", key="median_price")]).state is ViewState.unavailable
    )
