"""Fake Otodom corpus search that behaves like the live contract verified on 2026-10-20 (RM-411, L-050).

Hand-made data only (no seller fields). Modelled behaviour, each observed live with small probes:
- `daysSinceCreated=N` keeps the adverts created in the last N x 24 hours, measured at `now` (rolling,
  no upper bound);
- `by=LATEST` sorts by creation time, `direction=ASC|DESC`;
- pages hold `page_size` adverts (36 live); `totalPages` is 0 for an empty search;
- every non-empty page repeats a sponsored `hpr/` tile with a synthetic id and a 1999 date;
- a page past the end answers the last page again (so `currentPage` differs from the request).
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any

from rm_core.deadline import Deadline
from rm_worker.clients.otodom import Priority, SearchOptions, UpstreamBlocked

SPONSORED: dict[str, Any] = {
    "id": 9_000_062_237,
    "estate": "FLAT",
    "transaction": "RENT",
    "href": "hpr/[lang]/ad/sponsored-ID9P5lk9",
    "createdAtFirst": "1999-02-29 00:00:01",
    "totalPrice": {"value": 2600, "currency": "PLN"},
    "areaInSquareMeters": 36,
}


def tile(
    offer_id: int, created: datetime, rent: object = 2500, area: object = 40, **over: Any
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": offer_id,
        "estate": "FLAT",
        "transaction": "RENT",
        "hidePrice": False,
        "href": f"[lang]/ad/test-{offer_id}",
        "areaInSquareMeters": area,
        "totalPrice": {"value": rent, "currency": "PLN"},
        "rentPrice": {"value": 650, "currency": "PLN"},  # admin fee: must never be read as rent
        "roomsNumber": 2,
        "createdAtFirst": created.isoformat(),
        "pushedUpAt": "2099-01-01T00:00:00+00:00",  # promotion time: must never be read as publication
    }
    return base | over


@dataclass
class FakeCorpusSearch:
    tiles: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    page_size: int = 4
    now: datetime = datetime(2026, 9, 1, 1, 10, tzinfo=UTC)  # the site's clock; tests move it
    calls: list[tuple[str, int, SearchOptions, str]] = field(
        default_factory=list[tuple[str, int, SearchOptions, str]]
    )
    fail_on_call: int | None = None  # 1-based call number that raises
    retryable: bool = True
    delay_s: float = 0.0
    raw_override: dict[str, Any] | None = None
    sponsored: bool = True

    def created(self, t: dict[str, Any]) -> datetime:
        try:
            return datetime.fromisoformat(t["createdAtFirst"]).astimezone(UTC)
        except ValueError:  # the live sponsored tile has a naive 1999 date: it sorts as ancient
            return datetime(1999, 2, 28, tzinfo=UTC)

    async def fetch_corpus_search(
        self,
        location_id: str,
        page: int,
        *,
        options: SearchOptions,
        deadline: Deadline,
        priority: Priority = "batch",
    ) -> dict[str, Any]:
        self.calls.append((location_id, page, options, priority))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail_on_call == len(self.calls):
            raise UpstreamBlocked("HTTP 429", retryable=self.retryable)
        if self.raw_override is not None:
            return self.raw_override
        floor = (
            None
            if options.days_since_created is None
            else self.now - timedelta(days=options.days_since_created)
        )
        inside = sorted(
            (t for t in self.tiles if floor is None or self.created(t) >= floor),
            key=lambda t: (self.created(t), t["id"]),
            reverse=options.order == "newest",
        )
        total = ceil(len(inside) / self.page_size)
        shown = min(page, max(total, 1))  # past the end repeats the last page
        start = (shown - 1) * self.page_size
        items = inside[start : start + self.page_size]
        if items and self.sponsored:
            items = [*items, SPONSORED]
        return {
            "items": items,
            "pagination": {
                "itemsPerPage": self.page_size,
                "totalItems": len(inside),
                "totalPages": total,
                "currentPage": shown,
            },
        }
