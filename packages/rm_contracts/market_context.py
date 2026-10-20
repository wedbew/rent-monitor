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
    cohort_key: str = "all"  # the apartment-size or rooms cohort every figure in `items` belongs to


# --- experimental locality index (RM-439) --------------------------------------------------------------
IndexStateOut = Literal["ok", "scored_not_ranked", "not_scored", "no_data", "unavailable"]


class IndexComponentOut(_Out):
    """One indicator inside the index: its value, where it stands among all gminas and what it adds."""

    key: str
    pillar: str
    pillar_pl: str
    name_pl: str
    explain_pl: str
    unit_pl: str
    weight: int  # the share of 100 the component carries when every indicator is available
    value: Decimal | None
    year: int | None
    basis: Literal["direct", "proxy"] | None
    measured: TerritoryOut | None  # the unit the value was read from (the powiat for a proxy)
    national_rank: int | None
    national_of: int | None
    score: Decimal | None  # 0..100, 100 = most favourable among the gminas that have a value
    points: Decimal | None  # what it adds to the index (weights renormalised over the available ones)
    favourable_pl: str  # "Wyższa wartość = korzystniej" or the opposite: the direction of the score


class IndexCohortOut(_Out):
    name_pl: str  # which units the position is among, e.g. "gminy w Polsce z kompletnym indeksem"
    scope: Literal["national", "voivodeship"]
    rank: int | None
    of: int | None
    percentile: Decimal | None
    unit_name: str | None  # the voivodeship for the regional position


class IndexOut(_Out):
    """An experimental statistical summary of the gmina's official indicators, not a property metric."""

    state: IndexStateOut
    reasons: list[str]  # why it is not scored or not ranked
    method_version: int
    title_pl: str
    caveat_pl: str
    higher_is_better: Literal[True] = True
    score: Decimal | None
    weight_coverage: Decimal | None
    positions: list[IndexCohortOut]
    components: list[IndexComponentOut]
    missing: list[str]  # names of the indicators with no value for this gmina
    gmina: TerritoryOut | None  # the unit the index describes
    oldest_year: int | None
    newest_year: int | None
    min_weight_coverage: Decimal
    min_cohort: int


class LocationIndexOut(_Out):
    location_id: str
    name: str
    mapping: PlaceMappingOut
    index: IndexOut
    source: SourceOut


class RankingEntryOut(_Out):
    location_id: str
    name: str
    gmina_name: str | None
    state: IndexStateOut
    score: Decimal | None
    rank: int | None
    of: int | None
    relation: Literal["gmina", "within_gmina"] | None


class RankingOverviewOut(_Out):
    method_version: int
    title_pl: str
    caveat_pl: str
    cohort_name_pl: str
    scored_gminas: int  # the national denominator
    total_places: int
    visible_places: int
    access: Literal["full", "free"]
    items: list[RankingEntryOut]  # best position first, places without a score last
    source: SourceOut
