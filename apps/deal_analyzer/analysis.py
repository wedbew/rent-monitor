"""The canonical `DealAnalysis` and the pure function that assembles it from an extracted listing
(invariants 4-6).

JSON is canonical; the Markdown view is derived from it (`deal_analyzer.markdown`). Nothing here reads
a clock, a database
or the network: the caller supplies the rent estimate, the risk-free rate and the optional vision answer.
Fractional ownership never reaches the math: `FractionalOwnershipError` is raised before any number is
computed.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deal_analyzer.assumptions import ASSUMPTIONS_VERSION, Assumptions
from deal_analyzer.capex import CapexEstimate, estimate_capex
from deal_analyzer.cashflow import CashFlowResult, DealInputs, compute_cash_flows
from deal_analyzer.legal_class import LegalAssessment, classify_legal
from deal_analyzer.listing import Listing
from deal_analyzer.maxbid import DEFAULT_PREMIUM, MaxBidResult, analyse_deal, hurdle_rate
from deal_analyzer.money import ONE, engine_math, pln
from deal_analyzer.ownership import (
    Confidence,
    OwnershipAssessment,
    classify_ownership,
    require_whole_ownership,
)
from deal_analyzer.vision import Condition, VisionOutput, VisionRecord, apply_vision

SCHEMA_VERSION = 1
ENGINE_VERSION = "0.1.0"
MIN_COMPARABLES = 3  # fewer comparable rents and the rent is refused: grade N (ENGINE-SPEC row 5)
THIN_MARKET = 10  # fewer than this lowers confidence


class RentInput(BaseModel):
    """The market rent as the rent model (N-04) reports it. Comparables are asking rents."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    monthly_rent_pln: Decimal = Field(ge=0)
    basis: Literal["asking", "achieved"] = "asking"
    comparables: int = Field(ge=0)


