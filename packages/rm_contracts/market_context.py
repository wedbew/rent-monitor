"""`/api/market/locations/{id}/context` and `/api/market/overview` schemas (RM-282, #21, #48).

LEGAL[third-party-data]: GUS BDL statistics and Otodom asking-rent aggregates; terms unreviewed (B-012)
  (RM-282).
LEGAL[republication]: aggregates only; no offer or listing content (RM-282).
GDPR[personal-data]: none; territorial statistics (RM-282).

Every number is copied from a published BDL release or a published asking-rent summary; nothing is
computed in the SPA (invariant 4) and none of it enters the financial engine. A value measured at a
wider unit is a labelled `proxy` naming the unit actually measured; a missing value is `unavailable`
with a reason, never zero. Deed-type statistics (GUS transactions) and Otodom asking rents are never
mixed (invariant 2).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from rm_contracts.market import DataStatus

Level = Literal["gmina", "powiat", "wojewodztwo", "country"]
MappingStatusOut = Literal["mapped", "ambiguous", "unmatched"]
MetricState = Literal["direct", "proxy", "unavailable"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TerritoryOut(_Out):
    territory_id: str
    name: str
    level: Level
    teryt: str  # "" for the country


class PlaceMappingOut(_Out):
    status: MappingStatusOut
    relation: Literal["gmina", "within_gmina"] | None
    method: str
    candidates: list[TerritoryOut]  # filled when a name fits several gminas: never guessed


class PointOut(_Out):
    year: int
    value: Decimal | None
    status: str  # measured | suppressed | missing | invalid_attribute | withheld


class TrendOut(_Out):
    state: Literal["ok", "suppressed", "unavailable"]
    movement: Literal["up", "down", "flat"] | None
    favorable: bool | None
    from_year: int | None
    to_year: int | None
    absolute_change: Decimal | None
    percent_change: Decimal | None
    comparable_steps: int
    reasons: list[str]


class ParentValueOut(_Out):
    territory: TerritoryOut
    value: Decimal | None
    relation: Literal["above", "below", "equal"] | None  # the measured unit against this ancestor


class RankOut(_Out):
    scope: str  # "kraj" cohort or the peer group, human readable in the SPA from `scope_level`
    scope_level: Level
    state: Literal["ok", "suppressed", "unavailable"]
    rank: int | None
    of: int | None
    percentile: Decimal | None
    median: Decimal | None
    coverage: Decimal | None
    reasons: list[str]


class MetricViewOut(_Out):
    key: str
    name_pl: str
    family: str
    family_pl: str
    unit: str  # a person-readable unit, e.g. "zł/m²"
    note_pl: str
    direction: Literal["higher_is_favorable", "lower_is_favorable", "neutral"]
    state: MetricState
    reason: str | None
    measured: TerritoryOut | None
    year: int | None
    value: Decimal | None
    value_status: str | None
    series: list[PointOut]
    trend: TrendOut | None
    parents: list[ParentValueOut]
    national: RankOut | None
    peers: RankOut | None
    release_id: str | None


class SourceOut(_Out):
    name: Literal["GUS BDL"] = "GUS BDL"
    url: str = "https://bdl.stat.gov.pl"  # a plain string: fixtures rewrite every URL
    attribution_pl: str
    note_pl: str


class LocationContextOut(_Out):
    location_id: str
    name: str
    mapping: PlaceMappingOut
    chain: list[TerritoryOut]  # the territory the metrics answer for, then its ancestors up to the country
    metrics: list[MetricViewOut]
    published_metrics: int
    source: SourceOut


class OverviewPlaceOut(_Out):
    """One place of the catalogue with what a map, a sort and a comparison need, from published data only."""

    location_id: str
    name: str
    data_status: DataStatus
    last_successful_refresh_at: datetime | None
    latest_summary_date: date | None
    median_rent_pln: Decimal | None
    median_ppm2: Decimal | None
    priced_count: int | None
    sufficient: bool | None
    withheld_reason: Literal["insufficient_sample"] | None
    mapping: MappingStatusOut | None
    relation: Literal["gmina", "within_gmina"] | None
    gmina_teryt: str | None  # the administrative area the place maps to; never a listing's position
    powiat_name: str | None
    wojewodztwo_name: str | None


class OverviewOut(_Out):
    items: list[OverviewPlaceOut]
    total_places: int  # all places of the catalogue
    visible_places: int  # what this account may see (the free tier sees a fixed top list)
    access: Literal["full", "free"]
    free_limit: int
    free_rule_pl: str
