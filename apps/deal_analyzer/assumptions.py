"""Versioned assumptions. Every number below is a *default from docs/ENGINE-SPEC.md*, changeable per audit.

Values marked ACCOUNTANT/NOTARY are facts to be confirmed before launch (PRE-DEPLOYMENT section 4);
they are constants here on purpose, so confirming or correcting one is a one-line change with a test,
not a code change.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

ASSUMPTIONS_VERSION = "2026-10-12.2"

# Maximum notary fee for a sale deed (taksa notarialna): (upper bound, base fee, rate, bound the rate
# starts from).
# ACCOUNTANT/NOTARY: confirm against the current regulation. Fee excludes 23% VAT, which is added separately.
NOTARY_SCALE: tuple[tuple[Decimal | None, Decimal, Decimal, Decimal], ...] = (
    (Decimal(3_000), Decimal(100), Decimal(0), Decimal(0)),
    (Decimal(10_000), Decimal(100), Decimal("0.03"), Decimal(3_000)),
    (Decimal(30_000), Decimal(310), Decimal("0.02"), Decimal(10_000)),
    (Decimal(60_000), Decimal(710), Decimal("0.01"), Decimal(30_000)),
    (Decimal(1_000_000), Decimal(1_010), Decimal("0.004"), Decimal(60_000)),
    (None, Decimal(4_770), Decimal("0.002"), Decimal(1_000_000)),
)
NOTARY_FEE_CAP = Decimal(10_000)


class Assumptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: str = ASSUMPTIONS_VERSION
    horizon_years: int = Field(default=10, ge=1, le=30)
    fitout_months: int = Field(default=2, ge=0, le=12)  # no rent while CAPEX is carried out
    # Purchase costs (row 2)
    pcc_rate: Decimal = Decimal("0.02")  # secondary-market residential only. ACCOUNTANT
    notary_vat_rate: Decimal = Decimal("0.23")
    deed_copies_pln: Decimal = Decimal(150)  # wypisy; placeholder. NOTARY
    court_fee_pln: Decimal = Decimal(200)  # land-register entry. ACCOUNTANT
    broker_rate: Decimal = Decimal(0)  # buyers usually pay none; users may enter e.g. 0.025
    broker_vat_rate: Decimal = Decimal("0.23")
    vat_sale_rate: Decimal = Decimal("0.08")  # residential unit sold with VAT. ACCOUNTANT
    non_residential_vat_rate: Decimal = Decimal("0.23")
    # Operating costs (row 3)
    property_tax_pln_per_m2: Decimal = Decimal(
        "1.19"
    )  # statutory maximum for the year, to be versioned. ACCOUNTANT
    insurance_rate: Decimal = Decimal("0.0015")  # of price per year
    vacancy_months_per_year: Decimal = Field(default=Decimal(1), ge=0, le=12)
    management_rate: Decimal = Decimal(0)  # of collected rent; 0.08 if outsourced
    maintenance_rate: Decimal = Decimal("0.005")  # of price per year
    cost_inflation: Decimal = Decimal("0.03")  # applied to costs from year 2
    rent_growth: Decimal = Decimal("0.03")
    rent_haircut: Decimal = Decimal(
        "0.03"
    )  # comparables are asking rents; achieved rents come in lower (row 5)
    # Tax (row 6): ryczałt on private rental. ACCOUNTANT
    ryczalt_low_rate: Decimal = Decimal("0.085")
    ryczalt_high_rate: Decimal = Decimal("0.125")
    ryczalt_threshold_pln: Decimal = Decimal(100_000)  # per owner and year
    owners: int = Field(default=1, ge=1, le=10)
    sale_tax_rate: Decimal = Decimal(
        "0.19"
    )  # on gain if sold within `sale_tax_years` of the end of the purchase year
    sale_tax_years: int = Field(default=5, ge=0, le=20)
    # Exit (row 8)
    appreciation_rate: Decimal = Field(default=Decimal("0.02"), ge=Decimal("-0.5"), le=Decimal("0.5"))
    selling_cost_rate: Decimal = Decimal("0.02")
