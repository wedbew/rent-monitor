# Test cases for .semgrep/rentmonitor.yml (RM-55); CI runs them in the security workflow:
# semgrep --test --config .semgrep/rentmonitor.yml .semgrep/rentmonitor.py
from decimal import Decimal

from sqlalchemy.orm import Mapped, mapped_column


class S:
    # ok: no-float-money
    traces_sample_rate: float = 0.1
    # ok: no-float-money
    total_s: float = 5.0
    # ruleid: no-float-money
    price_pln: float = 0.0
    # ruleid: no-float-money
    admin_fee: float
    # ruleid: no-float-money
    max_bid: float | None = None
    # ruleid: no-float-money
    capex_total: Mapped[float] = mapped_column()
    # ok: no-float-money
    price_pln2: Decimal = Decimal("0")


# ruleid: no-float-money
def f(monthly_rent: float) -> None: ...


# ok: no-float-money
def g(seconds: float) -> None: ...


# ruleid: no-float-money
def h(x: int, purchase_cost: float = 0.0) -> None: ...


def k(o, rent_pln, p):
    # ruleid: no-float-money
    float(o.price)
    # ruleid: no-float-money
    float(rent_pln)
    # ok: no-float-money
    float(p)
