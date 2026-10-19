"""Deterministic deal engine (docs/ENGINE-SPEC.md). Pure Python: no network, no clock, no database."""

from deal_analyzer.analysis import DealAnalysis, RentInput, analyse_listing
from deal_analyzer.assumptions import ASSUMPTIONS_VERSION, Assumptions
from deal_analyzer.capex import CapexEstimate, estimate_capex
from deal_analyzer.cashflow import CashFlowResult, DealInputs, compute_cash_flows, irr, npv
from deal_analyzer.errors import ExtractionCode, ExtractionError, FractionalOwnershipError, RentNotADealError
from deal_analyzer.extract import extract_listing
from deal_analyzer.legal_class import LegalAssessment, LegalClass, classify_legal
from deal_analyzer.listing import Listing
from deal_analyzer.markdown import render_markdown
from deal_analyzer.maxbid import MaxBidResult, analyse_deal, grade_for, hurdle_rate, solve_max_bid
from deal_analyzer.ownership import (
    Confidence,
    OwnershipAssessment,
    classify_ownership,
    require_whole_ownership,
)
from deal_analyzer.rent import RentComparable, RentEstimate, estimate_rent
from deal_analyzer.seller_questions import SellerQuestionBlock, seller_questions
from deal_analyzer.vision import (
    Applied,
    Condition,
    PhotoKind,
    VisionOutput,
    VisionOutputError,
    VisionRecord,
    apply_vision,
    clamp_adjustment,
    parse_vision_output,
)

__all__ = [
    "ASSUMPTIONS_VERSION",
    "Applied",
    "Assumptions",
    "CapexEstimate",
    "CashFlowResult",
    "Condition",
    "Confidence",
    "DealAnalysis",
    "DealInputs",
    "ExtractionCode",
    "ExtractionError",
    "FractionalOwnershipError",
    "LegalAssessment",
    "LegalClass",
    "Listing",
    "MaxBidResult",
    "OwnershipAssessment",
    "PhotoKind",
    "RentComparable",
    "RentEstimate",
    "RentInput",
    "RentNotADealError",
    "SellerQuestionBlock",
    "VisionOutput",
    "VisionOutputError",
    "VisionRecord",
    "analyse_deal",
    "analyse_listing",
    "apply_vision",
    "clamp_adjustment",
    "classify_legal",
    "classify_ownership",
    "compute_cash_flows",
    "estimate_capex",
    "estimate_rent",
    "extract_listing",
    "grade_for",
    "hurdle_rate",
    "irr",
    "npv",
    "parse_vision_output",
    "render_markdown",
    "require_whole_ownership",
    "seller_questions",
    "solve_max_bid",
]
