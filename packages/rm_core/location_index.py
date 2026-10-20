"""Experimental locality index from published GUS BDL statistics (RM-439, LCTX): pure and deterministic.

LEGAL[third-party-data]: derives a ranking from public GUS BDL statistics; attribution and redistribution
  terms are unreviewed (B-012).
GDPR[personal-data]: none; aggregate territorial statistics only.

What it is: an *experimental* summary of how a gmina compares with the other gminas of Poland on a small,
documented set of official indicators (demography, labour market and income, business activity, municipal
own revenue). It is a description of the locality's statistics. It is not a property valuation, not a rent or
price forecast and not a return: nothing here feeds the financial engine (invariant 4) and no Otodom asking
rent or deed price enters it (invariant 2).

Method (version `INDEX_VERSION`, owner-delegated policy of 2026-10-19 recorded in L-096):
- Each component is one indicator's value for the gmina in the newest published year of that indicator. A
  powiat-grain indicator (earnings, unemployment) is the gmina's powiat value, labelled `proxy`; it is never
  presented as the gmina's own.
- A component's score is the gmina's national percentile among the gminas that have a value, oriented so
  that 100 is always the favourable end (the registry says which end is favourable; a lower unemployment
  rate scores higher). Ties share a rank (competition ranking: 1, 2, 2, 4).
- The index is the weight-weighted mean of the available component scores. It is shown only when every
  pillar has at least one component and the available weight is at least `MIN_WEIGHT_COVERAGE` of the
  total; otherwise the gmina is *not scored* and the reasons are listed. A rank needs a national cohort of
  at least `MIN_COHORT` scored gminas; the voivodeship rank needs `MIN_REGION`.
- Counts are first put on a per-1,000-residents basis (same unit, same year) so a big gmina is not simply
  "better".
Everything is `Decimal`; there is no float.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import Final

from rm_contracts.location_context import (
    Direction,
    Observation,
    ObservationStatus,
    TerritoryLevel,
    TerritoryRef,
)

from rm_core.bdl_metrics import BY_KEY
from rm_core.location_contracts import TerritoryHierarchy

INDEX_VERSION: Final = 1
MIN_WEIGHT_COVERAGE: Final = Decimal("0.80")
MIN_COHORT: Final = 50
MIN_REGION: Final = 5
_Q2 = Decimal("0.01")
_HUNDRED = Decimal(100)


class Pillar(StrEnum):
    demography = "demography"
    labour = "labour"
    business = "business"
    fiscal = "fiscal"


PILLAR_NAMES_PL: Final = {
    Pillar.demography: "Demografia",
    Pillar.labour: "Rynek pracy i dochody",
    Pillar.business: "Przedsiębiorczość",
    Pillar.fiscal: "Dochody własne gminy",
}


@dataclass(frozen=True)
class ComponentSpec:
    key: str
    pillar: Pillar
    name_pl: str
    metric: str  # registry key of the indicator that carries the value
    per_thousand_of: str | None  # registry key of the denominator when the count is put per 1,000 residents
    weight: int  # share of 100; the weights sum to 100
    explain_pl: str
    unit_pl: str


COMPONENTS: Final[tuple[ComponentSpec, ...]] = (
    ComponentSpec(
        "net_migration_per_1000",
        Pillar.demography,
        "Saldo migracji na pobyt stały na 1000 mieszkańców",
        "net_migration",
        "population_total",
        20,
        "Więcej osób, które osiedliły się w gminie, niż tych, które się z niej wymeldowały.",
        "osób na 1000 mieszkańców",
    ),
    ComponentSpec(
        "natural_increase_per_1000",
        Pillar.demography,
        "Przyrost naturalny na 1000 mieszkańców",
        "natural_increase",
        "population_total",
        10,
        "Urodzenia minus zgony. Wyżej = korzystniej.",
        "osób na 1000 mieszkańców",
    ),
    ComponentSpec(
        "unemployment_share",
        Pillar.labour,
        "Udział zarejestrowanych bezrobotnych w ludności w wieku produkcyjnym",
        "unemployment_share_working_age",
        None,
        15,
        "Mniej bezrobotnych = korzystniej, dlatego niższa wartość daje wyższy wynik.",
        "%",
    ),
    ComponentSpec(
        "earnings",
        Pillar.labour,
        "Przeciętne miesięczne wynagrodzenie brutto",
        "average_monthly_gross_earnings",
        None,
        15,
        "Wyższe wynagrodzenia = korzystniej. GUS podaje je dla powiatu; to wartość powiatu, nie gminy.",
        "zł",
    ),
    ComponentSpec(
        "business_density",
        Pillar.business,
        "Podmioty gospodarcze (REGON) na 10 tys. mieszkańców",
        "regon_entities_per_10k",
        None,
        20,
        "Więcej firm na mieszkańca = korzystniej. Wyżej = korzystniej.",
        "podmiotów na 10 tys. mieszkańców",
    ),
    ComponentSpec(
        "own_revenue",
        Pillar.fiscal,
        "Dochody własne gminy na mieszkańca",
        "own_revenue_per_resident",
        None,
        20,
        "Wyższe dochody własne = większa zdolność gminy do utrzymania usług. Wyżej = korzystniej.",
        "zł na mieszkańca",
    ),
)
assert sum(c.weight for c in COMPONENTS) == 100  # noqa: S101


class IndexState(StrEnum):
    ok = "ok"  # scored and ranked
    scored_not_ranked = "scored_not_ranked"  # scored, but the cohort is too small for a rank
    not_scored = "not_scored"  # too little data
    no_data = "no_data"  # nothing published at all


@dataclass(frozen=True)
class RawValue:
    value: Decimal
    year: int
    measured_territory_id: str
    proxy: bool


@dataclass(frozen=True)
class ComponentScore:
    key: str
    value: Decimal
    year: int
    measured_territory_id: str
    proxy: bool
    rank: int
    of: int
    score: Decimal  # 0..100, 100 = most favourable
    points: Decimal  # contribution to the index, already scaled by the available weight


@dataclass(frozen=True)
class GminaIndex:
    territory_id: str
    state: IndexState
    score: Decimal | None
    components: tuple[ComponentScore, ...]
    missing: tuple[str, ...]  # component keys with no value
    weight_coverage: Decimal
    reasons: tuple[str, ...]
    rank: int | None = None
    of: int | None = None
    percentile: Decimal | None = None
    region_rank: int | None = None
    region_of: int | None = None
    region_id: str | None = None


def _favourable(direction: Direction) -> int:
    """+1 when a larger value is favourable, -1 when a smaller one is; neutral indicators are never used."""
    if direction is Direction.higher_is_favorable:
        return 1
    if direction is Direction.lower_is_favorable:
        return -1
    raise ValueError("an index component needs a metric with a favourable direction")


def competition_ranks(values: Mapping[str, Decimal], *, larger_is_better: bool) -> dict[str, int]:
    """1, 2, 2, 4: tied values share the best rank of their group."""
    ordered = sorted(values.items(), key=lambda kv: (-kv[1] if larger_is_better else kv[1], kv[0]))
    ranks: dict[str, int] = {}
    previous: Decimal | None = None
    current = 0
    for position, (tid, v) in enumerate(ordered, start=1):
        if previous is None or v != previous:
            current = position
            previous = v
        ranks[tid] = current
    return ranks


def percentile_from_rank(rank: int, of: int) -> Decimal:
    """100 for rank 1, 0 for the last; a cohort of one has no percentile (the caller shows none)."""
    if of < 2:
        return Decimal(0)
    return ((Decimal(of - rank) / Decimal(of - 1)) * _HUNDRED).quantize(_Q2, ROUND_HALF_EVEN)


def _latest(rows: Iterable[Observation]) -> dict[str, Decimal]:
    return {
        o.territory_id: o.value
        for o in rows
        if o.status is ObservationStatus.measured and o.value is not None
    }


@dataclass(frozen=True)
class IndicatorSlice:
    """The newest published year of one indicator: every territory's measured value."""

    year: int
    values: Mapping[str, Decimal]

    @classmethod
    def of(cls, year: int, rows: Iterable[Observation]) -> "IndicatorSlice":
        return cls(year, _latest(o for o in rows if o.year == year))


