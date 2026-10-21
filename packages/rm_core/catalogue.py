"""Catalogue seam for the interior architect: provider protocol, a demo source, ranking (RM-449).

`ProductProvider` is the only way offers enter the system. A real provider is a licensed merchant feed or API
(webePartners, Convertiser, Awin; none is connected yet, B-026). `DemoCatalogue` is a clearly named fake with
fixed data for tests and the real-stack E2E: it is refused in production by the settings, labelled `is_demo`
everywhere it is shown, and never described as a merchant.

Selection is bounded and grounded: hard constraints (stock, freshness, budget, text) filter first, then a
deterministic score orders what is left, and an optional reranker may only reorder candidates that the
provider actually returned (an unknown id from a model is dropped, never trusted). Treat merchant text as
untrusted data: it is displayed, never executed or followed as an instruction.

LEGAL[third-party-data]: handles merchant product data under the source's licence (RM-449)
LEGAL[images]: carries per-photo rights; this module never fetches or stores an image (RM-449)
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from rm_contracts.catalogue import (
    MAX_CANDIDATES,
    Availability,
    Dimensions,
    ImageRights,
    Offer,
    OfferState,
)

FRESH_FOR = timedelta(hours=24)  # how long an observation counts as a quote; feeds are updated periodically
Key = tuple[str, str]  # (product_id, variant_id)


class CatalogueUnavailableError(Exception):
    """The provider is not configured, did not answer in time or answered nonsense."""


@dataclass(frozen=True)
class CatalogueQuery:
    text: str = ""
    category: str | None = None
    max_price_pln: Decimal | None = None
    limit: int = MAX_CANDIDATES


class ProductProvider(Protocol):
    name: str
    source_label: str
    is_demo: bool

    async def search(self, query: CatalogueQuery) -> list[Offer]: ...

    async def fetch(self, product_id: str, variant_id: str) -> Offer | None:
        """The exact variant's current offer, or None when the source no longer lists it."""
        ...


def offer_state(offer: Offer, now: datetime) -> OfferState:
    if offer.availability is Availability.out_of_stock:
        return OfferState.unavailable
    return OfferState.expired if now >= offer.expires_at else OfferState.fresh


# ---------------------------------------------------------------------------------------- ranking
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.casefold() for t in _WORD.findall(text) if len(t) > 1}


@dataclass(frozen=True)
class Ranked:
    offer: Offer
    flags: list[str] = field(default_factory=lambda: [])


def rank_offers(offers: Sequence[Offer], query: CatalogueQuery, now: datetime) -> list[Ranked]:
    """Hard constraints first, then a deterministic order. Nothing here estimates a price or a fit."""
    wanted = _tokens(query.text)
    scored: list[tuple[int, Ranked]] = []
    for offer in offers:
        if offer_state(offer, now) is not OfferState.fresh:
            continue
        if query.category is not None and offer.category != query.category:
            continue
        if (
            query.max_price_pln is not None
            and offer.price_pln is not None
            and offer.price_pln > query.max_price_pln
        ):
            continue
        haystack = _tokens(" ".join([offer.title, offer.category, *offer.attributes.values()]))
        score = len(wanted & haystack)
        if wanted and score == 0:
            continue
        flags: list[str] = []
        if offer.price_pln is None:
            flags.append("price_unknown")
        elif query.max_price_pln is not None:
            flags.append("within_budget")
        if offer.price_conditions:
            flags.append("conditional_price")
        if not offer.delivery_known:
            flags.append("delivery_unknown")
        if offer.availability is Availability.unknown:
            flags.append("stock_unknown")
        if score:
            flags.append("matches_text")
        scored.append((score, Ranked(offer, flags)))
    scored.sort(
        key=lambda t: (
            -t[0],
            t[1].offer.price_pln is None,  # priced offers before unpriced ones
            t[1].offer.price_pln or Decimal(0),
            t[1].offer.product_id,
            t[1].offer.variant_id,
        )
    )
    return [r for _, r in scored][: min(query.limit, MAX_CANDIDATES)]


class Reranker(Protocol):
    async def rerank(self, brief_text: str, candidates: Sequence[Offer]) -> list[Key]: ...


