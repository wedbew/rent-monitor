"""Typed failures of the engine; the worker maps them to terminal audit states (blueprint §2)."""

from enum import StrEnum


class ExtractionCode(StrEnum):
    MALFORMED = "malformed"  # wrong container type, too many or too long entries
    MISSING_FIELD = "missing_field"
    INVALID_VALUE = "invalid_value"  # not parseable as the expected type
    OUT_OF_RANGE = "out_of_range"  # parseable but outside the plausible bounds


class ExtractionError(ValueError):
    """The payload cannot become a trustworthy `Listing`. Not retryable: the payload is what it is."""

    def __init__(self, code: ExtractionCode, field: str, message: str = "") -> None:
        super().__init__(f"{code.value}: {field}" + (f" ({message})" if message else ""))
        self.code = code
        self.field = field


class RentNotADealError(Exception):
    """Invariant 1: a RENT listing is not a deal (`rejected / RENT_NOT_DEAL`, no vision call)."""

    def __init__(self, otodom_id: str) -> None:
        super().__init__(f"listing {otodom_id} is a rental, not a sale")
        self.otodom_id = otodom_id


class FractionalOwnershipError(Exception):
    """Invariant 5: only a share of the flat is for sale (`rejected / FRACTIONAL_OWNERSHIP`)."""

    def __init__(self, otodom_id: str, evidence: tuple[str, ...] = ()) -> None:
        super().__init__(f"listing {otodom_id} offers a fractional share, not the whole flat")
        self.otodom_id = otodom_id
        self.evidence = evidence
