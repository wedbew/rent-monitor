"""Territorial reference from GUS BDL unit lists: pure, no I/O (RM-48).

LEGAL[third-party-data]: identifiers and names of public administrative units from GUS BDL (RM-48).
GDPR[personal-data]: none; territorial units only (RM-48).

Facts verified against the live service on 2026-10-20 and relied on here:
- a BDL unit id has 12 digits: 2 (statistical macro-region) + 2 (voivodeship, the TERYT code) + 2
  (sub-region) + 3 (powiat, the TERYT powiat code is the last two of them) + 3 (gmina code and type): the
  TERYT code of a powiat is `id[2:4] + id[7:9]`, of a gmina `id[2:4] + id[7:9] + id[9:12]` (seven digits,
  the last is the type);
  a voivodeship id is `id[:4]` followed by eight zeros;
- the unit list holds, next to the whole gminas of types 1 (urban), 2 (rural) and 3 (urban-rural), their
  urban and rural parts (types 4 and 5), the districts of Warsaw (8) and defunct units; the data service
  answers for 380 powiats and about 3,900 level-6 units of which the whole ones are the gminas;
- the list cannot be filtered by year, so a unit counts as part of the reference when it reports a value for
  an anchor variable in the reference year (`active`); the rest is recorded, never silently dropped.
Powiat codes from 61 are cities with powiat rights, which keep both roles (`has_powiat_rights`).
"""

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from rm_contracts.location_context import TerritoryLevel, TerritoryRef

COUNTRY_ID = "000000000000"
WHOLE_GMINA_TYPES = frozenset("123")
PART_TYPES = frozenset("458")  # urban/rural part of an urban-rural gmina, district
CITY_WITH_POWIAT_RIGHTS_FROM = 61  # TERYT powiat codes 61.. are cities with powiat rights


class ReferenceError(ValueError):
    """The BDL unit lists do not form the expected hierarchy."""


@dataclass(frozen=True)
class UnitRow:
    id: str
    name: str
    level: int
    parent_id: str | None = None


@dataclass(frozen=True)
class ReferenceBuild:
    territories: tuple[TerritoryRef, ...]
    excluded: Mapping[str, tuple[str, ...]]  # why a listed unit is not in the reference -> ids

    def counts(self) -> dict[str, int]:
        out = {level.value: 0 for level in TerritoryLevel}
        for t in self.territories:
            out[t.level.value] += 1
        return out


def powiat_teryt(unit_id: str) -> str:
    return unit_id[2:4] + unit_id[7:9]


def gmina_teryt(unit_id: str) -> str:
    return unit_id[2:4] + unit_id[7:9] + unit_id[9:12]


def voivodeship_id(unit_id: str) -> str:
    return unit_id[:4] + "0" * 8


def build_reference(
    units: Mapping[int, Iterable[UnitRow]], active: Mapping[int, Collection[str]]
) -> ReferenceBuild:
    """Country, voivodeships, active powiats and active whole gminas, with TERYT codes and one-level parents.

    `units` maps a BDL level (0, 2, 5, 6) to its rows; `active` maps level 5 and 6 to the ids that report an
    anchor value in the reference year. Raises `ReferenceError` on anything that breaks the hierarchy."""
    country = [u for u in units.get(0, ()) if u.id == COUNTRY_ID]
    if len(country) != 1:
        raise ReferenceError("expected exactly one country unit")
    out: list[TerritoryRef] = [
        TerritoryRef(
            territory_id=COUNTRY_ID, teryt="", name=country[0].name.title(), level=TerritoryLevel.country
        )
    ]
    excluded: dict[str, list[str]] = {}
    wojs = {u.id: u for u in units.get(2, ())}
    if not wojs:
        raise ReferenceError("no voivodeships")
    for u in sorted(wojs.values(), key=lambda u: u.id):
        if u.id != voivodeship_id(u.id):
            raise ReferenceError(f"voivodeship id {u.id} does not follow the pattern")
        out.append(
            TerritoryRef(
                territory_id=u.id,
                teryt=u.id[2:4],
                name=u.name.title(),
                level=TerritoryLevel.wojewodztwo,
                parent_id=COUNTRY_ID,
            )
        )
    active_powiats = set(active.get(5, ()))
    powiats: dict[str, UnitRow] = {}
    for u in sorted(units.get(5, ()), key=lambda u: u.id):
        if u.id not in active_powiats:
            excluded.setdefault("powiat_without_value_in_reference_year", []).append(u.id)
            continue
        if voivodeship_id(u.id) not in wojs:
            raise ReferenceError(f"powiat {u.id} has no voivodeship")
        powiats[u.id] = u
        out.append(
            TerritoryRef(
                territory_id=u.id,
                teryt=powiat_teryt(u.id),
                name=u.name,
                level=TerritoryLevel.powiat,
                parent_id=voivodeship_id(u.id),
            )
        )
    active_gminas = set(active.get(6, ()))
    for u in sorted(units.get(6, ()), key=lambda u: u.id):
        kind = u.id[-1]
        if kind in PART_TYPES:
            excluded.setdefault("part_or_district", []).append(u.id)
            continue
        if kind not in WHOLE_GMINA_TYPES:
            raise ReferenceError(f"gmina {u.id} has an unknown type digit")
        if u.id not in active_gminas:
            excluded.setdefault("gmina_without_value_in_reference_year", []).append(u.id)
            continue
        if u.parent_id not in powiats:
            raise ReferenceError(f"gmina {u.id} has no active powiat parent {u.parent_id}")
        out.append(
            TerritoryRef(
                territory_id=u.id,
                teryt=gmina_teryt(u.id),
                name=u.name,
                level=TerritoryLevel.gmina,
                parent_id=u.parent_id,
                has_powiat_rights=int(u.id[7:9]) >= CITY_WITH_POWIAT_RIGHTS_FROM,
            )
        )
    return ReferenceBuild(tuple(out), {k: tuple(v) for k, v in excluded.items()})