def component_values(
    hierarchy: TerritoryHierarchy,
    slices: Mapping[str, IndicatorSlice],
    spec: ComponentSpec,
    gminas: Sequence[TerritoryRef],
) -> dict[str, RawValue]:
    """The component's raw value per gmina: its own, or its powiat's (proxy) for a powiat-grain indicator."""
    defn = BY_KEY[spec.metric]
    numerator = slices.get(spec.metric)
    if numerator is None:
        return {}
    denominator = slices.get(spec.per_thousand_of) if spec.per_thousand_of else None
    if spec.per_thousand_of and denominator is None:
        return {}
    out: dict[str, RawValue] = {}
    for g in gminas:
        measured = g
        proxy = False
        if defn.native is not TerritoryLevel.gmina:
            parent = hierarchy.get(g.parent_id) if g.parent_id else None
            if parent is None or parent.level is not TerritoryLevel.powiat:
                continue
            measured, proxy = parent, True
        v = numerator.values.get(measured.territory_id)
        if v is None:
            continue
        if denominator is not None:
            d = denominator.values.get(measured.territory_id)
            if d is None or d <= 0:
                continue
            v = v / d * Decimal(1000)
        out[g.territory_id] = RawValue(v, numerator.year, measured.territory_id, proxy)
    return out


