"""The report-pack catalog: exactly three one-time PLN packs of 1, 5 and 10 reports
(docs/PADDLE-INTEGRATION.md sections 1 and 2). Prices are the owner's decision and come only from approved
snapshots in configuration; nothing here has a default price, and a catalog that is incomplete, mixed or
inconsistent turns billing off.

The units a pack grants are fixed here by pack code and never read from provider data or buyer input
(`custom_data.reports` is not trusted anywhere).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from rm_core.settings import Settings

PackCode = Literal["reports_1", "reports_5", "reports_10"]
PACK_REPORTS: dict[PackCode, int] = {"reports_1": 1, "reports_5": 5, "reports_10": 10}
CURRENCY = "PLN"
MINOR_PER_UNIT = 100  # PLN minor units (grosze) per złoty
PRICE_ID_PREFIX = "pri_"


class CatalogError(ValueError):
    """The configured catalog is incomplete or inconsistent: sales stay off."""


@dataclass(frozen=True)
class Pack:
    code: PackCode
    reports: int
    price_id: str
    amount_minor: int  # approved gross price in grosze, as a string-compatible integer

    @property
    def gross_pln(self) -> Decimal:
        return Decimal(self.amount_minor) / MINOR_PER_UNIT


@dataclass(frozen=True)
class Catalog:
    environment: Literal["sandbox", "live"]
    packs: tuple[Pack, ...]

    def by_code(self, code: str) -> Pack | None:
        return next((p for p in self.packs if p.code == code), None)

    def by_price_id(self, price_id: str) -> Pack | None:
        return next((p for p in self.packs if p.price_id == price_id), None)


def _parse_amounts(text: str) -> dict[str, int]:
    amounts: dict[str, int] = {}
    for part in filter(None, (chunk.strip() for chunk in text.split(","))):
        code, sep, raw = part.partition("=")
        code, raw = code.strip(), raw.strip()
        if not sep or code in amounts or not raw.isdecimal() or int(raw) <= 0:
            msg = f"invalid approved amount entry {part!r}"
            raise CatalogError(msg)
        amounts[code] = int(raw)
    return amounts


def load_catalog(settings: Settings) -> Catalog | None:
    """None when billing is disabled. Raises `CatalogError` when it is enabled but cannot be trusted: a
    missing, unknown or duplicate price id or amount, a non-`pri_` id, or an unapproved amount."""
    if settings.billing_provider != "paddle":
        return None
    price_ids = {
        "reports_1": settings.paddle_price_reports_1,
        "reports_5": settings.paddle_price_reports_5,
        "reports_10": settings.paddle_price_reports_10,
    }
    amounts = _parse_amounts(settings.paddle_approved_amounts)
    unknown = set(amounts) - set(PACK_REPORTS)
    if unknown:
        msg = f"approved amounts name unknown packs: {sorted(unknown)}"
        raise CatalogError(msg)
    packs: list[Pack] = []
    for code, reports in PACK_REPORTS.items():
        price_id = price_ids[code].strip()
        if not price_id.startswith(PRICE_ID_PREFIX):
            msg = f"{code}: price id missing or not a Paddle price id"
            raise CatalogError(msg)
        if code not in amounts:
            msg = f"{code}: no owner-approved amount (PADDLE_APPROVED_AMOUNTS)"
            raise CatalogError(msg)
        packs.append(Pack(code=code, reports=reports, price_id=price_id, amount_minor=amounts[code]))
    if len({p.price_id for p in packs}) != len(packs):
        msg = "two packs share one price id"
        raise CatalogError(msg)
    return Catalog(environment=settings.paddle_environment, packs=tuple(packs))
