"""Deterministic deal engine (docs/ENGINE-SPEC.md). Pure Python: no network, no clock, no database."""

from deal_analyzer.assumptions import ASSUMPTIONS_VERSION, Assumptions
from deal_analyzer.cashflow import CashFlowResult, DealInputs, compute_cash_flows, irr, npv
from deal_analyzer.errors import ExtractionCode, ExtractionError, FractionalOwnershipError, RentNotADealError
from deal_analyzer.extract import extract_listing
from deal_analyzer.legal_class import LegalAssessment, LegalClass, classify_legal
from deal_analyzer.listing import Listing
from deal_analyzer.ownership import (
    Confidence,
    OwnershipAssessment,
    classify_ownership,
    require_whole_ownership,
)

__all__ = [
    "ASSUMPTIONS_VERSION",
    "Assumptions",
    "CashFlowResult",
    "Confidence",
    "DealInputs",
    "ExtractionCode",
    "ExtractionError",
    "FractionalOwnershipError",
    "LegalAssessment",
    "LegalClass",
    "Listing",
    "OwnershipAssessment",
    "RentNotADealError",
    "classify_legal",
    "classify_ownership",
    "compute_cash_flows",
    "extract_listing",
    "irr",
    "npv",
    "require_whole_ownership",
]