def build_index(hierarchy: TerritoryHierarchy, slices: Mapping[str, IndicatorSlice]) -> dict[str, GminaIndex]:
    """The index of every gmina of the reference, from the newest published slice of each indicator."""
    gminas = [t for t in hierarchy.all() if t.level is TerritoryLevel.gmina]
    raw: dict[str, dict[str, RawValue]] = {}
    ranks: dict[str, dict[str, int]] = {}
    for spec in COMPONENTS:
        values = component_values(hierarchy, slices, spec, gminas)
        raw[spec.key] = values
        direction = _favourable(BY_KEY[spec.metric].direction)
        ranks[spec.key] = competition_ranks(
            {tid: rv.value for tid, rv in values.items()}, larger_is_better=direction > 0
        )
    total_weight = Decimal(sum(c.weight for c in COMPONENTS))
    drafts: dict[str, GminaIndex] = {}
    for g in gminas:
        present = [c for c in COMPONENTS if g.territory_id in raw[c.key]]
        missing = tuple(c.key for c in COMPONENTS if g.territory_id not in raw[c.key])
        weight = Decimal(sum(c.weight for c in present))
        coverage = (weight / total_weight).quantize(_Q2, ROUND_HALF_EVEN)
        reasons: list[str] = []
        pillars_present = {c.pillar for c in present}
        for pillar in Pillar:
            if pillar not in pillars_present:
                reasons.append(f"brak danych w obszarze „{PILLAR_NAMES_PL[pillar]}”")
        if coverage < MIN_WEIGHT_COVERAGE:
            reasons.append(
                f"dostępne wskaźniki to {int(coverage * 100)}% wagi, wymagane "
                f"{int(MIN_WEIGHT_COVERAGE * 100)}%"
            )
        if not present:
            drafts[g.territory_id] = GminaIndex(
                g.territory_id, IndexState.no_data, None, (), missing, coverage, tuple(reasons)
            )
            continue
        scored: list[ComponentScore] = []
        for c in present:
            rv = raw[c.key][g.territory_id]
            rank = ranks[c.key][g.territory_id]
            of = len(raw[c.key])
            score = percentile_from_rank(rank, of)
            scored.append(
                ComponentScore(
                    c.key,
                    rv.value.quantize(_Q2, ROUND_HALF_EVEN),
                    rv.year,
                    rv.measured_territory_id,
                    rv.proxy,
                    rank,
                    of,
                    score,
                    (Decimal(c.weight) / weight * score).quantize(_Q2, ROUND_HALF_EVEN),
                )
            )
        if reasons:
            drafts[g.territory_id] = GminaIndex(
                g.territory_id, IndexState.not_scored, None, tuple(scored), missing, coverage, tuple(reasons)
            )
            continue
        index = sum(
            (Decimal(c.weight) / weight * s.score for c, s in zip(present, scored, strict=True)), Decimal(0)
        )
        drafts[g.territory_id] = GminaIndex(
            g.territory_id,
            IndexState.scored_not_ranked,
            index.quantize(_Q2, ROUND_HALF_EVEN),
            tuple(scored),
            missing,
            coverage,
            (),
        )
    return _rank_scored(hierarchy, drafts)


def _rank_scored(hierarchy: TerritoryHierarchy, drafts: dict[str, GminaIndex]) -> dict[str, GminaIndex]:
    scored = {tid: g.score for tid, g in drafts.items() if g.score is not None}
    national = competition_ranks(scored, larger_is_better=True) if len(scored) >= MIN_COHORT else {}
    by_region: dict[str, dict[str, Decimal]] = {}
    region_of: dict[str, str] = {}
    for tid, value in scored.items():
        region = next((a for a in hierarchy.ancestors(tid) if a.level is TerritoryLevel.wojewodztwo), None)
        if region is not None:
            region_of[tid] = region.territory_id
            by_region.setdefault(region.territory_id, {})[tid] = value
    region_ranks = {
        r: competition_ranks(vals, larger_is_better=True)
        for r, vals in by_region.items()
        if len(vals) >= MIN_REGION
    }
    out: dict[str, GminaIndex] = {}
    for tid, g in drafts.items():
        if g.score is None:
            out[tid] = g
            continue
        rank = national.get(tid)
        region = region_of.get(tid)
        in_region = region_ranks.get(region or "")
        out[tid] = GminaIndex(
            g.territory_id,
            IndexState.ok if rank is not None else IndexState.scored_not_ranked,
            g.score,
            g.components,
            g.missing,
            g.weight_coverage,
            g.reasons
            if rank is not None
            else (*g.reasons, f"kohorta mniejsza niż {MIN_COHORT} gmin: brak pozycji"),
            rank=rank,
            of=len(scored) if rank is not None else None,
            percentile=percentile_from_rank(rank, len(scored)) if rank is not None else None,
            region_rank=in_region.get(tid) if in_region else None,
            region_of=len(by_region[region]) if in_region and region else None,
            region_id=region,
        )
    return out
