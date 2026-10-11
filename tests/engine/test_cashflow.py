"""N-06: deterministic cash flow, tax and returns (docs/ENGINE-SPEC.md), including invariants 3 and 4."""

import decimal
from decimal import Decimal as D

import pytest
from deal_analyzer import Assumptions, DealInputs, LegalClass, compute_cash_flows, irr, npv
from deal_analyzer.costs import notary_fee, purchase_costs
from deal_analyzer.tax import ryczalt_tax, sale_tax
from hypothesis import given, settings
from hypothesis import strategies as st

# A "clean room" assumption set: every optional cost, tax and growth is off, so results can be hand-checked.
CLEAN = Assumptions(
    fitout_months=0,
    court_fee_pln=D(0),
    deed_copies_pln=D(0),
    pcc_rate=D(0),
    property_tax_pln_per_m2=D(0),
    insurance_rate=D(0),
    maintenance_rate=D(0),
    vacancy_months_per_year=D(0),
    cost_inflation=D(0),
    rent_growth=D(0),
    ryczalt_low_rate=D(0),
    ryczalt_high_rate=D(0),
    sale_tax_rate=D(0),
    selling_cost_rate=D(0),
    appreciation_rate=D(0),
)


def deal(**kw: object) -> DealInputs:
    base: dict[str, object] = {
        "price_pln": D(100_000),
        "area_m2": D(50),
        "monthly_rent_pln": D(1_000),
        "assumptions": CLEAN,
    }
    return DealInputs(**{**base, **kw})  # pyright: ignore[reportArgumentType]