async def apply_rerank(ranked: list[Ranked], reranker: Reranker, brief_text: str) -> list[Ranked]:
    """Reorder by a model's answer without trusting it: ids not in `ranked` are ignored, duplicates collapse,
    and anything the model left out keeps its deterministic place after the chosen ones."""
    by_key = {(r.offer.product_id, r.offer.variant_id): r for r in ranked}
    chosen = await reranker.rerank(brief_text, [r.offer for r in ranked])
    out: list[Ranked] = []
    for key in chosen:
        item = by_key.pop(key, None)
        if item is not None:
            out.append(item)
    return [*out, *by_key.values()]


# ------------------------------------------------------------------------------------ demo source
def _d(value: str) -> Decimal:
    return Decimal(value)


# (product, title, category, seller, [(variant, attributes, availability, price, delivery, conditions)])
_Variant = tuple[str, dict[str, str], Availability, str | None, str | None, str | None]
_DEMO: list[tuple[str, str, str, str, list[_Variant]]] = [
    (
        "sofa-nordic",
        "Sofa Nordic 3-osobowa",
        "sofa",
        "Demo Meble",
        [
            (
                "grey",
                {"kolor": "szary", "materiał": "tkanina"},
                Availability.in_stock,
                "2499.00",
                "149.00",
                None,
            ),
            (
                "beige",
                {"kolor": "beżowy", "materiał": "tkanina"},
                Availability.in_stock,
                "2599.00",
                None,
                None,
            ),
            (
                "green",
                {"kolor": "zielony", "materiał": "welur"},
                Availability.out_of_stock,
                "2799.00",
                "149.00",
                None,
            ),
        ],
    ),
    (
        "armchair-velvet",
        "Fotel Velvet",
        "armchair",
        "Demo Meble",
        [
            (
                "navy",
                {"kolor": "granatowy", "materiał": "welur"},
                Availability.in_stock,
                "899.00",
                "79.00",
                None,
            ),
            (
                "mustard",
                {"kolor": "musztardowy", "materiał": "welur"},
                Availability.unknown,
                "899.00",
                None,
                None,
            ),
        ],
    ),
    (
        "table-oak",
        "Stół dębowy 140x80",
        "table",
        "Demo Drewno",
        [
            ("oak-140", {"kolor": "dąb", "rozmiar": "140x80"}, Availability.in_stock, "1299.00", None, None),
            ("oak-180", {"kolor": "dąb", "rozmiar": "180x90"}, Availability.in_stock, "1599.00", None, None),
        ],
    ),
    (
        "lamp-arc",
        "Lampa podłogowa Arc",
        "lamp",
        "Demo Oświetlenie",
        [
            ("black", {"kolor": "czarny"}, Availability.in_stock, "189.00", "0.00", None),
            (
                "white",
                {"kolor": "biały"},
                Availability.in_stock,
                None,
                "0.00",
                None,
            ),  # price on request: unknown
        ],
    ),
    (
        "rug-wool",
        "Dywan wełniany 160x230",
        "rug",
        "Demo Dom",
        [
            (
                "sand",
                {"kolor": "piaskowy", "rozmiar": "160x230"},
                Availability.in_stock,
                "649.00",
                "39.00",
                "cena z kartą klubową",
            ),
        ],
    ),
    (
        "shelf-ladder",
        "Regał drabinkowy",
        "shelf",
        "Demo Drewno",
        [
            ("white", {"kolor": "biały"}, Availability.in_stock, "329.00", "49.00", None),
            ("walnut", {"kolor": "orzech"}, Availability.in_stock, "379.00", "49.00", None),
        ],
    ),
    (
        "bed-160",
        "Łóżko tapicerowane 160x200",
        "bed",
        "Demo Meble",
        [
            (
                "graphite",
                {"kolor": "grafitowy", "rozmiar": "160x200"},
                Availability.in_stock,
                "1899.00",
                "149.00",
                None,
            ),
        ],
    ),
    (
        "desk-compact",
        "Biurko kompaktowe 120",
        "desk",
        "Demo Biuro",
        [
            (
                "white",
                {"kolor": "biały", "rozmiar": "120x60"},
                Availability.in_stock,
                "459.00",
                "29.00",
                None,
            ),
            ("oak", {"kolor": "dąb", "rozmiar": "120x60"}, Availability.in_stock, "499.00", "29.00", None),
        ],
    ),
    (
        "mirror-round",
        "Lustro okrągłe 80 cm",
        "mirror",
        "Demo Dom",
        [
            ("brass", {"kolor": "mosiądz", "rozmiar": "80"}, Availability.in_stock, "259.00", "19.00", None),
        ],
    ),
    (
        "curtains-linen",
        "Zasłony lniane 2 szt.",
        "curtains",
        "Demo Dom",
        [
            (
                "natural",
                {"kolor": "naturalny", "materiał": "len"},
                Availability.in_stock,
                "219.00",
                "15.00",
                None,
            ),
        ],
    ),
]


