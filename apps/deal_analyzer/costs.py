"""Purchase costs and yearly operating costs (docs/ENGINE-SPEC.md rows 2 and 3). Exact `Decimal`."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from deal_analyzer.assumptions import NOTARY_FEE_CAP, NOTARY_SCALE, Assumptions
from deal_analyzer.legal_class import LegalClass
from deal_analyzer.money import ONE, TWELVE, ZERO, engine_math, pln


class PurchaseCosts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    price_pln: Decimal  # price including VAT where the sale is a VAT sale
    pcc_pln: Decimal
    notary_pln: Decimal  # fee plus VAT
    deed_copies_pln: Decimal
    court_fee_pln: Decimal
    broker_pln: Decimal
    total_costs_pln: Decimal  # everything except the price
    total_acquisition_pln: Decimal  # price plus costs


def effective_price(price: Decimal, basis: str, legal_class: LegalClass, a: Assumptions) -> Decimal:
    """The price actually paid: net + VAT prices are grossed up; stated or unknown prices are taken as
    gross."""
    if basis != "net_plus_vat":
        return price
    with engine_math():
        vat = a.non_residential_vat_rate if legal_class is LegalClass.NON_RESIDENTIAL else a.vat_sale_rate
        return price * (ONE + vat)


def notary_fee(price: Decimal, a: Assumptions) -> Decimal:
    """Maximum statutory notary fee for a sale at `price`, plus VAT, capped. NOTARY: confirm the scale."""
    with engine_math():
        fee = ZERO
        for upper, base, scale_rate, floor in NOTARY_SCALE:
            if upper is None or price <= upper:
                fee = base + scale_rate * (price - floor) if scale_rate else base
                break
        return min(fee, NOTARY_FEE_CAP) * (ONE + a.notary_vat_rate)


class ExactPurchase(BaseModel):
    """Unrounded figures the engine computes with; `output` is what leaves the engine."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    output: PurchaseCosts
    price: Decimal
    costs: Decimal
    total: Decimal


def purchase_costs(
    price_stated: Decimal, basis: str, legal_class: LegalClass, a: Assumptions
) -> ExactPurchase:
    with engine_math():
        price = effective_price(price_stated, basis, legal_class, a)
        pcc = price * a.pcc_rate if legal_class is LegalClass.RESIDENTIAL else ZERO  # VAT sales carry no PCC
        notary = notary_fee(price, a)
        broker = price * a.broker_rate * (ONE + a.broker_vat_rate)
        costs = pcc + notary + a.deed_copies_pln + a.court_fee_pln + broker
        total = price + costs
        out = PurchaseCosts(
            price_pln=pln(price),
            pcc_pln=pln(pcc),
            notary_pln=pln(notary),
            deed_copies_pln=pln(a.deed_copies_pln),
            court_fee_pln=pln(a.court_fee_pln),
            broker_pln=pln(broker),
            total_costs_pln=pln(costs),
            total_acquisition_pln=pln(total),
        )
        return ExactPurchase(output=out, price=price, costs=costs, total=total)


class YearlyCosts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    admin_fee_pln: Decimal  # czynsz: an owner cost (invariant 3)
    property_tax_pln: Decimal
    insurance_pln: Decimal
    maintenance_pln: Decimal
    management_pln: Decimal
    total_pln: Decimal


def yearly_costs(
    year: int,
    *,
    price: Decimal,
    area_m2: Decimal,
    admin_fee_monthly: Decimal | None,
    collected_rent: Decimal,
    a: Assumptions,
) -> tuple[YearlyCosts, Decimal]:
    """Operating costs for `year` (1-based). The admin fee is paid every month, tenant or not."""
    with engine_math():
        inflation = (ONE + a.cost_inflation) ** (year - 1)
        admin = (admin_fee_monthly or ZERO) * TWELVE * inflation
        tax = area_m2 * a.property_tax_pln_per_m2 * inflation
        insurance = price * a.insurance_rate * inflation
        maintenance = price * a.maintenance_rate * inflation
        management = collected_rent * a.management_rate
        total = admin + tax + insurance + maintenance + management
        out = YearlyCosts(
            admin_fee_pln=pln(admin),
            property_tax_pln=pln(tax),
            insurance_pln=pln(insurance),
            maintenance_pln=pln(maintenance),
            management_pln=pln(management),
            total_pln=pln(total),
        )
        return out, total
