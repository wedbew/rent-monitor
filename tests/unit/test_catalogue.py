"""Catalogue seam: offer contract, freshness states, hard-constraint ranking, grounded reranking (RM-449)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from rm_contracts.catalogue import Availability, Offer, OfferState, SelectionIn
from rm_core.catalogue import (
    CatalogueQuery,
    CatalogueUnavailableError,
    DemoCatalogue,
    Ranked,
    apply_rerank,
    demo_image_png,
    offer_state,
    rank_offers,
)
from rm_core.settings import Settings

T0 = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def demo(at: datetime = T0) -> DemoCatalogue:
    return DemoCatalogue(clock=lambda: at)


async def offers(source: DemoCatalogue | None = None) -> list[Offer]:
    return await (source or demo()).search(CatalogueQuery())


async def test_demo_offers_are_exact_variants_with_provenance_and_freshness() -> None:
    all_offers = await offers()
    assert len({(o.product_id, o.variant_id) for o in all_offers}) == len(all_offers)
    sofa = next(o for o in all_offers if (o.product_id, o.variant_id) == ("sofa-nordic", "grey"))
    assert (sofa.price_pln, sofa.price_is_gross, sofa.delivery_pln, sofa.delivery_known) == (
        Decimal("2499.00"),
        True,
        Decimal("149.00"),
        True,
    )
    assert sofa.attributes == {"kolor": "szary", "materiał": "tkanina"}
    assert (sofa.observed_at, sofa.expires_at - sofa.observed_at) == (T0, timedelta(hours=24))
    assert sofa.product_url.startswith("https://demo.invalid/")
    assert "nie sklep" in sofa.source_label  # a demo says so
    unknown_price = next(o for o in all_offers if (o.product_id, o.variant_id) == ("lamp-arc", "white"))
    assert unknown_price.price_pln is None
    unknown_delivery = next(o for o in all_offers if o.product_id == "table-oak")
    assert (unknown_delivery.delivery_pln, unknown_delivery.delivery_known) == (None, False)


def test_offer_state_follows_stock_and_the_clock() -> None:
    base = next(iter(_sync(offers())))
    assert offer_state(base, T0) is OfferState.fresh
    assert offer_state(base, base.expires_at) is OfferState.expired
    gone = base.model_copy(update={"availability": Availability.out_of_stock})
    assert offer_state(gone, T0) is OfferState.unavailable
    unknown = base.model_copy(update={"availability": Availability.unknown})
    assert offer_state(unknown, T0) is OfferState.fresh  # unknown stock is flagged, not hidden


def _sync(coro: object) -> list[Offer]:
    import asyncio  # noqa: PLC0415

    return asyncio.run(coro)  # pyright: ignore[reportArgumentType]


async def test_ranking_applies_hard_constraints_before_ordering() -> None:
    all_offers = await offers()
    ranked = rank_offers(all_offers, CatalogueQuery(text="sofa"), T0)
    keys = [(r.offer.product_id, r.offer.variant_id) for r in ranked]
    assert keys == [
        ("sofa-nordic", "grey"),
        ("sofa-nordic", "beige"),
    ]  # the out-of-stock green one is excluded
    assert all("matches_text" in r.flags for r in ranked)

    cheap = rank_offers(all_offers, CatalogueQuery(max_price_pln=Decimal("300")), T0)
    assert cheap
    assert all(r.offer.price_pln is None or r.offer.price_pln <= 300 for r in cheap)
    assert any(r.offer.price_pln is None and "price_unknown" in r.flags for r in cheap)  # kept, flagged
    assert [r.offer.price_pln is None for r in cheap] == sorted(r.offer.price_pln is None for r in cheap)

    assert {r.offer.category for r in rank_offers(all_offers, CatalogueQuery(category="lamp"), T0)} == {
        "lamp"
    }
    assert rank_offers(all_offers, CatalogueQuery(text="nonexistent-thing"), T0) == []
    assert rank_offers(all_offers, CatalogueQuery(text="sofa"), T0 + timedelta(days=2)) == []  # all expired


async def test_flags_say_what_is_unknown_or_conditional() -> None:
    ranked = {
        (r.offer.product_id, r.offer.variant_id): r.flags
        for r in rank_offers(await offers(), CatalogueQuery(), T0)
    }
    assert "conditional_price" in ranked[("rug-wool", "sand")]
    assert "delivery_unknown" in ranked[("table-oak", "oak-140")]
    assert "stock_unknown" in ranked[("armchair-velvet", "mustard")]
    assert "delivery_unknown" not in ranked[("lamp-arc", "black")]  # known free delivery is a fact


async def test_ranking_is_deterministic_and_bounded() -> None:
    a = rank_offers(await offers(), CatalogueQuery(limit=5), T0)
    b = rank_offers(list(reversed(await offers())), CatalogueQuery(limit=5), T0)
    assert [r.offer for r in a] == [r.offer for r in b]
    assert len(a) == 5
    assert len(rank_offers(await offers(), CatalogueQuery(limit=999), T0)) <= 24


class _Model:
    def __init__(self, answer: list[tuple[str, str]]) -> None:
        self.answer = answer

    async def rerank(self, brief_text: str, candidates: object) -> list[tuple[str, str]]:
        return self.answer


async def test_a_reranker_cannot_introduce_or_duplicate_candidates() -> None:
    ranked = rank_offers(await offers(), CatalogueQuery(category="shelf"), T0)
    assert [r.offer.variant_id for r in ranked] == ["white", "walnut"]
    hallucinated = _Model([("shelf-ladder", "walnut"), ("invented-sku", "x"), ("shelf-ladder", "walnut")])
    out = await apply_rerank(ranked, hallucinated, "reading nook")
    assert [(r.offer.product_id, r.offer.variant_id) for r in out] == [
        ("shelf-ladder", "walnut"),
        ("shelf-ladder", "white"),  # left out by the model: keeps its place after the chosen ones
    ]
    assert all(isinstance(r, Ranked) for r in out)
    assert [r.offer for r in await apply_rerank(ranked, _Model([]), "x")] == [r.offer for r in ranked]


async def test_demo_helpers_change_what_the_source_says() -> None:
    source = demo()
    source.set_availability("sofa-nordic", "grey", Availability.out_of_stock)
    source.set_price("lamp-arc", "black", "199.00")
    source.remove("mirror-round", "brass")
    assert (await source.fetch("sofa-nordic", "grey")) is not None
    sofa = await source.fetch("sofa-nordic", "grey")
    assert sofa is not None
    assert sofa.availability is Availability.out_of_stock
    lamp = await source.fetch("lamp-arc", "black")
    assert lamp is not None
    assert lamp.price_pln == Decimal("199.00")
    assert await source.fetch("mirror-round", "brass") is None
    assert await source.fetch("no-such", "variant") is None
    source.fail_next = True
    with pytest.raises(CatalogueUnavailableError):
        await source.search(CatalogueQuery())
    assert await source.search(CatalogueQuery())  # one-shot failure
    assert source.calls == 7


def test_offer_contract_rejects_unsafe_or_malformed_data() -> None:
    good = _sync(offers())[0].model_dump()
    for bad in (
        {"product_url": "javascript:alert(1)"},
        {"product_url": "https://x.pl/a b"},
        {"price_pln": Decimal("-1")},
        {"price_pln": Decimal("1.005")},
        {"product_id": "has space"},
        {"title": ""},
        {"unknown_field": 1},
    ):
        with pytest.raises(ValidationError):
            Offer.model_validate({**good, **bad})
    with pytest.raises(ValidationError):  # the client never supplies a price
        SelectionIn.model_validate(
            {"provider": "demo", "product_id": "a", "variant_id": "b", "price_pln": "1"}
        )


def test_the_demo_source_is_refused_in_production() -> None:
    assert Settings(_env_file=None, catalogue_provider="demo", app_env="test")  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValidationError):
        Settings(_env_file=None, catalogue_provider="demo", app_env="production")  # pyright: ignore[reportCallIssue]
    assert Settings(_env_file=None).catalogue_provider == "none"  # pyright: ignore[reportCallIssue]


def test_the_demo_image_is_deterministic_and_a_real_png() -> None:
    a, b = demo_image_png("sofa-nordic", "grey"), demo_image_png("sofa-nordic", "grey")
    assert a == b
    assert a != demo_image_png("sofa-nordic", "beige")
    assert a.startswith(b"\x89PNG")
