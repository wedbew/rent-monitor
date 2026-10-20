"""Interior contracts: an own item needs only a name; links and prices are bounded (RM-448)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from rm_contracts.interior import Brief, CustomItemIn, ProjectCreate, RoomType


def test_a_name_alone_is_a_valid_item() -> None:
    item = CustomItemIn(name="  Stary fotel  ")
    assert (item.name, item.quantity, item.price_pln, item.url) == ("Stary fotel", 1, None, None)


def test_photo_price_and_link_are_optional_and_validated() -> None:
    item = CustomItemIn(name="Lampa", price_pln=Decimal("129.90"), url=" https://sklep.pl/lampa?x=1 ")
    assert item.url == "https://sklep.pl/lampa?x=1"
    assert CustomItemIn(name="Lampa", url="   ").url is None


@pytest.mark.parametrize(
    "bad",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 121},
        {"name": "a", "quantity": 0},
        {"name": "a", "quantity": 100},
        {"name": "a", "price_pln": Decimal("-1")},
        {"name": "a", "price_pln": Decimal("1.005")},
        {"name": "a", "price_pln": Decimal("10000001")},
        {"name": "a", "url": "javascript:alert(1)"},
        {"name": "a", "url": "ftp://x.pl/a"},
        {"name": "a", "url": "https://user:pw@sklep.pl/a"},
        {"name": "a", "url": "https://sklep.pl/a b"},
        {"name": "a", "url": "https://" + "a" * 2050 + ".pl"},
        {"name": "a", "unknown": 1},
    ],
)
def test_invalid_items_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CustomItemIn.model_validate(bad)


def test_brief_money_is_an_exact_string_and_keep_is_bounded() -> None:
    brief = Brief(room_type=RoomType.kitchen, budget_pln=Decimal("5000"))
    assert brief.model_dump(mode="json")["budget_pln"] == "5000.00"
    with pytest.raises(ValidationError):
        Brief(room_type=RoomType.kitchen, keep=["x"] * 11)
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"name": "a", "brief": {"room_type": "garage"}})
