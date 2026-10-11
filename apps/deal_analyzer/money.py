"""Decimal arithmetic for the engine (docs/ENGINE-SPEC.md row 13).

All engine math runs inside `engine_math()`, a LOCAL `decimal.Context` (28 digits, round half up). The global
context is never read or changed, so results are byte-identical whatever the host process did to `decimal`.
Values are rounded only when they leave the engine: money to 0.01 PLN, rates to 4 decimals.
"""

from collections.abc import Generator
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext

ENGINE_CONTEXT = Context(prec=28, rounding=ROUND_HALF_UP, Emin=-999999, Emax=999999)
_CENT = Decimal("0.01")
_RATE = Decimal("0.0001")
ZERO = Decimal(0)
ONE = Decimal(1)
TWELVE = Decimal(12)


@contextmanager
def engine_math() -> Generator[Context]:
    with localcontext(ENGINE_CONTEXT) as ctx:
        yield ctx


def pln(value: Decimal) -> Decimal:
    """Round money for output: half-up to 0.01 PLN."""
    with engine_math():
        return value.quantize(_CENT)


def rate(value: Decimal) -> Decimal:
    """Round a rate or ratio for output: half-up to 4 decimals."""
    with engine_math():
        return value.quantize(_RATE)