class RentApplied(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    input_monthly_pln: Decimal
    basis: Literal["asking", "achieved"]  # the result labels an asking-based anchor as such
    haircut: Decimal
    monthly_after_haircut_pln: Decimal
    monthly_used_pln: Decimal  # after the clamped vision adjustment, if any
    comparables: int
    confidence: Confidence


class DealAnalysis(BaseModel):
    """The canonical result. `model_dump_json()` is what is stored, shown through the API and rendered
    to Markdown."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: int = Field(
        default=SCHEMA_VERSION,
        description="Version of this document's shape. Additive changes keep it; a removed or renamed "
        "field, a changed type or a narrowed enum bumps it (docs/REPORT-SCHEMA.md)",
    )
    engine_version: str = Field(
        default=ENGINE_VERSION, description="Engine release that produced the numbers"
    )
    assumptions_version: str = Field(
        default=ASSUMPTIONS_VERSION, description="Version of the numeric assumptions the engine used"
    )
    listing: Listing = Field(description="The advert as extracted: asking price, never a deed price")
    ownership: OwnershipAssessment = Field(
        description="Whole or fractional ownership; fractional never gets here"
    )
    legal: LegalAssessment = Field(description="Residential / VAT-sale / non-residential classification")
    rent: RentApplied = Field(description="Market rent used, with its basis, haircut and confidence")
    capex: CapexEstimate = Field(description="Renovation cost estimate before any vision adjustment")
    capex_used_pln: Decimal = Field(description="CAPEX after the clamped vision adjustment (PLN, string)")
    vision: VisionRecord | None = Field(
        description="What the photos changed, or null when no vision answer was used (a degraded audit)"
    )
    cash_flow: CashFlowResult = Field(description="Ten-year cash flows and returns; computed in Python only")
    valuation: MaxBidResult = Field(description="Max Bid and the grade; a null value means 'not computed'")
    confidence: Confidence = Field(description="The weakest of the input confidences")
    warnings: tuple[str, ...] = Field(
        default=(), description="Stable codes for missing or doubtful inputs; they lower confidence"
    )


def _rent_confidence(comparables: int) -> Confidence:
    if comparables < MIN_COMPARABLES:
        return Confidence.LOW
    return Confidence.MEDIUM if comparables < THIN_MARKET else Confidence.HIGH


def _weakest(*levels: Confidence) -> Confidence:
    order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
    return min(levels, key=lambda c: order[c])


def analyse_listing(
    listing: Listing,
    *,
    rent: RentInput,
    risk_free: Decimal,
    premium: Decimal = DEFAULT_PREMIUM,
    vision: VisionOutput | None = None,
    model: str = "none",
    prompt_version: str = "none",
    market_value_pln: Decimal | None = None,
    assumptions: Assumptions | None = None,
) -> DealAnalysis:
    """Raises `FractionalOwnershipError` for a fractional share (invariant 5); everything else returns
    an analysis."""
    a = assumptions or Assumptions()
    ownership = classify_ownership(
        title=listing.title, description=listing.description, structured=listing.building_ownership
    )
    require_whole_ownership(ownership, listing.otodom_id)
    legal = classify_legal(title=listing.title, description=listing.description)

    with engine_math():
        after_haircut = (
            rent.monthly_rent_pln * (ONE - a.rent_haircut)
            if rent.basis == "asking"
            else rent.monthly_rent_pln
        )
    capex = estimate_capex(
        area_m2=listing.area_m2,
        condition=vision.condition if vision is not None else Condition.UNKNOWN,
        city=listing.city,
    )
    capex_used, rent_used = capex.base_pln, after_haircut
    record: VisionRecord | None = None
    if vision is not None:
        record = apply_vision(
            vision,
            model=model,
            prompt_version=prompt_version,
            capex_base=capex.base_pln,
            rent_base=after_haircut,
        )
        capex_used = record.capex.value if record.capex is not None else capex_used
        rent_used = record.rent.value if record.rent is not None else rent_used

    inputs = DealInputs(
        price_pln=listing.price_pln,
        price_basis=legal.price_basis,
        legal_class=legal.legal_class,
        area_m2=listing.area_m2,
        admin_fee_monthly_pln=listing.admin_fee_pln,
        monthly_rent_pln=rent_used,
        capex_pln=capex_used,
        market_value_pln=market_value_pln,
        assumptions=a,
    )
    cash_flow = compute_cash_flows(inputs)
    hurdle = hurdle_rate(risk_free, premium)
    valuation = analyse_deal(inputs, hurdle, insufficient_data=rent.comparables < MIN_COMPARABLES)

    rent_conf = _rent_confidence(rent.comparables)
    overall = _weakest(rent_conf, capex.confidence, legal.confidence)
    warnings = [*listing.warnings]
    if rent.comparables < MIN_COMPARABLES:
        warnings.append("rent_refused_too_few_comparables")
    elif rent.comparables < THIN_MARKET:
        warnings.append("rent_thin_market")
    if capex.prices_are_placeholders:
        warnings.append("capex_prices_are_placeholders")
    if legal.needs_review:
        warnings.append("legal_class_needs_review")
    if vision is None:
        warnings.append("vision_unavailable")
    warnings.extend(cash_flow.warnings)

    return DealAnalysis(
        listing=listing,
        ownership=ownership,
        legal=legal,
        rent=RentApplied(
            input_monthly_pln=pln(rent.monthly_rent_pln),
            basis=rent.basis,
            haircut=a.rent_haircut if rent.basis == "asking" else Decimal(0),
            monthly_after_haircut_pln=pln(after_haircut),
            monthly_used_pln=pln(rent_used),
            comparables=rent.comparables,
            confidence=rent_conf,
        ),
        capex=capex,
        capex_used_pln=pln(capex_used),
        vision=record,
        cash_flow=cash_flow,
        valuation=valuation,
        confidence=overall,
        warnings=tuple(dict.fromkeys(warnings)),
    )
