"""Deterministic 10-year cash flow, returns and tax for one deal (docs/ENGINE-SPEC.md).

Pure function of its inputs: no I/O, no clock, no randomness, no float, no global decimal state.
Same input gives a byte-identical result (invariant 4). The admin fee is an operating cost and never
income (invariant 3).
"""

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from deal_analyzer.assumptions import ASSUMPTIONS_VERSION, Assumptions
from deal_analyzer.costs import PurchaseCosts, YearlyCosts, purchase_costs, yearly_costs
from deal_analyzer.legal_class import LegalClass
from deal_analyzer.money import ONE, TWELVE, ZERO, engine_math, pln, rate
from deal_analyzer.tax import ryczalt_tax, sale_tax

IRR_LOW = Decimal("-0.99")
IRR_HIGH = Decimal(10)
IRR_PRECISION = Decimal("1e-10")


class DealInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    price_pln: Decimal = Field(gt=0)
    price_basis: str = "gross"  # gross | net_plus_vat | unknown
    legal_class: LegalClass = LegalClass.RESIDENTIAL
    area_m2: Decimal = Field(gt=0)
    admin_fee_monthly_pln: Decimal | None = Field(default=None, ge=0)  # OPEX (invariant 3)
    monthly_rent_pln: Decimal = Field(ge=0)  # market rent excluding any admin fee, supplied by the rent model
    capex_pln: Decimal = Field(default=Decimal(0), ge=0)
    assumptions: Assumptions = Assumptions()


class YearRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    year: int
    rent_collected_pln: Decimal
    costs: YearlyCosts
    income_tax_pln: Decimal
    net_cash_flow_pln: Decimal  # before the sale proceeds


class ExitBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    exit_value_pln: Decimal
    selling_costs_pln: Decimal
    sale_tax_pln: Decimal
    net_proceeds_pln: Decimal


class Returns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    gross_yield: Decimal  # first full year of rent / price
    net_yield: Decimal  # stabilised year: rent less operating costs, over total invested
    irr: Decimal | None  # unlevered, after tax; None when it cannot be computed
    moic: Decimal  # total net cash back over total invested
    cagr: Decimal | None  # MOIC annualised over the horizon


class CashFlowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    assumptions_version: str = ASSUMPTIONS_VERSION
    purchase: PurchaseCosts
    capex_pln: Decimal
    total_invested_pln: Decimal
    years: tuple[YearRow, ...]
    exit: ExitBreakdown
    returns: Returns
    warnings: tuple[str, ...] = ()


def npv(rate_: Decimal, flows: Sequence[Decimal]) -> Decimal:
    with engine_math():
        base = ONE + rate_
        return sum((cf / base**t for t, cf in enumerate(flows)), ZERO)


def irr(flows: Sequence[Decimal]) -> Decimal | None:
    """Rate where NPV = 0, by bisection (deterministic). None if the sign never changes or no root is
    in range."""
    if not (any(cf < 0 for cf in flows) and any(cf > 0 for cf in flows)):
        return None
    with engine_math():
        lo, hi = IRR_LOW, IRR_HIGH
        f_lo, f_hi = npv(lo, flows), npv(hi, flows)
        if f_lo == 0:
            return lo
        if f_hi == 0:
            return hi
        if (f_lo > 0) == (f_hi > 0):
            return None
        while hi - lo > IRR_PRECISION:
            mid = (lo + hi) / 2
            f_mid = npv(mid, flows)
            if f_mid == 0:
                return mid
            if (f_mid > 0) == (f_lo > 0):
                lo, f_lo = mid, f_mid
            else:
                hi = mid
        return (lo + hi) / 2


def _collected_months(year: int, a: Assumptions) -> Decimal:
    available = Decimal(12 - a.fitout_months) if year == 1 else TWELVE
    return max(available - a.vacancy_months_per_year, ZERO)


def compute_cash_flows(inp: DealInputs) -> CashFlowResult:
    a = inp.assumptions
    warnings: list[str] = []
    with engine_math() as ctx:
        bought = purchase_costs(inp.price_pln, inp.price_basis, inp.legal_class, a)
        costs_out, price = bought.output, bought.price
        invested = bought.total + inp.capex_pln
        flows: list[Decimal] = [-pln(invested)]
        rows: list[YearRow] = []
        stabilised_noi = ZERO
        for year in range(1, a.horizon_years + 1):
            rent = inp.monthly_rent_pln * (ONE + a.rent_growth) ** (year - 1) * _collected_months(year, a)
            year_costs, cost_total = yearly_costs(
                year,
                price=price,
                area_m2=inp.area_m2,
                admin_fee_monthly=inp.admin_fee_monthly_pln,
                collected_rent=rent,
                a=a,
            )
            tax = ryczalt_tax(rent, a)
            net = pln(rent) - pln(cost_total) - pln(tax)
            rows.append(
                YearRow(
                    year=year,
                    rent_collected_pln=pln(rent),
                    costs=year_costs,
                    income_tax_pln=pln(tax),
                    net_cash_flow_pln=net,
                )
            )
            flows.append(net)
            if year == min(2, a.horizon_years):
                stabilised_noi = rent - cost_total

        exit_value = price * (ONE + a.appreciation_rate) ** a.horizon_years
        selling = exit_value * a.selling_cost_rate
        basis = invested  # price + purchase costs + CAPEX
        tax_on_sale = sale_tax(exit_value - selling, basis, a.horizon_years, a)
        proceeds = exit_value - selling - tax_on_sale
        exit_out = ExitBreakdown(
            exit_value_pln=pln(exit_value),
            selling_costs_pln=pln(selling),
            sale_tax_pln=pln(tax_on_sale),
            net_proceeds_pln=pln(proceeds),
        )
        flows[-1] = flows[-1] + exit_out.net_proceeds_pln

        total_back = sum(flows[1:], ZERO)
        invested_out = pln(invested)
        moic = total_back / invested_out
        solved = irr(flows)
        if solved is None:
            warnings.append("irr_not_computable")
        cagr: Decimal | None = None
        if moic > 0:
            cagr = ctx.power(moic, ONE / a.horizon_years) - ONE
        returns = Returns(
            gross_yield=rate(inp.monthly_rent_pln * TWELVE / price),
            net_yield=rate(stabilised_noi / invested_out),
            irr=rate(solved) if solved is not None else None,
            moic=rate(moic),
            cagr=rate(cagr) if cagr is not None else None,
        )
        return CashFlowResult(
            purchase=costs_out,
            capex_pln=pln(inp.capex_pln),
            total_invested_pln=invested_out,
            years=tuple(rows),
            exit=exit_out,
            returns=returns,
            warnings=tuple(warnings),
        )
