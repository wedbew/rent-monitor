"""Schemas for `/api/audits` (blueprint §2 *Listing-analysis contract*).

Inbound models forbid unknown fields. The canonical `DealAnalysis` JSON is carried as an opaque object: the
API echoes what the worker stored and never derives a number from it (agents.md §2, invariant 4).
LEGAL[republication]: `result` echoes fields of third-party listing data to the tenant that requested it.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MAX_LISTING_REF = 300


class AuditState(StrEnum):
    """Mirrors `rm_core.db.models.AuditStatus`; `tests/unit/test_audit_contracts.py` fails if they drift."""

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    succeeded_degraded = "succeeded_degraded"
    rejected = "rejected"
    failed_input = "failed_input"
    failed_upstream = "failed_upstream"
    failed_internal = "failed_internal"
    cancelled = "cancelled"


class ChargeStateName(StrEnum):
    """Mirrors `rm_core.db.models.ChargeState`."""

    reserved = "reserved"
    captured = "captured"
    released = "released"


class AuditCreate(BaseModel):
    """`listing_ref` is bounded here and normalised to the short Otodom id by the route
    (`rm_core.listing_ref.parse_listing_ref`, which rejects anything but an Otodom URL or id)."""

    model_config = ConfigDict(extra="forbid")

    listing_ref: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LISTING_REF)
    ]
    lang: Literal["pl", "en"] = "pl"
    analyst: bool = False  # Pro-only text-LLM audit; refused with FEATURE_NOT_IN_PLAN until it exists


class AuditAccepted(BaseModel):
    audit_id: UUID
    status: AuditState
    events_url: str
    credits_remaining: int | None = Field(description="None: the audit is within the plan allowance")


class SellerQuestionRuleName(StrEnum):
    """Mirrors `deal_analyzer.seller_questions.SellerQuestionRule`; the drift test compares the values."""

    admin_fee_unknown = "admin_fee_unknown"
    floor_unknown = "floor_unknown"
    build_year_unknown = "build_year_unknown"
    condition_unclear = "condition_unclear"
    floor_plan_missing = "floor_plan_missing"
    seller_status_unclear = "seller_status_unclear"
    equipment_sale_status = "equipment_sale_status"


class SellerQuestion(BaseModel):
    """A question to ask the seller (G-03, RM-404). Mirrors `deal_analyzer.seller_questions.SellerQuestion`;
    `tests/unit/test_seller_questions.py` fails if the two schemas drift."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^sq-[0-9a-f]{16}$", description="stable: rule plus evidence key")
    rule: SellerQuestionRuleName = Field(description="stable rule code, for localisation in the SPA")
    text: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=300)
    evidence: tuple[str, ...] = Field(
        max_length=20, description="the facts it rests on; the engine never emits an empty list"
    )


class SellerQuestionBlock(BaseModel):
    """The versioned block persisted with the audit. Null on audits made before RM-404: no questions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    questions: tuple[SellerQuestion, ...] = Field(max_length=40)


class AuditOut(BaseModel):
    """One audit. Money columns are copied from `result` by the worker, never computed by the API."""

    audit_id: UUID
    otodom_id: str
    status: AuditState
    error_code: str | None
    charge_state: ChargeStateName
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    grade: str | None
    asking_price_pln: Decimal | None
    max_bid_pln: Decimal | None
    irr_10y: Decimal | None
    capex_pln: Decimal | None
    result: dict[str, Any] | None = Field(
        description="canonical DealAnalysis JSON; null until a terminal success. Its shape is "
        "docs/deal-analysis.schema.json for the version in `result.schema_version`"
    )
    seller_questions: SellerQuestionBlock | None = Field(
        default=None,
        description="questions to ask the seller, generated with the report (RM-404); null when the audit "
        "has none stored (every audit made before RM-404, or no successful result)",
    )


class AuditPage(BaseModel):
    """One page of the caller's audits, newest first. There is deliberately no total: an exact count under
    filters is a scan per request, and a cursor is all a list needs."""

    items: list["AuditSummary"]
    next_cursor: str | None = Field(
        description="opaque; pass it back as `cursor` for the next page. null: this was the last page"
    )


class AuditSummary(BaseModel):
    """List row: the same fields without the full result."""

    audit_id: UUID
    otodom_id: str
    status: AuditState
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None
    grade: str | None
    asking_price_pln: Decimal | None
    max_bid_pln: Decimal | None