def oracle_irr(flows: list[D]) -> float:
    """An independent IRR in plain floats (tests only): bisection on NPV, no shared code with the engine."""
    values = [float(f) for f in flows]

    def f(r: float) -> float:
        return sum(cf / (1 + r) ** t for t, cf in enumerate(values))

    lo, hi = -0.99, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (f(lo) > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---- notary scale ----
@pytest.mark.parametrize(
    ("price", "fee_net"),
    [
        (3_000, "100"),
        (10_000, "310"),
        (30_000, "710"),
        (60_000, "1010"),
        (100_000, "1170"),
        (1_000_000, "4770"),
        (2_000_000, "6770"),
        (50_000_000, "10000"),  # capped
    ],
)
def test_notary_fee_follows_the_scale_and_adds_vat(price: int, fee_net: str) -> None:
    assert notary_fee(D(price), Assumptions()) == D(fee_net) * D("1.23")


# ---- tax ----
def test_ryczalt_uses_the_low_rate_up_to_the_threshold_and_the_high_rate_above() -> None:
    a = Assumptions()
    assert ryczalt_tax(D(50_000), a) == D(4_250)
    assert ryczalt_tax(D(150_000), a) == D(8_500) + D(6_250)
    assert ryczalt_tax(D(0), a) == 0
    assert ryczalt_tax(D(-5), a) == 0


def test_the_ryczalt_threshold_applies_per_owner() -> None:
    one = ryczalt_tax(D(150_000), Assumptions(owners=1))
    two = ryczalt_tax(D(150_000), Assumptions(owners=2))
    assert two == D(75_000) * D("0.085") * 2
    assert two < one


def test_sale_tax_only_inside_the_holding_window() -> None:
    a = Assumptions()
    assert sale_tax(D(300_000), D(250_000), 5, a) == D(9_500)
    assert sale_tax(D(300_000), D(250_000), 6, a) == 0
    assert sale_tax(D(200_000), D(250_000), 3, a) == 0  # a loss is not taxed


# ---- purchase costs ----
def test_vat_sales_have_no_pcc_and_net_prices_are_grossed_up() -> None:
    a = Assumptions()
    resid = purchase_costs(D(100_000), "gross", LegalClass.RESIDENTIAL, a)
    vat = purchase_costs(D(100_000), "net_plus_vat", LegalClass.VAT_SALE, a)
    commercial = purchase_costs(D(100_000), "net_plus_vat", LegalClass.NON_RESIDENTIAL, a)
    assert resid.output.pcc_pln == D("2000.00")
    assert vat.output.pcc_pln == 0
    assert vat.price == D(108_000)
    assert commercial.price == D(123_000)
    assert commercial.output.pcc_pln == 0


def test_total_acquisition_is_price_plus_every_cost() -> None:
    p = purchase_costs(D(450_000), "gross", LegalClass.RESIDENTIAL, Assumptions()).output
    assert p.total_acquisition_pln == p.price_pln + p.total_costs_pln
    assert p.total_costs_pln == p.pcc_pln + p.notary_pln + p.deed_copies_pln + p.court_fee_pln + p.broker_pln


# ---- cash flow by hand ----
def test_clean_room_cash_flow_matches_a_hand_calculation() -> None:
    result = compute_cash_flows(deal())
    notary = D("1439.10")  # 1170 plus 23% VAT
    invested = D(100_000) + notary
    assert result.total_invested_pln == invested
    assert [r.rent_collected_pln for r in result.years] == [D(12_000)] * 10
    assert all(r.net_cash_flow_pln == D(12_000) for r in result.years)
    assert result.exit.net_proceeds_pln == D(100_000)
    assert result.returns.gross_yield == D("0.1200")
    assert result.returns.net_yield == (D(12_000) / invested).quantize(D("0.0001"))
    assert result.returns.moic == ((D(120_000) + D(100_000)) / invested).quantize(D("0.0001"))
    flows = [-invested, *[D(12_000)] * 9, D(112_000)]
    assert result.returns.irr is not None
    assert (
        abs(float(result.returns.irr) - oracle_irr(flows)) <= 0.00005 + 1e-9
    )  # agrees with an independent solver
    assert npv(result.returns.irr - D("0.0001"), flows) > 0 > npv(result.returns.irr + D("0.0001"), flows)


def test_fitout_and_vacancy_reduce_the_collected_months() -> None:
    a = CLEAN.model_copy(update={"fitout_months": 2, "vacancy_months_per_year": D(1)})
    rows = compute_cash_flows(deal(assumptions=a)).years
    assert rows[0].rent_collected_pln == D(1_000) * 9  # 12 - 2 fit-out - 1 vacancy
    assert rows[1].rent_collected_pln == D(1_000) * 11


def test_rent_grows_and_costs_inflate_from_year_two() -> None:
    a = CLEAN.model_copy(
        update={"rent_growth": D("0.10"), "cost_inflation": D("0.05"), "maintenance_rate": D("0.01")}
    )
    rows = compute_cash_flows(deal(assumptions=a)).years
    assert rows[1].rent_collected_pln == D(13_200)
    assert rows[0].costs.maintenance_pln == D(1_000)
    assert rows[1].costs.maintenance_pln == D(1_050)


def test_exit_applies_appreciation_selling_costs_and_the_sale_tax_window() -> None:
    a = CLEAN.model_copy(
        update={
            "appreciation_rate": D("0.02"),
            "selling_cost_rate": D("0.02"),
            "sale_tax_rate": D("0.19"),
            "horizon_years": 3,
        }
    )
    result = compute_cash_flows(deal(assumptions=a))
    exit_value = D(100_000) * D("1.02") ** 3
    assert result.exit.exit_value_pln == exit_value.quantize(D("0.01"))
    assert result.exit.selling_costs_pln == (exit_value * D("0.02")).quantize(D("0.01"))
    gain = exit_value * D("0.98") - result.total_invested_pln
    assert result.exit.sale_tax_pln == (gain * D("0.19")).quantize(D("0.01"))
    ten_years = compute_cash_flows(deal(assumptions=a.model_copy(update={"horizon_years": 10})))
    assert ten_years.exit.sale_tax_pln == 0


def test_irr_is_none_when_it_cannot_exist_and_the_result_says_so() -> None:
    assert irr([D(-100), D(-5)]) is None
    assert irr([D(100), D(5)]) is None
    assert irr([]) is None
    assert irr([D(-100), D(110)]) == pytest.approx(D("0.10"), abs=D("1e-8"))
    a = CLEAN.model_copy(update={"appreciation_rate": D("-0.5"), "horizon_years": 1})
    result = compute_cash_flows(deal(monthly_rent_pln=D(0), assumptions=a))
    assert result.returns.irr is not None  # exit proceeds are positive, so a (very negative) IRR exists


def test_a_listing_with_no_rent_and_no_exit_value_flags_the_missing_irr() -> None:
    a = CLEAN.model_copy(update={"selling_cost_rate": D(1)})  # everything is eaten by selling costs
    result = compute_cash_flows(deal(monthly_rent_pln=D(0), assumptions=a))
    assert result.returns.irr is None
    assert "irr_not_computable" in result.warnings


# ---- invariant 3 ----
@pytest.mark.invariant
def test_invariant_admin_fee_is_opex() -> None:
    """characteristics.rent = 600 PLN is an owner COST (7,200 a year), and adds nothing to income."""
    with_fee = compute_cash_flows(deal(admin_fee_monthly_pln=D(600)))
    without = compute_cash_flows(deal(admin_fee_monthly_pln=None))
    assert with_fee.years[0].costs.admin_fee_pln == D(7_200)
    assert without.years[0].costs.admin_fee_pln == 0
    assert [r.rent_collected_pln for r in with_fee.years] == [
        r.rent_collected_pln for r in without.years
    ]  # no income
    assert with_fee.years[0].net_cash_flow_pln == without.years[0].net_cash_flow_pln - D(7_200)
    assert with_fee.returns.irr is not None
    assert without.returns.irr is not None
    assert with_fee.returns.irr < without.returns.irr
    assert with_fee.returns.gross_yield == without.returns.gross_yield  # yield is about rent, not the fee


@pytest.mark.invariant
def test_invariant_admin_fee_does_not_reduce_ryczalt_tax() -> None:
    a = Assumptions()  # real tax rates
    with_fee = compute_cash_flows(deal(admin_fee_monthly_pln=D(600), assumptions=a))
    without = compute_cash_flows(deal(admin_fee_monthly_pln=None, assumptions=a))
    assert (
        with_fee.years[0].income_tax_pln == without.years[0].income_tax_pln
    )  # ryczałt taxes revenue, not profit


# ---- invariant 4 ----
@pytest.mark.invariant
def test_invariant_deterministic_math() -> None:
    inp = deal(admin_fee_monthly_pln=D(600), assumptions=Assumptions(), capex_pln=D(30_000))
    first = compute_cash_flows(inp)
    second = compute_cash_flows(inp)
    assert first.returns.model_dump_json() == second.returns.model_dump_json()  # byte-identical returns block
    assert first.model_dump_json() == second.model_dump_json()

    # The global decimal context must not influence results: sabotage it and compute again.
    saved = decimal.getcontext().copy()
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        assert compute_cash_flows(inp).model_dump_json() == first.model_dump_json()
        assert decimal.getcontext().prec == 5  # and the engine did not touch it either
    finally:
        decimal.setcontext(saved)


def test_no_float_anywhere_in_the_result() -> None:
    def walk(value: object) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list | tuple):
            for v in value:
                walk(v)
        else:
            assert not isinstance(value, float)

    walk(compute_cash_flows(deal(assumptions=Assumptions())).model_dump())