class DemoCatalogue:
    """Deterministic fake source: clearly named, never a merchant. Tests drive it through the helpers."""

    name = "demo"
    source_label = "Demo (dane przykładowe, nie sklep)"
    is_demo = True

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._removed: set[Key] = set()
        self._availability: dict[Key, Availability] = {}
        self._price: dict[Key, str | None] = {}
        self.fail_next = False
        self.calls = 0  # searches and fetches, so a test can assert "no second call"

    # ------------------------------------------------------------------------------ test helpers
    def remove(self, product_id: str, variant_id: str) -> None:
        self._removed.add((product_id, variant_id))

    def set_availability(self, product_id: str, variant_id: str, value: Availability) -> None:
        self._availability[(product_id, variant_id)] = value

    def set_price(self, product_id: str, variant_id: str, price: str | None) -> None:
        self._price[(product_id, variant_id)] = price

    # ------------------------------------------------------------------------------ the protocol
    def _all(self) -> list[Offer]:
        now = self._clock()
        out: list[Offer] = []
        for product, title, category, seller, variants in _DEMO:
            for variant, attrs, availability, price, delivery, conditions in variants:
                key = (product, variant)
                if key in self._removed:
                    continue
                price_value = self._price.get(key, price)
                out.append(
                    Offer(
                        provider=self.name,
                        product_id=product,
                        variant_id=variant,
                        offer_id=f"{product}-{variant}",
                        seller=seller,
                        title=title,
                        product_url=f"https://demo.invalid/{product}?wariant={variant}",
                        category=category,
                        attributes=attrs,
                        dimensions=Dimensions(
                            width_cm=_d("200"),
                            depth_cm=_d("90"),
                            height_cm=_d("85"),
                            source="dane przykładowe",
                        )
                        if category == "sofa"
                        else None,
                        price_pln=_d(price_value) if price_value is not None else None,
                        price_is_gross=True if price_value is not None else None,
                        price_conditions=conditions,
                        delivery_pln=_d(delivery) if delivery is not None else None,
                        delivery_known=delivery is not None,
                        availability=self._availability.get(key, availability),
                        observed_at=now,
                        expires_at=now + FRESH_FOR,
                        image_url=f"/api/interior/catalogue/demo-image/{product}/{variant}",
                        image_rights=ImageRights(display=True, cache=True, generation_reference=True),
                        source_label=self.source_label,
                    )
                )
        return out

    async def search(self, query: CatalogueQuery) -> list[Offer]:
        self.calls += 1
        if self.fail_next:
            self.fail_next = False
            raise CatalogueUnavailableError("demo failure")
        return self._all()  # the caller ranks and bounds; a real source filters server-side

    async def fetch(self, product_id: str, variant_id: str) -> Offer | None:
        self.calls += 1
        if self.fail_next:
            self.fail_next = False
            raise CatalogueUnavailableError("demo failure")
        for offer in self._all():
            if (offer.product_id, offer.variant_id) == (product_id, variant_id):
                return offer
        return None


def demo_image_png(product_id: str, variant_id: str) -> bytes:
    """A flat-colour placeholder for the demo source: the colour comes from the ids, the caption says it is a
    demo. Never a product photograph."""
    import hashlib  # noqa: PLC0415
    import io  # noqa: PLC0415

    from PIL import Image, ImageDraw  # noqa: PLC0415

    digest = hashlib.sha256(f"{product_id}/{variant_id}".encode()).digest()
    color = (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)
    image = Image.new("RGB", (320, 240), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 200, 320, 240), fill=(255, 255, 255))
    draw.text((8, 212), f"DEMO {product_id[:24]}", fill=(30, 30, 30))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()
