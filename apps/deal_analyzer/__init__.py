"""Deterministic deal engine (docs/ENGINE-SPEC.md). Pure Python: no network, no clock, no database."""

from deal_analyzer.errors import ExtractionCode, ExtractionError, RentNotADealError
from deal_analyzer.extract import extract_listing
from deal_analyzer.listing import Listing

__all__ = ["ExtractionCode", "ExtractionError", "Listing", "RentNotADealError", "extract_listing"]