def test_money_is_rounded_to_grosz_and_rates_to_four_decimals() -> None:
    result = compute_cash_flows(
        deal(price_pln=D("333333.33"), assumptions=Assumptions(), monthly_rent_pln=D("1777.77"))
    )
    for row in result.years:
        assert row.net_cash_flow_pln == row.net_cash_flow_pln.quantize(D("0.01"))
    assert result.returns.gross_yield == result.returns.gross_yield.quantize(D("0.0001"))


def test_the_result_is_versioned_and_has_one_row_per_year() -> None:
    result = compute_cash_flows(deal(assumptions=Assumptions(horizon_years=7)))
    assert [r.year for r in result.years] == list(range(1, 8))
    assert result.assumptions_version


# ---- properties ----
prices = st.integers(150_000, 1_500_000).map(D)
rents = st.integers(1_000, 8_000).map(D)


@settings(max_examples=60, deadline=None)
@given(price=prices, rent=rents, bump=st.integers(1_000, 100_000).map(D))
def test_a_higher_price_never_improves_the_irr(price: D, rent: D, bump: D) -> None:
    a = Assumptions()
    cheap = compute_cash_flows(deal(price_pln=price, monthly_rent_pln=rent, assumptions=a)).returns.irr
    dear = compute_cash_flows(deal(price_pln=price + bump, monthly_rent_pln=rent, assumptions=a)).returns.irr
    assert cheap is not None
    assert dear is not None
    assert dear <= cheap


@settings(max_examples=60, deadline=None)
@given(price=prices, rent=rents, bump=st.integers(50, 2_000).map(D))
def test_a_higher_rent_never_hurts_the_irr(price: D, rent: D, bump: D) -> None:
    a = Assumptions()
    low = compute_cash_flows(deal(price_pln=price, monthly_rent_pln=rent, assumptions=a)).returns.irr
    high = compute_cash_flows(deal(price_pln=price, monthly_rent_pln=rent + bump, assumptions=a)).returns.irr
    assert low is not None
    assert high is not None
    assert high >= low


@settings(max_examples=60, deadline=None)
@given(price=prices, rent=rents, capex=st.integers(0, 200_000).map(D), fee=st.integers(0, 1_500).map(D))
def test_the_reported_irr_zeroes_the_npv(price: D, rent: D, capex: D, fee: D) -> None:
    result = compute_cash_flows(
        deal(
            price_pln=price,
            monthly_rent_pln=rent,
            capex_pln=capex,
            admin_fee_monthly_pln=fee,
            assumptions=Assumptions(),
        )
    )
    if result.returns.irr is None:
        return
    flows = [-result.total_invested_pln, *[r.net_cash_flow_pln for r in result.years]]
    flows[-1] += result.exit.net_proceeds_pln
    assert abs(float(result.returns.irr) - oracle_irr(flows)) <= 0.00005 + 1e-9
