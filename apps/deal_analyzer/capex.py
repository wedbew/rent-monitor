"""CAPEX estimate: condition-based catalog with a regional multiplier (docs/ENGINE-SPEC.md row 4).

PLACEHOLDER PRICES: the PLN/m2 figures below are NOT market data. They only make the structure work and
are flagged
in docs/LIMITATIONS.md (L-007) and docs/BLOCKERS.md (B-015); they must be replaced with sourced prices
before launch.
The result carries `prices_are_placeholders=True` so no consumer can present the number as real.
The condition comes from the vision assessment; an unknown condition is treated as `refresh` with LOW
confidence.
LLM adjustments are applied afterwards by the caller, clamped to +/-15 % (`deal_analyzer.vision`).
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from deal_analyzer.money import engine_math, pln
from deal_analyzer.ownership import Confidence
from deal_analyzer.text import fold
from deal_analyzer.vision import Condition

CATALOG_VERSION = "placeholder-2026-10-12"
CATALOG_PLN_PER_M2: dict[Condition, Decimal] = {  # PLACEHOLDER, see module docstring
    Condition.GOOD: Decimal(0),
    Condition.REFRESH: Decimal(600),
    Condition.RENOVATION: Decimal(2_200),
    Condition.SHELL: Decimal(4_000),
}
Tier = Literal["metro", "major", "other"]
TIER_MULTIPLIER: dict[
    Tier, Decimal
] = {  # PLACEHOLDER: big cities cost more (the POC audit found one national constant misprices them)
    "metro": Decimal("1.25"),
    "major": Decimal("1.10"),
    "other": Decimal("1.00"),
}
_METRO = frozenset({"warszawa"})
_MAJOR = frozenset(
    {
        "krakow",
        "wroclaw",
        "gdansk",
        "gdynia",
        "sopot",
        "poznan",
        "lodz",
        "katowice",
        "szczecin",
        "lublin",
        "bialystok",
    }
)
RANGE_LOW = Decimal("0.75")  # the estimate is a range: -25 % / +25 %
RANGE_HIGH = Decimal("1.25")


class CapexEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    condition_used: Condition
    condition_assumed: bool  # True when the condition was unknown and `refresh` was assumed
    tier: Tier
    multiplier: Decimal
    pln_per_m2: Decimal
    base_pln: Decimal
    low_pln: Decimal
    high_pln: Decimal
    confidence: Confidence
    catalog_version: str
    prices_are_placeholders: bool = True


def city_tier(city: str | None) -> Tier:
    key = fold(city or "")
    if key in _METRO:
        return "metro"
    return "major" if key in _MAJOR else "other"


def estimate_capex(*, area_m2: Decimal, condition: Condition, city: str | None) -> CapexEstimate:
    assumed = condition is Condition.UNKNOWN
    used = Condition.REFRESH if assumed else condition
    tier = city_tier(city)
    with engine_math():
        per_m2 = CATALOG_PLN_PER_M2[used] * TIER_MULTIPLIER[tier]
        base = per_m2 * area_m2
        return CapexEstimate(
            condition_used=used,
            condition_assumed=assumed,
            tier=tier,
            multiplier=TIER_MULTIPLIER[tier],
            pln_per_m2=pln(per_m2),
            base_pln=pln(base),
            low_pln=pln(base * RANGE_LOW),
            high_pln=pln(base * RANGE_HIGH),
            confidence=Confidence.LOW if assumed or city is None else Confidence.MEDIUM,
            catalog_version=CATALOG_VERSION,
        )
