"""Compose the API shapes of the experimental locality index from a computed snapshot (RM-439).

LEGAL[third-party-data]: GUS BDL statistics with source, year and level (RM-439).
GDPR[personal-data]: none.
"""

from rm_contracts.location_context import Direction, TerritoryLevel
from rm_contracts.market_context import (
    IndexCohortOut,
    IndexComponentOut,
    IndexOut,
)

from rm_core.bdl_metrics import BY_KEY
from rm_core.location_contracts import HierarchyError, TerritoryHierarchy
from rm_core.location_index import (
    COMPONENTS,
    INDEX_VERSION,
    MIN_COHORT,
    MIN_WEIGHT_COVERAGE,
    PILLAR_NAMES_PL,
    GminaIndex,
)
from rm_core.location_index_read import IndexSnapshot
from rm_core.location_profile import territory_out

TITLE_PL = "Eksperymentalny indeks warunków lokalnych"
CAVEAT_PL = (
    "To eksperymentalne podsumowanie oficjalnych wskaźników GUS: porównuje gminę z innymi gminami w Polsce. "
    "Nie jest wyceną nieruchomości, prognozą czynszów ani cen i nie wchodzi do żadnego wyniku finansowego."
)
COHORT_PL = "gminy w Polsce z kompletnym indeksem"
HIGHER_PL = "Wyższa wartość = korzystniej"
LOWER_PL = "Niższa wartość = korzystniej"


def _direction_pl(metric: str) -> str:
    return LOWER_PL if BY_KEY[metric].direction is Direction.lower_is_favorable else HIGHER_PL


def unavailable(reasons: list[str]) -> IndexOut:
    return IndexOut(
        state="unavailable",
        reasons=reasons,
        method_version=INDEX_VERSION,
        title_pl=TITLE_PL,
        caveat_pl=CAVEAT_PL,
        score=None,
        weight_coverage=None,
        positions=[],
        components=[],
        missing=[],
        gmina=None,
        oldest_year=None,
        newest_year=None,
        min_weight_coverage=MIN_WEIGHT_COVERAGE,
        min_cohort=MIN_COHORT,
    )


def index_out(snapshot: IndexSnapshot, hierarchy: TerritoryHierarchy, gmina_id: str) -> IndexOut:
    g: GminaIndex | None = snapshot.index.get(gmina_id)
    if g is None:
        return unavailable(["Ta jednostka nie jest gminą w opublikowanym wykazie GUS."])
    by_key = {c.key: c for c in g.components}
    components: list[IndexComponentOut] = []
    for spec in COMPONENTS:
        got = by_key.get(spec.key)
        components.append(
            IndexComponentOut(
                key=spec.key,
                metric_key=spec.metric,
                pillar=spec.pillar.value,
                pillar_pl=PILLAR_NAMES_PL[spec.pillar],
                name_pl=spec.name_pl,
                explain_pl=spec.explain_pl,
                unit_pl=spec.unit_pl,
                weight=spec.weight,
                value=got.value if got else None,
                year=got.year if got else None,
                basis=("proxy" if got.proxy else "direct") if got else None,
                measured=territory_out(hierarchy.get(got.measured_territory_id)) if got else None,
                national_rank=got.rank if got else None,
                national_of=got.of if got else None,
                score=got.score if got else None,
                points=got.points if got and g.score is not None else None,
                favourable_pl=_direction_pl(spec.metric),
            )
        )
    positions: list[IndexCohortOut] = []
    if g.rank is not None:
        positions.append(
            IndexCohortOut(
                name_pl=COHORT_PL,
                scope="national",
                rank=g.rank,
                of=g.of,
                percentile=g.percentile,
                unit_name=None,
            )
        )
    if g.region_rank is not None and g.region_id is not None:
        positions.append(
            IndexCohortOut(
                name_pl="gminy z kompletnym indeksem w tym samym województwie",
                scope="voivodeship",
                rank=g.region_rank,
                of=g.region_of,
                percentile=None,
                unit_name=hierarchy.get(g.region_id).name,
            )
        )
    years = [c.year for c in g.components]
    names = {s.key: s.name_pl for s in COMPONENTS}
    return IndexOut(
        state=g.state.value,
        reasons=list(g.reasons),
        method_version=INDEX_VERSION,
        title_pl=TITLE_PL,
        caveat_pl=CAVEAT_PL,
        score=g.score,
        weight_coverage=g.weight_coverage,
        positions=positions,
        components=components,
        missing=[names[k] for k in g.missing],
        gmina=territory_out(hierarchy.get(gmina_id)),
        oldest_year=min(years) if years else None,
        newest_year=max(years) if years else None,
        min_weight_coverage=MIN_WEIGHT_COVERAGE,
        min_cohort=MIN_COHORT,
    )


def is_gmina(hierarchy: TerritoryHierarchy, territory_id: str) -> bool:
    try:
        return hierarchy.get(territory_id).level is TerritoryLevel.gmina
    except HierarchyError:  # an unknown id is simply not a gmina
        return False


__all__ = ["CAVEAT_PL", "COHORT_PL", "TITLE_PL", "index_out", "is_gmina", "unavailable"]
