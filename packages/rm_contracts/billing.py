"""Schemas for `/api/billing` (docs/PADDLE-INTEGRATION.md section 3). Inbound models forbid unknown fields.

Nothing a browser sends can set an amount, a report count, a price id, a user id, a discount or a redirect:
the only inputs are the pack code and an idempotency key. Money is a `Decimal` string.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

PackCodeName = Literal["reports_1", "reports_5", "reports_10"]
PurchaseStateName = Literal[
    "intent", "creating", "created", "creation_unknown", "failed", "paid", "granted", "review", "refunded"
]


class PackOut(BaseModel):
    code: PackCodeName
    reports: int
    gross_pln: Decimal
    currency: Literal["PLN"] = "PLN"
    catalog_version: int


class PacksOut(BaseModel):
    enabled: bool
    packs: list[PackOut]


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack_code: PackCodeName


class PurchaseOut(BaseModel):
    """GDPR[personal-data]: returned to the buyer only. No raw provider payload, no binding token."""

    purchase_id: UUID
    pack_code: PackCodeName
    reports: int
    gross_pln: Decimal
    currency: Literal["PLN"] = "PLN"
    state: PurchaseStateName
    transaction_id: str | None
    checkout_url: str | None
    created_at: datetime
    granted_at: datetime | None
    refunded_at: datetime | None


class InvoiceOut(BaseModel):
    """A link to the document Paddle issued for this sale. Short-lived: fetched on demand, never stored."""

    url: str


class RefundRequest(BaseModel):
    """Support's reason, sent to Paddle with the request (never shown to the buyer by us)."""

    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class RefundOut(BaseModel):
    status: Literal["requested", "exists", "unknown"]
    adjustment_id: str | None


class PurchasesOut(BaseModel):
    purchases: list[PurchaseOut]
