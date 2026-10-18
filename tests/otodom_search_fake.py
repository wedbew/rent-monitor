"""Fake Otodom corpus search: a hand-built set of adverts filtered by created-date bounds and paginated.

Hand-made data only (no seller fields). Bounds are treated as inclusive on both ends, an assumption that the
live site has not confirmed (L-050); the importer must not depend on it beyond idempotent inserts.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from typing import Any

from rm_core.deadline import Deadline
from rm_worker.clients.otodom import Priority, SearchOptions, UpstreamBlocked


def tile(
    offer_id: int, created: datetime, rent: object = 2500, area: object = 40, **over: Any
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": offer_id,
        "estate": "FLAT",
        "transaction": "RENT",
        "hidePrice": False,
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
    calls: list[tuple[str, int, SearchOptions, str]] = field(
        default_factory=list[tuple[str, int, SearchOptions, str]]
    )
    fail_on_call: int | None = None  # 1-based call number that raises
    retryable: bool = True
    delay_s: float = 0.0
    raw_override: dict[str, Any] | None = None

    def created(self, t: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(t.get("_filter_at") or t["createdAtFirst"])  # `_filter_at`: test-only

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
        inside = sorted(
            (
                t
                for t in self.tiles
                if (options.created_from is None or self.created(t) >= options.created_from)
                and (options.created_to is None or self.created(t) <= options.created_to)
            ),
            key=lambda t: t.get("id", 0),
        )
        total = max(1, ceil(len(inside) / self.page_size))
        start = (page - 1) * self.page_size
        return {"items": inside[start : start + self.page_size], "pagination": {"totalPages": total}}
