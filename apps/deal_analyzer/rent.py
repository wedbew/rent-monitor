"""Rent estimate from comparable asking rents (docs/ENGINE-SPEC.md row 5).

Method: PLN per m2 of comparables of similar size, outliers trimmed, median scaled to the flat's area,
with a quartile
interval. Comparables are ASKING rents, so the result is labelled asking-based (the 3 % haircut is applied in
`deal_analyzer.analysis`). Thin markets: fewer than 3 comparables refuses a number (grade N
downstream), fewer than 10 lowers
confidence. Pure and deterministic; the caller supplies the comparables (market lane, RM-48/49/N-13),
nothing is fetched here.
A full hedonic regression (floor, standard, distances) is a later refinement: this version adjusts only
for size.
"""

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from deal_analyzer.analysis import MIN_COMPARABLES, THIN_MARKET, RentInput
from deal_analyzer.money import ZERO, engine_math, pln
from deal_analyzer.ownership import Confidence

AREA_WINDOW = Decimal("0.30")  # comparables within +/-30 % of the flat's area are preferred
PPM2_RANGE = (Decimal(5), Decimal(500))  # plausible PLN per m2 per month; anything else is a data error
IQR_FENCE = Decimal("1.5")
TRIM_MIN_SAMPLE = 8  # outlier trimming needs enough points to mean something


class RentComparable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    monthly_rent_pln: Decimal = Field(gt=0)
    area_m2: Decimal = Field(gt=0)


class RentEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    refused: bool
    monthly_rent_pln: Decimal | None  # None when refused
    low_monthly_pln: Decimal | None
    high_monthly_pln: Decimal | None
    ppm2_median: Decimal | None
    comparables_considered: int
    comparables_used: int
    basis: str = "asking"
    confidence: Confidence
    warnings: tuple[str, ...] = ()

    def to_input(self) -> RentInput:
        """The `RentInput` for `analyse_listing`; a refused estimate becomes rent 0 with its (too
        small) comparable count."""
        return RentInput(
            monthly_rent_pln=self.monthly_rent_pln or ZERO, basis="asking", comparables=self.comparables_used
        )


def _quantile(sorted_values: Sequence[Decimal], q: Decimal) -> Decimal:
    """Linear-interpolated quantile of an ascending list (deterministic, Decimal only)."""
    with engine_math():
        pos = (len(sorted_values) - 1) * q
        lower = int(pos)
        frac = pos - lower
        if lower + 1 >= len(sorted_values):
            return sorted_values[-1]
        return sorted_values[lower] + (sorted_values[lower + 1] - sorted_values[lower]) * frac


def _trim(values: list[Decimal]) -> list[Decimal]:
    if len(values) < TRIM_MIN_SAMPLE:
        return values
    with engine_math():
        q1, q3 = _quantile(values, Decimal("0.25")), _quantile(values, Decimal("0.75"))
        spread = (q3 - q1) * IQR_FENCE
        kept = [v for v in values if q1 - spread <= v <= q3 + spread]
    return kept or values


def estimate_rent(area_m2: Decimal, comparables: Sequence[RentComparable]) -> RentEstimate:
    warnings: list[str] = []
    with engine_math():
        usable = [(c, c.monthly_rent_pln / c.area_m2) for c in comparables]
        usable = [(c, p) for c, p in usable if PPM2_RANGE[0] <= p <= PPM2_RANGE[1]]
        if len(usable) < len(comparables):
            warnings.append("comparables_dropped_implausible")
        near = [(c, p) for c, p in usable if abs(c.area_m2 - area_m2) <= area_m2 * AREA_WINDOW]
        pool = near if len(near) >= MIN_COMPARABLES else usable
        if pool is not near:
            warnings.append("size_window_widened")
        considered = len(pool)
        values = _trim(sorted(p for _, p in pool))
        used = len(values)
        if used < MIN_COMPARABLES:
            return RentEstimate(
                refused=True,
                monthly_rent_pln=None,
                low_monthly_pln=None,
                high_monthly_pln=None,
                ppm2_median=None,
                comparables_considered=considered,
                comparables_used=used,
                confidence=Confidence.LOW,
                warnings=(*warnings, "rent_refused_too_few_comparables"),
            )
        median = _quantile(values, Decimal("0.5"))
        low, high = _quantile(values, Decimal("0.25")), _quantile(values, Decimal("0.75"))
        confidence = Confidence.MEDIUM if used < THIN_MARKET else Confidence.HIGH
        if used < THIN_MARKET:
            warnings.append("rent_thin_market")
        return RentEstimate(
            refused=False,
            monthly_rent_pln=pln(median * area_m2),
            low_monthly_pln=pln(low * area_m2),
            high_monthly_pln=pln(high * area_m2),
            ppm2_median=pln(median),
            comparables_considered=considered,
            comparables_used=used,
            confidence=confidence,
            warnings=tuple(warnings),
        )
