"""Deterministic deal engine (docs/ENGINE-SPEC.md). Pure Python: no network, no clock, no database."""

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
    "Confidence",
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
    "extract_listing",
    "require_whole_ownership",
]
