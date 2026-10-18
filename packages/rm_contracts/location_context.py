"""Typed contracts for BDL (GUS) location context: territories, metrics, observations, rankings.

LCTX-01 (RM-378), proposal in `docs/BDL-LOCATION-CONTEXT-CONTRACT.md`. Pure data shapes: no I/O, no DB.

LEGAL[third-party-data]: models describe GUS BDL statistics (source terms, attribution and
redistribution limits are unreviewed, B-023/B-012) (RM-378)
GDPR[processor]: none of these models hold personal data; aggregate public statistics only (RM-378)

Open policy (B-023): metric selection, coverage thresholds, scoring and staleness limits are NOT decided here.
Every threshold is optional; `None` means "owner has not decided" and gates report `undecided`,
never `passed`.
BDL statistics are contextual or deed-type facts and are never blended with asking prices (invariant 2).
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,63}$")]
TerritoryId = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z]+$")]
Ratio = Annotated[Decimal, Field(ge=Decimal(0), le=Decimal(1))]

# Methodology versions of the pure rules below; bump when a rule changes (the contract requires versioning).
RANKING_METHOD_VERSION = 1


class TerritoryLevel(StrEnum):
    gmina = "gmina"
    powiat = "powiat"
    wojewodztwo = "wojewodztwo"
    country = "country"


# Order from the finest to the widest level; parent of a level is the next one.
LEVEL_ORDER = (
    TerritoryLevel.gmina,
    TerritoryLevel.powiat,
    TerritoryLevel.wojewodztwo,
    TerritoryLevel.country,
)

# TERYT code length per level (strings; leading zeros are significant). Gmina: 7 digits incl. type digit.
TERYT_LENGTH = {
    TerritoryLevel.gmina: 7,
    TerritoryLevel.powiat: 4,
    TerritoryLevel.wojewodztwo: 2,
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TerritoryRef(_Model):
    """One administrative unit. BDL ids and TERYT codes are distinct identifiers (both kept as strings)."""

    territory_id: TerritoryId  # BDL unit id
    teryt: Annotated[str, StringConstraints(pattern=r"^[0-9]{0,7}$")]  # empty only for the country
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    level: TerritoryLevel
    parent_id: TerritoryId | None = None
    # City with powiat rights: the gmina keeps its own id and points at the powiat of the same name; the
    # flag records that the two roles exist so population is never counted twice.
    has_powiat_rights: bool = False

    @model_validator(mode="after")
    def _check(self) -> Self:
        expected = TERYT_LENGTH.get(self.level)
        if expected is None:
            if self.teryt:
                raise ValueError("country has no TERYT code")
        elif len(self.teryt) != expected:
            raise ValueError(f"{self.level.value} TERYT must have {expected} digits")
        if (self.parent_id is None) != (self.level is TerritoryLevel.country):
            raise ValueError("only the country has no parent")
        if self.parent_id == self.territory_id:
            raise ValueError("territory cannot be its own parent")
        if self.has_powiat_rights and self.level is not TerritoryLevel.gmina:
            raise ValueError("powiat rights are a gmina role")
        return self


class Direction(StrEnum):
    """Which end of a metric is favourable. `neutral` = size/price orderings: say higher/lower, not better."""

    higher_is_favorable = "higher_is_favorable"
    lower_is_favorable = "lower_is_favorable"
    neutral = "neutral"


class ChangeBasis(StrEnum):
    """How a change between two years may be expressed."""

    percent = "percent"  # positive-only quantities (counts, prices); percent change is meaningful
    absolute = "absolute"  # signed or rate-like quantities (net migration, rates): never percent growth


class SelectionStatus(StrEnum):
    selected = "selected"
    deferred = "deferred"
    unavailable = "unavailable"  # e.g. the two unresolved land-market metrics


class MetricDefinition(_Model):
    """One approved (or deferred / unavailable) BDL metric. Selection itself is an owner decision (B-023)."""

    key: Key
    version: int = Field(ge=1)
    name_pl: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    unit: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    native_level: TerritoryLevel
    # Levels at which the source itself publishes this metric. Parent values are never built by averaging.
    published_levels: frozenset[TerritoryLevel]
    direction: Direction = Direction.neutral
    change_basis: ChangeBasis = ChangeBasis.absolute
    additive: bool = False  # only additive metrics may ever be summed, and only when a contract says so
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    selection: SelectionStatus = SelectionStatus.deferred
    bdl_variable_id: str | None = None  # reviewed source signature; None until reviewed

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.native_level not in self.published_levels:
            raise ValueError("native_level must be among published_levels")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value exceeds max_value")
        if self.selection is SelectionStatus.selected and not self.bdl_variable_id:
            raise ValueError("a selected metric needs a reviewed bdl_variable_id")
        return self


class PublicationPolicy(_Model):
    """Gate thresholds for one metric version. Every value `None` = undecided (B-023), not 'no limit'."""

    metric_key: Key
    metric_version: int = Field(ge=1)
    min_coverage: Ratio | None = None  # eligible / expected territories
    min_cohort_size: int | None = Field(default=None, ge=1)


class ObservationStatus(StrEnum):
    measured = "measured"  # includes a genuine zero
    suppressed = "suppressed"  # source withholds the value
    missing = "missing"  # no source row
    invalid_attribute = "invalid_attribute"  # source row unusable (bad attribute/unit)
    withheld = "withheld"  # raw value kept, comparison suppressed (territorial break, review)


class Observation(_Model):
    """One metric value for one territory and one annual period, with provenance."""

    territory_id: TerritoryId
    metric_key: Key
    metric_version: int = Field(ge=1)
    year: int = Field(ge=1990, le=2100)
    status: ObservationStatus
    value: Decimal | None = None
    reason: Annotated[str, StringConstraints(max_length=200)] | None = None
    source_digest: Sha256Hex

    @model_validator(mode="after")
    def _check(self) -> Self:
        has_value = self.status in {ObservationStatus.measured, ObservationStatus.withheld}
        if has_value and self.value is None:
            raise ValueError(f"{self.status.value} observation needs a value")
        if not has_value and self.value is not None:
            raise ValueError(f"{self.status.value} observation must not carry a value")
        if self.status is not ObservationStatus.measured and not self.reason:
            raise ValueError("a gap or withheld observation needs a reason")
        if self.value is not None and not self.value.is_finite():
            raise ValueError("value must be finite")
        return self


class BoundaryBreak(_Model):
    """Territorial change effective in `effective_year`; comparisons spanning it are withheld."""

    territory_id: TerritoryId
    effective_year: int = Field(ge=1990, le=2100)
    reason: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class RankedEntry(_Model):
    territory_id: TerritoryId
    value: Decimal
    rank: int = Field(ge=1)  # competition rank: 1, 2, 2, 4
    percentile: Ratio | None  # midrank percentile; None for a one-unit cohort


class RankingResult(_Model):
    metric_key: Key
    metric_version: int
    year: int
    direction: Direction
    cohort_id: str  # caller-declared cohort identity (e.g. "country", "wojewodztwo:02")
    level: TerritoryLevel
    expected: int
    eligible: int
    missing: int
    excluded: int
    method_version: int = RANKING_METHOD_VERSION
    tie_rule: Literal["competition"] = "competition"
    percentile_rule: Literal["midrank"] = "midrank"
    entries: tuple[RankedEntry, ...]


class GateVerdict(StrEnum):
    passed = "passed"
    failed = "failed"
    undecided = "undecided"  # policy values not decided by the owner


class GateResult(_Model):
    verdict: GateVerdict
    eligible: int
    expected: int
    coverage: Decimal | None  # None when expected == 0
    reasons: tuple[str, ...] = ()


class ComparisonState(StrEnum):
    comparable = "comparable"
    missing_endpoint = "missing_endpoint"
    withheld = "withheld"  # observation withheld or boundary break


class PeriodComparison(_Model):
    metric_key: Key
    territory_id: TerritoryId
    year_a: int
    year_b: int
    state: ComparisonState
    reason: str | None = None
    value_a: Decimal | None = None
    value_b: Decimal | None = None
    absolute_change: Decimal | None = None
    percent_change: Decimal | None = None  # only for percent-basis metrics with a positive base


class ViewState(StrEnum):
    direct = "direct"
    proxy = "proxy"  # published at a wider level and shown as parent context
    unavailable = "unavailable"


class LocationMetricView(_Model):
    """What a profile may show for (territory, metric): the actual measured unit, never a substitute."""

    requested_territory_id: TerritoryId
    metric_key: Key
    state: ViewState
    measured_territory_id: TerritoryId | None = None
    measured_level: TerritoryLevel | None = None
    observation: Observation | None = None
    reason: str | None = None
