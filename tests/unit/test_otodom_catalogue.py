"""Catalogue discovery from the location sitemap: settlement rule, stable ids, reconciliation (RM-411).

The sitemap is hand-built: real shapes (observed 2026-10-20), invented places.

LEGAL[scraping]: parses a sitemap of Otodom location pages offline (RM-411).
"""

import pytest
from rm_contracts.market import LocationCatalogue
from rm_worker.importers.otodom_catalogue import (
    APPROVED_TARGET,
    build_catalogue,
    build_entries,
    display_name,
    flat_paths,
    humanize,
    location_id_for,
    parse_sitemap,
    reconcile,
    settlement_units,
)

P = "https://www.otodom.pl/pl/wyniki"
SITEMAP = "\n".join(
    f"<url><loc>{u}</loc></url>"
    for u in [
        f"{P}/wynajem/mieszkanie/slaskie",  # voivodeship
        f"{P}/wynajem/mieszkanie/slaskie/pszczynski",  # county
        f"{P}/wynajem/mieszkanie/slaskie/pszczynski/pszczyna",  # gmina with a listed city
        f"{P}/wynajem/mieszkanie/slaskie/pszczynski/pszczyna/pszczyna",  # the city
        f"{P}/wynajem/mieszkanie,2-pokoje/slaskie/pszczynski/pszczyna/pszczyna",  # same city, qualifier
        f"{P}/wynajem/mieszkanie/slaskie/pszczynski/goczalkowice-zdroj",  # gmina without a city
        f"{P}/wynajem/mieszkanie/slaskie/katowice/katowice/katowice/bogucice",  # district
        f"{P}/wynajem/mieszkanie/slaskie/katowice/katowice/katowice",  # city
        f"{P}/sprzedaz/mieszkanie/slaskie/pszczynski/suszec",  # sale-only gmina
        f"{P}/sprzedaz/dom/slaskie/pszczynski/kobior",  # a house: not a flat location
        f"{P}/wynajem/lokal/slaskie/pszczynski/miedzna",  # commercial premises: not a flat location
        "https://www.otodom.pl/pl/finanse",  # not a results URL
        f"{P}/wynajem/mieszkanie/../etc",  # malformed path
    ]
).encode()


def test_parse_strips_qualifiers_and_skips_everything_that_is_not_a_results_url() -> None:
    found = parse_sitemap(SITEMAP)
    assert ("wynajem", "mieszkanie", "slaskie/pszczynski/pszczyna/pszczyna") in found
    assert (
        len([f for f in found if f[2] == "slaskie/pszczynski/pszczyna/pszczyna"]) == 2
    )  # qualifier merged later
    assert all(".." not in path and "finanse" not in path for _, _, path in found)


def test_units_are_non_overlapping_gmina_level_places() -> None:
    by_tx = flat_paths(parse_sitemap(SITEMAP))
    units = settlement_units(by_tx["wynajem"] | by_tx["sprzedaz"])
    assert units == [
        "slaskie/katowice/katowice/katowice",  # depth 4, its gmina is not listed
        "slaskie/pszczynski/goczalkowice-zdroj",
        "slaskie/pszczynski/pszczyna",  # the gmina, not the city below it
        "slaskie/pszczynski/suszec",
    ]
    for a in units:  # no unit is an ancestor of another: an offer can belong to one location only
        assert not any(b.startswith(a + "/") for b in units)


def test_reconciliation_states_the_difference_and_never_pretends_to_match() -> None:
    by_tx = flat_paths(parse_sitemap(SITEMAP))
    units = settlement_units(by_tx["wynajem"] | by_tx["sprzedaz"])
    rec = reconcile(by_tx, units).as_dict()
    assert rec["approved_target"] == APPROVED_TARGET == 727
    assert rec["discovered"] == 4
    assert rec["difference_from_target"] == 4 - 727
    assert rec["identity_match_possible"] is False
    assert rec["places_with_only_a_flat_sale_landing_page"] == 1
    assert rec["nested_locations_excluded_by_depth"] == {"1": 1, "2": 1, "5": 1}


def test_ids_are_stable_unique_and_valid() -> None:
    a = location_id_for("slaskie/pszczynski/pszczyna/pszczyna")
    assert a == location_id_for("slaskie/pszczynski/pszczyna/pszczyna")  # stable for the same path
    assert a != location_id_for("slaskie/pszczynski/pszczyna")  # same last segment, different place
    entries = build_entries(["slaskie/pszczynski/pszczyna/pszczyna", "slaskie/pszczynski/pszczyna"])
    assert len({e.location_id for e in entries}) == 2


def test_catalogue_is_deterministic_and_names_do_not_change_its_identity() -> None:
    units = ["slaskie/pszczynski/suszec", "slaskie/pszczynski/pszczyna/pszczyna"]
    one = build_catalogue(1, "ref", build_entries(units))
    two = build_catalogue(
        1, "ref", build_entries(list(reversed(units)), {units[0]: "Suszec, pszczyński, śląskie"})
    )
    assert isinstance(one, LocationCatalogue)
    assert one.checksum == two.checksum  # id, path and flag only: a name is display data


def test_display_name_is_taken_only_from_the_location_that_was_asked_for() -> None:
    ads = {"locationsObjects": [{"id": "a/b", "fullName": "Bé, a"}]}
    assert display_name(ads, "a/b") == "Bé, a"
    assert display_name(ads, "a/c") is None
    assert display_name({"locationsObjects": []}, "a/b") is None
    assert display_name({"locationsObjects": ["x"]}, "a/b") is None
    assert humanize("slaskie/pszczynski/goczalkowice-zdroj") == "Goczalkowice Zdroj"
    assert humanize("a/b/miasto--stronie-slaskie") == "Miasto Stronie Slaskie"  # no doubled spaces


@pytest.mark.parametrize(
    "junk", [b"", b"<loc>not a url</loc>", b"<loc>https://example.com/pl/wyniki/wynajem/mieszkanie/x</loc>"]
)
def test_foreign_or_empty_input_yields_nothing(junk: bytes) -> None:
    assert parse_sitemap(junk) == []
