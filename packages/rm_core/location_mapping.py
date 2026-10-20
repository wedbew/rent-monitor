"""Explicit mapping of Otodom places to GUS BDL territories (RM-282): pure, no I/O.

LEGAL[third-party-data]: relates Otodom place paths to public GUS administrative units (RM-282).
GDPR[personal-data]: none; territorial identifiers only (RM-282).

Never by name alone: the voivodeship and the powiat must match first, a gmina is looked up only inside that
powiat, and a name that fits more than one whole gmina (a city and its rural gmina share names in 311
powiats) stays `ambiguous` with its candidates listed. A place below a listed gmina is `within_gmina`: the
gmina that contains it, not the place itself. Cities with powiat rights carry the slug of the city
(`Powiat m. Kraków` is `krakow`, the surrounding `Powiat krakowski` is `krakowski`), so the two are never
mixed.
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from rm_contracts.location_context import TerritoryLevel, TerritoryRef

_LETTERS = str.maketrans({"ł": "l", "Ł": "l"})
_URBAN, _RURAL = "gmina-miejska--", "gmina-wiejska--"


class MappingStatus(StrEnum):
    mapped = "mapped"
    ambiguous = "ambiguous"
    unmatched = "unmatched"


class Relation(StrEnum):
    gmina = "gmina"  # the Otodom place is the whole gmina
    within_gmina = "within_gmina"  # the place lies inside the mapped gmina


@dataclass(frozen=True)
class PlaceMapping:
    location_id: str
    status: MappingStatus
    method: str
    relation: Relation | None = None
    gmina_id: str | None = None
    powiat_id: str | None = None
    wojewodztwo_id: str | None = None
    candidates: tuple[str, ...] = ()


def slug(text: str) -> str:
    """ASCII, lower case, runs of non-alphanumerics as one hyphen (the shape of an Otodom path segment)."""
    folded = unicodedata.normalize("NFKD", text.translate(_LETTERS)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def _powiat_key(name: str) -> str:
    """`Powiat m. st. Warszawa` -> warszawa, `Powiat m. Wałbrzych od 2013` -> walbrzych, `Powiat krakowski` ->
    krakowski. A name that ends `do YYYY` is a historical unit and is left out of the reference upstream."""
    bare = re.sub(r"^Powiat\s+(m\.\s*(st\.\s*)?)?", "", name, flags=re.I)
    return slug(re.sub(r"\s+od\s+\d{4}$", "", bare))


def _gmina_key(name: str) -> str:
    """`Wałbrzych od 2013` -> walbrzych, `M.st.Warszawa od 2002` -> warszawa: the source's year qualifier
    and capital prefix are not part of the name an Otodom path carries."""
    bare = re.sub(r"\s+od\s+\d{4}$", "", name)
    return slug(re.sub(r"^m\.\s*st\.\s*", "", bare, flags=re.I))


def map_places(places: Iterable[tuple[str, str]], reference: Sequence[TerritoryRef]) -> list[PlaceMapping]:
    """`places` are `(location_id, otodom_path)`; `reference` is the stored territorial reference."""
    woj = {slug(t.name): t for t in reference if t.level is TerritoryLevel.wojewodztwo}
    powiats: dict[tuple[str, str], list[TerritoryRef]] = defaultdict(list)
    gminas: dict[tuple[str, str], list[TerritoryRef]] = defaultdict(list)
    for t in reference:
        if t.level is TerritoryLevel.powiat and t.parent_id:
            powiats[(t.parent_id, _powiat_key(t.name))].append(t)
        elif t.level is TerritoryLevel.gmina and t.parent_id:
            gminas[(t.parent_id, _gmina_key(t.name))].append(t)
    return [_map_one(lid, path, woj, powiats, gminas) for lid, path in places]


def _map_one(
    location_id: str,
    path: str,
    woj: dict[str, TerritoryRef],
    powiats: dict[tuple[str, str], list[TerritoryRef]],
    gminas: dict[tuple[str, str], list[TerritoryRef]],
) -> PlaceMapping:
    parts = path.split("/")
    if len(parts) < 3:
        return PlaceMapping(location_id, MappingStatus.unmatched, "path_too_short")
    w = woj.get(slug(parts[0]))
    if w is None:
        return PlaceMapping(location_id, MappingStatus.unmatched, "voivodeship_unknown")
    found = powiats.get((w.territory_id, slug(parts[1])), [])
    if len(found) != 1:
        method = "powiat_unknown" if not found else "powiat_ambiguous"
        return PlaceMapping(
            location_id,
            MappingStatus.unmatched,
            method,
            wojewodztwo_id=w.territory_id,
            candidates=tuple(t.territory_id for t in found),
        )
    p = found[0]
    base = {"powiat_id": p.territory_id, "wojewodztwo_id": w.territory_id}
    segment = parts[2]
    hint = None
    if segment.startswith(_URBAN):
        segment, hint = segment.removeprefix(_URBAN), "1"
    elif segment.startswith(_RURAL):
        segment, hint = segment.removeprefix(_RURAL), "2"
    candidates = gminas.get((p.territory_id, slug(segment)), [])
    method = "name_in_powiat"
    if hint is not None:
        candidates = [t for t in candidates if t.teryt[-1] == hint]
        method = "type_hint_in_powiat"
    relation = Relation.gmina if len(parts) == 3 else Relation.within_gmina
    if len(candidates) == 1:
        return PlaceMapping(
            location_id,
            MappingStatus.mapped,
            method,
            relation,
            gmina_id=candidates[0].territory_id,
            candidates=(candidates[0].territory_id,),
            **base,
        )
    status = MappingStatus.ambiguous if candidates else MappingStatus.unmatched
    return PlaceMapping(
        location_id,
        status,
        "gmina_ambiguous" if candidates else "gmina_unknown",
        None,
        candidates=tuple(t.territory_id for t in candidates),
        **base,
    )
