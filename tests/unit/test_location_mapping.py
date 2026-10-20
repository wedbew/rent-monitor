"""Otodom place -> BDL territory mapping: explicit, hierarchical, honest about ambiguity (RM-282).

Hand-built reference with the real naming patterns observed on 2026-10-20 (invented ids).

LEGAL[third-party-data]: relates place paths to administrative units (RM-282).
"""

from mapping_fixtures import REF
from rm_core.location_mapping import MappingStatus as S
from rm_core.location_mapping import Relation, map_places, slug


def one(path: str):
    (m,) = map_places([("x", path)], REF)
    return m


def test_slug_folds_polish_letters_and_hyphen_runs() -> None:
    assert slug("Kujawsko-Pomorskie") == slug("kujawsko--pomorskie") == "kujawsko-pomorskie"
    assert slug("Nowy Wiśnicz") == "nowy-wisnicz"
    assert slug("Łódź") == "lodz"


def test_a_gmina_page_maps_to_the_whole_gmina() -> None:
    m = one("malopolskie/bocheński".replace("ń", "n") + "/nowy-wisnicz")
    assert (m.status, m.gmina_id, m.relation, m.powiat_id, m.wojewodztwo_id) == (
        S.mapped,
        "G3",
        Relation.gmina,
        "P1201",
        "W12",
    )


def test_a_place_below_a_gmina_is_within_it_not_the_gmina_itself() -> None:
    m = one("malopolskie/bochenski/nowy-wisnicz/klaj")
    assert (m.status, m.gmina_id, m.relation) == (S.mapped, "G3", Relation.within_gmina)


def test_city_county_and_surrounding_county_are_never_mixed() -> None:
    city = one("malopolskie/krakow/krakow/krakow")
    around = one("malopolskie/krakowski/krzeszowice")
    assert (city.powiat_id, city.gmina_id) == ("P1261", "G4")  # `Powiat m. Kraków`
    assert (around.powiat_id, around.gmina_id) == ("P1206", "G5")  # `Powiat krakowski`
    assert one("mazowieckie/warszawa/warszawa/warszawa").gmina_id == "G6"  # `Powiat m. st. Warszawa`


def test_same_name_in_one_powiat_needs_a_type_hint_or_stays_ambiguous() -> None:
    plain = one("malopolskie/bochenski/bochnia")
    assert (plain.status, plain.method) == (S.ambiguous, "gmina_ambiguous")
    assert plain.gmina_id is None
    assert set(plain.candidates) == {"G1", "G2"}  # listed, never guessed
    assert plain.powiat_id == "P1201"  # powiat context remains available
    assert one("malopolskie/bochenski/gmina-miejska--bochnia").gmina_id == "G1"
    assert one("malopolskie/bochenski/gmina-wiejska--bochnia").gmina_id == "G2"


def test_wrong_hierarchy_is_unmatched_even_when_the_gmina_name_exists_elsewhere() -> None:
    assert (
        one("mazowieckie/bochenski/nowy-wisnicz").status is S.unmatched
    )  # powiat is not in this voivodeship
    assert one("nieznane/bochenski/nowy-wisnicz").method == "voivodeship_unknown"
    assert one("malopolskie/bochenski/nieistnieje").method == "gmina_unknown"
    assert one("malopolskie/bochenski").method == "path_too_short"
    assert one("kujawsko--pomorskie/bydgoski/koronowo").gmina_id == "G7"
