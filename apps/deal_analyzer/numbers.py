"""Bounded parsing of numbers found in third-party payloads. Always `Decimal`, never `float`."""

import math
import re
from decimal import Decimal, InvalidOperation

from deal_analyzer.errors import ExtractionCode, ExtractionError

# Thousands separators seen on the portal: space, no-break space, narrow no-break space.
_SPACES = str.maketrans("", "", " \u00a0\u202f")
_PLAIN = re.compile(
    r"^[+-]?[0-9]{1,15}([.,][0-9]{1,6})?$"
)  # ASCII digits only: \d would accept other scripts


def parse_decimal(
    raw: object, field: str, *, low: Decimal, high: Decimal, allow_float: bool = False
) -> Decimal:
    """Parse '450000', '450 000', '55.3', '55,3' (or int/Decimal). Rejects NaN, infinity, exponents, bools."""
    if isinstance(raw, bool) or raw is None:
        raise ExtractionError(ExtractionCode.INVALID_VALUE, field, "not a number")
    if isinstance(raw, float):
        # JSON numbers with a fraction arrive as floats (coordinates). Accept them only where the caller opts
        # in, converted through their shortest text form so no binary noise enters a Decimal.
        if not allow_float or not math.isfinite(raw):
            raise ExtractionError(ExtractionCode.INVALID_VALUE, field, "floats are not accepted")
        text = repr(raw)
    elif isinstance(raw, int | Decimal):
        text = str(raw)
    elif isinstance(raw, str):
        text = raw.strip().translate(_SPACES)
    else:
        raise ExtractionError(ExtractionCode.INVALID_VALUE, field, "not a number")
    if len(text) > 32 or not _PLAIN.match(text):
        raise ExtractionError(ExtractionCode.INVALID_VALUE, field, "not a plain decimal number")
    try:
        value = Decimal(text.replace(",", "."))
    except InvalidOperation as exc:  # pragma: no cover  (the pattern already guarantees a valid literal)
        raise ExtractionError(ExtractionCode.INVALID_VALUE, field) from exc
    if not low <= value <= high:
        raise ExtractionError(ExtractionCode.OUT_OF_RANGE, field, f"must be within {low}..{high}")
    return value


def parse_int(raw: object, field: str, *, low: int, high: int) -> int:
    value = parse_decimal(raw, field, low=Decimal(low), high=Decimal(high))
    if value != value.to_integral_value():
        raise ExtractionError(ExtractionCode.INVALID_VALUE, field, "not a whole number")
    return int(value)
