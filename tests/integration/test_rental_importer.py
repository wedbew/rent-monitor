# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
"""The rental importer on real Postgres: a city imported here is found by `MarketContext` (RM-209).

Real: Postgres, the sidecar and comparable store, `MarketContext`, `estimate_rent`. Faked, by name: the search
source (hand-built result pages, no seller data) and the import queue. Offline end to end, NOT live evidence.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from deal_analyzer import extract_listing
from rm_core.comparables import ComparableCache, city_slug
from rm_core.db.models import MarketSidecar, RentComparableRow, SidecarKind
from rm_core.deadline import Deadline
from rm_worker.clients.otodom import UpstreamBlocked
from rm_worker.context import MarketContext
from rm_worker.importers.otodom_rental import ImportTooThinError, import_city_rentals
from rm_worker.listing_source import GatedSearchSource, ScrapingDisabledError
from sqlalchemy import delete, func, select
from test_audit_journey import Harness, clean_up, h, sale_ad  # noqa: F401  (fixtures)

pytestmark = [pytest.mark.integration]
CITY = "Importowo"
SLUG = city_slug(CITY)
LOC = "testowe/importowo/importowo/importowo"
OCT, NOV = date(2026, 10, 14), date(2026, 11, 3)


def offers(first_id: int, count: int, *, ppm2: int = 60, area: int = 48) -> list[dict[str, Any]]:
    return [
        {
            "id": first_id + n,
            "estate": "FLAT",
            "transaction": "RENT",
            "hidePrice": False,
            "areaInSquareMeters": area + n % 5,
            "rentPrice": {"value": (area + n % 5) * (ppm2 + n % 4), "currency": "PLN"},
            "title": "Mieszkanie",
            "agency": {"name": "Seller Name", "phone": "+48000000000"},
        }
        for n in range(count)
    ]


@dataclass
class FakeSearch:
    pages: list[list[dict[str, Any]]]
    calls: list[tuple[str, int, str]] = field(default_factory=list[tuple[str, int, str]])
    fail_on: int | None = None

    async def fetch_rental_search(
        self, location_id: str, page: int, *, deadline: Deadline, priority: str = "batch"
    ) -> dict[str, Any]:
        self.calls.append((location_id, page, priority))
        if page == self.fail_on:
            raise UpstreamBlocked("HTTP 429", retryable=False)
        items = self.pages[page - 1] if page <= len(self.pages) else []
        return {"items": items, "pagination": {"totalPages": len(self.pages)}}


@dataclass
class FakeQueue:
    requests: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    broken: bool = False

    async def request(self, city: str, location_id: str) -> None:
        if self.broken:
            raise RuntimeError("queue down")
        self.requests.append((city, location_id))


@pytest.fixture(autouse=True)
async def wipe(h: Harness) -> AsyncIterator[None]:
    async def go() -> None:
        async with h.sm() as s, s.begin():
            await s.execute(delete(MarketSidecar).where(MarketSidecar.city_slug == SLUG))

    await go()
    yield
    await go()


async def sidecars(h: Harness) -> list[MarketSidecar]:
    async with h.sm() as s:
        return list((await s.scalars(select(MarketSidecar).where(MarketSidecar.city_slug == SLUG))).all())


async def row_count(h: Harness) -> int:
    async with h.sm() as s:
        return int(
            await s.scalar(
                select(func.count())
                .select_from(RentComparableRow)
                .join(MarketSidecar, MarketSidecar.id == RentComparableRow.sidecar_id)
                .where(MarketSidecar.city_slug == SLUG)
            )
            or 0
        )


def listing() -> Any:
    ad = sale_ad()
    ad["location"]["address"]["city"] = {"name": CITY}
    ad["location"]["reverseGeocoding"] = {
        "locations": [{"locationLevel": "city_or_village", "name": CITY, "id": LOC}]
    }
    return extract_listing(ad)


async def run(h: Harness, source: FakeSearch, today: date = OCT, **kw: Any) -> Any:
    return await import_city_rentals(
        h.sm, source, city_name=CITY, location_id=LOC, deadline=Deadline.after(60), today=today, **kw
    )


async def test_imported_city_is_found_by_the_audit_context_and_the_rent_is_not_refused(h: Harness) -> None:
    source = FakeSearch([offers(1, 36), offers(100, 36), offers(200, 20)])
    result = await run(h, source)
    assert (result.rows, result.pages, result.changed) == (92, 3, True)
    assert source.calls == [(LOC, 1, "batch"), (LOC, 2, "batch"), (LOC, 3, "batch")]  # batch lane only

    (sidecar,) = await sidecars(h)
    assert sidecar.kind == SidecarKind.otodom_rental
    assert sidecar.price_basis == "rent"  # invariant 2: never asking/deed
    assert sidecar.period == date(2026, 10, 1)
    assert sidecar.source_stem == f"otodom-rental-{SLUG}-2026-10"

    ctx = MarketContext(h.sm, risk_free=Decimal("0.055"))
    rent = await ctx.rent_input(listing(), deadline=Deadline.after(5))
    assert rent.comparables == 92
    assert rent.monthly_rent_pln > 0
    assert Decimal(2500) < rent.monthly_rent_pln < Decimal(4000)  # ~48 m2 at ~61 PLN/m2


async def test_nothing_personal_or_listing_specific_is_stored(h: Harness) -> None:
    await run(h, FakeSearch([offers(1, 20)]))
    (sidecar,) = await sidecars(h)
    blob = json.dumps(sidecar.payload) + sidecar.source_stem
    for forbidden in ("Seller Name", "+48", "Mieszkanie", "agency", "phone"):
        assert forbidden not in blob
    assert set(sidecar.payload) == {"offers", "pages", "median_rent_pln", "source", "location_id"}


async def test_rerun_with_the_same_market_changes_nothing_and_a_new_market_replaces_rows(h: Harness) -> None:
    first = await run(h, FakeSearch([offers(1, 20)]))
    again = await run(h, FakeSearch([offers(500, 20)]))  # other ids, same rents and areas
    assert (first.changed, again.changed) == (True, False)
    assert len(await sidecars(h)) == 1
    assert await row_count(h) == 20

    moved = await run(h, FakeSearch([offers(1, 25, ppm2=80)]))
    assert moved.changed is True
    assert len(await sidecars(h)) == 1  # same month, same grain: replaced, not duplicated
    assert await row_count(h) == 25


async def test_duplicate_offers_across_pages_count_once(h: Harness) -> None:
    result = await run(h, FakeSearch([offers(1, 12), offers(1, 12)]))
    assert result.rows == 12


async def test_a_new_month_adds_a_sidecar_and_the_context_reads_the_newest(h: Harness) -> None:
    await run(h, FakeSearch([offers(1, 20, ppm2=50)]), today=OCT)
    await run(h, FakeSearch([offers(1, 20, ppm2=90)]), today=NOV)
    assert [s.period for s in sorted(await sidecars(h), key=lambda s: s.period)] == [
        date(2026, 10, 1),
        date(2026, 11, 1),
    ]
    rent = await MarketContext(h.sm, risk_free=None).rent_input(listing(), deadline=Deadline.after(5))
    assert rent.monthly_rent_pln > Decimal(4000)  # the November (90 PLN/m2) set, not October


async def test_a_thin_import_writes_nothing_and_keeps_the_previous_month(h: Harness) -> None:
    await run(h, FakeSearch([offers(1, 20, ppm2=50)]), today=OCT)
    with pytest.raises(ImportTooThinError):
        await run(h, FakeSearch([offers(1, 4)]), today=NOV)
    assert [s.period for s in await sidecars(h)] == [date(2026, 10, 1)]  # no half-month shadowing October


async def test_a_block_midway_writes_nothing(h: Harness) -> None:
    source = FakeSearch([offers(1, 36), offers(100, 36)], fail_on=2)
    with pytest.raises(UpstreamBlocked):
        await run(h, source)
    assert await sidecars(h) == []


async def test_page_cap_bounds_the_requests(h: Harness) -> None:
    source = FakeSearch([offers(i * 100, 36) for i in range(20)])
    result = await run(h, source, max_pages=2)
    assert (result.pages, len(source.calls)) == (2, 2)


async def test_the_kill_switch_stops_the_search_before_any_request() -> None:
    inner = FakeSearch([offers(1, 20)])
    gated = GatedSearchSource(inner, enabled=False)  # type: ignore[arg-type]
    with pytest.raises(ScrapingDisabledError):
        await gated.fetch_rental_search(LOC, 1, deadline=Deadline.after(5))
    assert inner.calls == []


# ------------------------------------------------------------------------------ demand trigger
async def test_an_audit_in_an_unknown_city_requests_one_import_and_still_gets_the_honest_refusal(
    h: Harness,
) -> None:
    queue = FakeQueue()
    ctx = MarketContext(h.sm, risk_free=None, import_queue=queue, today=lambda: OCT)
    rent = await ctx.rent_input(listing(), deadline=Deadline.after(5))
    assert queue.requests == [(CITY, LOC)]
    assert rent.monthly_rent_pln == 0  # refused, never guessed


async def test_no_request_when_the_current_month_is_already_stored(h: Harness) -> None:
    await run(h, FakeSearch([offers(1, 20)]), today=OCT)
    queue = FakeQueue()
    ctx = MarketContext(h.sm, risk_free=None, import_queue=queue, cache=ComparableCache(), today=lambda: OCT)
    await ctx.rent_input(listing(), deadline=Deadline.after(5))
    assert queue.requests == []


async def test_a_stale_month_is_served_and_a_refresh_is_requested(h: Harness) -> None:
    await run(h, FakeSearch([offers(1, 20)]), today=OCT)
    queue = FakeQueue()
    ctx = MarketContext(h.sm, risk_free=None, import_queue=queue, today=lambda: NOV)
    rent = await ctx.rent_input(listing(), deadline=Deadline.after(5))
    assert rent.comparables == 20  # October rents still answer the audit
    assert queue.requests == [(CITY, LOC)]


async def test_a_broken_queue_never_fails_the_audit(h: Harness) -> None:
    ctx = MarketContext(h.sm, risk_free=None, import_queue=FakeQueue(broken=True), today=lambda: OCT)
    rent = await ctx.rent_input(listing(), deadline=Deadline.after(5))
    assert rent.monthly_rent_pln == 0
