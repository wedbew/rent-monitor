"""Income tax on private rental (ryczałt) and on a sale within the holding window (ENGINE-SPEC row 6).
ACCOUNTANT."""

from decimal import Decimal

from deal_analyzer.assumptions import Assumptions
from deal_analyzer.money import ZERO, engine_math


def ryczalt_tax(revenue: Decimal, a: Assumptions) -> Decimal:
    """8.5 % up to the threshold, 12.5 % above, per owner: joint owners each use their own threshold.

    Ryczałt taxes revenue; costs (including the admin fee) do not reduce it.
    """
    if revenue <= 0:
        return ZERO
    with engine_math():
        share = revenue / a.owners
        low = min(share, a.ryczalt_threshold_pln)
        high = max(share - a.ryczalt_threshold_pln, ZERO)
        return (low * a.ryczalt_low_rate + high * a.ryczalt_high_rate) * a.owners


def sale_tax(proceeds: Decimal, cost_basis: Decimal, years_held: int, a: Assumptions) -> Decimal:
    """19 % of the gain when the flat is sold within the holding window, otherwise none."""
    if years_held > a.sale_tax_years:
        return ZERO
    with engine_math():
        return max(proceeds - cost_basis, ZERO) * a.sale_tax_rate
