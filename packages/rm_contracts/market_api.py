"""`/api/market/locations` response schemas: asking-rent aggregates, freshness and history (RM-421, #21).

LEGAL[third-party-data]: aggregates of original Otodom asking rents; terms unreviewed (B-012) (RM-421).
LEGAL[republication]: aggregates only, never an offer or listing content (RM-421).
GDPR[personal-data]: counts and quantiles; no personal data (RM-421).

Invariant 2: every figure is an *asking* rent (`price_basis` is the literal `asking`); no deed field exists.
Invariant 4: the values are copied from the published summaries; nothing is computed here or in the SPA.
A sample under the sufficiency threshold keeps its counts but its statistics are withheld (null with a
reason), so a missing value is never shown as zero.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rm_contracts.market import DataStatus

Series = Literal["additions", "cohort"]
WithheldReason = Literal["insufficient_sample"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AskingRentOut(_Out):
    """One published aggregate: a series and cohort on one summary day."""

    price_basis: Literal["asking"] = "asking"
    measure: Literal["original_asking_rent"] = "original_asking_rent"
    source: Literal["otodom"] = "otodom"
    archive_days: Literal[90] = 90
    caveats: list[str]
    summary_date: date
    series: Series
    cohort_key: str
    as_of: datetime
    observed_count: int = Field(ge=0)
    priced_count: int = Field(ge=0)
    first_observed_count: int | None
    median_rent_pln: Decimal | None
    median_ppm2: Decimal | None
    p25_ppm2: Decimal | None
    p75_ppm2: Decimal | None
    sufficient: bool
    withheld_reason: WithheldReason | None
    backfilled: bool


class LocationSummaryOut(_Out):
    location_id: str
    name: str
    data_status: DataStatus
    last_successful_refresh_at: datetime | None
    latest_summary_date: date | None
    median_rent_pln: Decimal | None
    median_ppm2: Decimal | None
    priced_count: int | None
    sufficient: bool | None
    withheld_reason: WithheldReason | None


class LocationPage(_Out):
    items: list[LocationSummaryOut]
    next_cursor: str | None


class LocationDetailOut(_Out):
    location_id: str
    name: str
    data_status: DataStatus
    last_successful_refresh_at: datetime | None
    covered_until: datetime | None
    unresolved_gap_since: datetime | None
    usable_for_ranking: bool
    cohort: list[AskingRentOut]  # the latest `cohort` series day, one entry per cohort key


class LocationHistoryOut(_Out):
    location_id: str
    series: Series
    cohort_key: str
    start: date
    end: date
    points: list[AskingRentOut]  # oldest first; a day without a published row is absent, not zero
