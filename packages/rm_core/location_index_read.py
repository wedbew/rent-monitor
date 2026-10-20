"""Read side of the experimental locality index: load the newest published slices (RM-439).

LEGAL[third-party-data]: GUS BDL statistics; terms are with counsel (B-012).
GDPR[personal-data]: none.

The index ranks every gmina of Poland against the others, so one answer needs every gmina's value of every
component. The newest published year of each indicator is read once per publication (a handful of indicators,
a few thousand rows each) and the finished index is kept in process memory under the identity of those
releases: a new BDL publication changes the key, so a stale answer cannot outlive it.
"""

from dataclasses import dataclass

from rm_core.bdl_metrics import BY_KEY
from rm_core.location_contracts import TerritoryHierarchy
from rm_core.location_index import COMPONENTS, GminaIndex, IndicatorSlice, build_index
from rm_core.location_repo import PgLocationRepo


@dataclass(frozen=True)
class IndexSnapshot:
    signature: tuple[tuple[str, int, str], ...]  # (indicator, year, release id) of every slice used
    index: dict[str, GminaIndex]
    years: dict[str, int]  # indicator key -> published year used
    scored: int  # gminas with a score and, so, in the national cohort


def indicator_keys() -> list[str]:
    keys: list[str] = []
    for c in COMPONENTS:
        for k in (c.metric, c.per_thousand_of):
            if k is not None and k not in keys:
                keys.append(k)
    return keys


async def load_index(repo: PgLocationRepo, hierarchy: TerritoryHierarchy) -> IndexSnapshot:
    slices: dict[str, IndicatorSlice] = {}
    signature: list[tuple[str, int, str]] = []
    for key in indicator_keys():
        defn = BY_KEY[key].definition
        years = await repo.published_years(defn.key, defn.version)
        if not years:
            continue
        year = years[-1]
        release = await repo.current_release(defn.key, defn.version, year)
        if release is None:
            continue
        slices[key] = IndicatorSlice.of(year, await repo.observations(defn.key, defn.version, year))
        signature.append((key, year, release.release_id))
    index = build_index(hierarchy, slices)
    return IndexSnapshot(
        tuple(signature),
        index,
        {k: s.year for k, s in slices.items()},
        sum(1 for g in index.values() if g.score is not None),
    )


async def current_signature(repo: PgLocationRepo) -> tuple[tuple[str, int, str], ...]:
    """The identity of what `load_index` would read now, without reading any observation."""
    out: list[tuple[str, int, str]] = []
    for key in indicator_keys():
        defn = BY_KEY[key].definition
        years = await repo.published_years(defn.key, defn.version)
        if not years:
            continue
        release = await repo.current_release(defn.key, defn.version, years[-1])
        if release is not None:
            out.append((key, years[-1], release.release_id))
    return tuple(out)
