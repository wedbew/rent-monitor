"""N-03 (pure part): distances and nearest points of interest."""

from decimal import Decimal as D

import pytest
from deal_analyzer.geo import Poi, PoiCategory, bounding_box, distance_m, in_poland, nearest_by_category
from hypothesis import given, settings
from hypothesis import strategies as st

WARSAW = (D("52.2297"), D("21.0122"))
KRAKOW = (D("50.0647"), D("19.9450"))
GDANSK = (D("54.3520"), D("18.6466"))


def test_known_city_distances_are_within_a_kilometre_of_the_published_figures() -> None:
    assert abs(distance_m(*WARSAW, *KRAKOW) - D(252_000)) < D(2_000)  # ~252 km great circle
    assert abs(distance_m(*WARSAW, *GDANSK) - D(284_000)) < D(3_000)  # ~284 km


def test_distance_is_zero_symmetric_and_whole_metres() -> None:
    assert distance_m(*WARSAW, *WARSAW) == 0
    assert distance_m(*WARSAW, *KRAKOW) == distance_m(*KRAKOW, *WARSAW)
    d = distance_m(*WARSAW, *KRAKOW)
    assert d == d.to_integral_value()
    assert isinstance(d, D)


def test_a_degree_of_latitude_is_about_111_kilometres() -> None:
    assert abs(distance_m(D(50), D(20), D(51), D(20)) - D(111_195)) < D(100)


def test_the_antimeridian_and_the_poles_do_not_break_the_formula() -> None:
    assert distance_m(D(0), D(179), D(0), D(-179)) == distance_m(D(0), D(0), D(0), D(2))
    assert distance_m(D(90), D(0), D(90), D(120)) == 0  # the same point: the pole
    assert distance_m(D(0), D(0), D(0), D(180)) > D(20_000_000)


@settings(max_examples=100, deadline=None)
@given(
    a=st.tuples(st.integers(-8_000, 8_000), st.integers(-17_000, 17_000)),
    b=st.tuples(st.integers(-8_000, 8_000), st.integers(-17_000, 17_000)),
    c=st.tuples(st.integers(-8_000, 8_000), st.integers(-17_000, 17_000)),
)
def test_distance_obeys_the_triangle_inequality_up_to_rounding(
    a: tuple[int, int], b: tuple[int, int], c: tuple[int, int]
) -> None:
    def pt(p: tuple[int, int]) -> tuple[D, D]:
        return D(p[0]) / 100, D(p[1]) / 100

    ab, bc, ac = distance_m(*pt(a), *pt(b)), distance_m(*pt(b), *pt(c)), distance_m(*pt(a), *pt(c))
    assert ac <= ab + bc + 2  # +2 m for rounding of the three terms
    assert ab == distance_m(*pt(b), *pt(a))


def _poi(cat: PoiCategory, dlat: str) -> Poi:
    return Poi(category=cat, latitude=D("52.2297") + D(dlat), longitude=D("21.0122"))


def test_nearest_per_category_within_the_radius() -> None:
    pois = [
        _poi(PoiCategory.TRANSIT, "0.0020"),  # ~222 m
        _poi(PoiCategory.TRANSIT, "0.0040"),
        _poi(PoiCategory.SCHOOL, "0.0100"),  # ~1.1 km
        _poi(PoiCategory.SHOP, "0.0500"),  # ~5.5 km: outside a 1.5 km radius
    ]
    result = {n.category: n for n in nearest_by_category(*WARSAW, pois, 1_500)}
    assert result[PoiCategory.TRANSIT].count_within_radius == 2
    transit = result[PoiCategory.TRANSIT].distance_m
    assert transit is not None
    assert D(200) < transit < D(250)
    assert result[PoiCategory.SCHOOL].count_within_radius == 1
    assert result[PoiCategory.SHOP].distance_m is None
    assert result[PoiCategory.PARK].distance_m is None  # reported even when nothing was found
    assert set(result) == set(PoiCategory)


def test_poi_lists_are_capped_and_order_does_not_matter() -> None:
    many = [_poi(PoiCategory.SHOP, "0.0010")] * 600
    assert (
        next(
            n for n in nearest_by_category(*WARSAW, many, 1_000) if n.category is PoiCategory.SHOP
        ).count_within_radius
        == 500
    )
    a = [_poi(PoiCategory.PARK, "0.0030"), _poi(PoiCategory.PARK, "0.0010")]
    assert nearest_by_category(*WARSAW, a, 1_000) == nearest_by_category(*WARSAW, list(reversed(a)), 1_000)


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [("52.2", "21.0", True), ("40.7", "-74.0", False), ("55.1", "20", False), ("49.0", "14.0", True)],
)
def test_poland_bounding_box(lat: str, lon: str, expected: bool) -> None:
    assert in_poland(D(lat), D(lon)) is expected


def test_bounding_box() -> None:
    assert bounding_box([]) is None
    assert bounding_box([WARSAW, KRAKOW, GDANSK]) == (D("50.0647"), D("18.6466"), D("54.3520"), D("21.0122"))
