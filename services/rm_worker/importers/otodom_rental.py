"""Rental-comparables importer: Otodom flat-for-rent search results -> one `otodom_rental` sidecar per
city and month, with one `rent_comparable` row per usable offer (RM-209; written from the requirement).

LEGAL[scraping]: fetches Otodom search pages with browser TLS impersonation through the shared 1 req/s host
slot and circuit breaker, at `batch` priority so it yields to audits; ToS and EU database-right exposure are
with counsel. `LEGAL_SCRAPING_ENABLED=false` stops it without a deploy.
LEGAL[third-party-data]: only a rent and an area per offer are kept; the sidecar payload holds aggregates.
No listing id, title, seller, agency, phone or photo is stored (GDPR: nothing personal reaches the database).
Invariant 2 (asking is not deed): rows belong to `otodom_rental` sidecars (price_basis 'rent') only.
Safety: a thin or failed import never replaces data, so a city keeps its last good month.
"""

import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast

import structlog
from deal_analyzer.rent import PPM2_RANGE
from rm_core.comparables import StoredComparable, city_slug, replace_comparables
from rm_core.db.models import MarketSidecar, SidecarKind
from rm_core.deadline import Deadline
from rm_core.legal import LegalTag, tag_names
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.otodom import Priority

log = structlog.get_logger(__name__)
MAX_PAGES = 5  # 36 offers a page: at most ~180 offers and 5 requests per city per month
MIN_ROWS = 10  # below this a city is not replaced (the engine itself refuses under 3, lowers trust under 10)
RENT_RANGE = (
    Decimal(300),
    Decimal(60_000),
)  # PLN a month; plausibility bounds for a flat, not business rules
AREA_RANGE = (Decimal(8), Decimal(400))
MAX_ITEMS_PER_PAGE = 100


class SearchSource(Protocol):
    async def fetch_rental_search(
        self, location_id: str, page: int, *, deadline: Deadline, priority: Priority = "batch"
    ) -> dict[str, Any]: ...


class ImportTooThinError(RuntimeError):
    """Not enough usable offers; nothing was written and the previous month stays in use."""


@dataclass(frozen=True)
class ImportResult:
    city_slug: str
    period: date
    pages: int
    rows: int
    changed: bool


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _obj(value: object) -> dict[str, Any] | None:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def parse_offers(search_ads: dict[str, Any]) -> tuple[list[tuple[int, StoredComparable]], int]:
    """Usable (offer id, rent, area) triples of one results page, and the reported number of pages.

    Anything that is not a flat for rent in PLN with a visible price and a plausible rent and area is dropped
    (developments, hidden prices, foreign currency, per-m2 only entries). Third-party JSON is untrusted.
    """
    raw_items: object = search_ads.get("items")
    items: list[object] = (
        cast("list[object]", raw_items)[:MAX_ITEMS_PER_PAGE] if isinstance(raw_items, list) else []
    )
    total_pages = (_obj(search_ads.get("pagination")) or {}).get("totalPages")
    pages = total_pages if isinstance(total_pages, int) and not isinstance(total_pages, bool) else 1
    found: list[tuple[int, StoredComparable]] = []
    for raw in items:
        item = _obj(raw)
        if item is None:
            continue
        if item.get("estate") != "FLAT" or item.get("transaction") != "RENT" or item.get("hidePrice"):
            continue
        offer_id, price = item.get("id"), _obj(item.get("rentPrice"))
        if isinstance(offer_id, bool) or not isinstance(offer_id, int) or price is None:
            continue
        if price.get("currency") != "PLN":
            continue
        rent, area = _decimal(price.get("value")), _decimal(item.get("areaInSquareMeters"))
        if rent is None or area is None:
            continue
        if not (RENT_RANGE[0] <= rent <= RENT_RANGE[1] and AREA_RANGE[0] <= area <= AREA_RANGE[1]):
            continue
        if not PPM2_RANGE[0] <= rent / area <= PPM2_RANGE[1]:
            continue
        found.append((offer_id, StoredComparable(monthly_rent_pln=rent, area_m2=area)))
    return found, max(1, min(pages, 1000))


def _digest(rows: list[StoredComparable]) -> str:
    canonical = json.dumps(sorted((str(r.monthly_rent_pln), str(r.area_m2)) for r in rows))
    return hashlib.sha256(canonical.encode()).hexdigest()


def month_start(today: date) -> date:
    return date(today.year, today.month, 1)


async def import_city_rentals(
    sessionmaker: async_sessionmaker[AsyncSession],
    source: SearchSource,
    *,
    city_name: str,
    location_id: str,
    deadline: Deadline,
    today: date | None = None,
    max_pages: int = MAX_PAGES,
    min_rows: int = MIN_ROWS,
) -> ImportResult:
    slug = city_slug(city_name)
    if not slug:
        raise ValueError("city name has no usable slug")
    period = month_start(today or datetime.now(UTC).date())
    bound = log.bind(city=slug, legal_tags=tag_names(LegalTag.scraping, LegalTag.third_party_data))
    seen: set[int] = set()
    rows: list[StoredComparable] = []
    pages_fetched, total_pages = 0, 1
    page = 1
    while page <= min(total_pages, max_pages):
        search_ads = await source.fetch_rental_search(location_id, page, deadline=deadline, priority="batch")
        offers, total_pages = parse_offers(search_ads)
        pages_fetched += 1
        fresh = [(i, c) for i, c in offers if i not in seen]
        seen.update(i for i, _ in fresh)
        rows.extend(c for _, c in fresh)
        if not offers:
            break
        page += 1
    if len(rows) < min_rows:
        bound.warning("rental_import_thin", rows=len(rows), pages=pages_fetched)
        raise ImportTooThinError(f"only {len(rows)} usable offers for {slug}")
    sha = _digest(rows)
    rents = [r.monthly_rent_pln for r in rows]
    payload: dict[str, Any] = {
        "offers": len(rows),
        "pages": pages_fetched,
        "median_rent_pln": str(statistics.median(rents)),
        "source": "otodom-search-rent-flat",
        "location_id": location_id,
    }
    async with sessionmaker() as session, session.begin():
        changed = await _store(session, slug, period, sha=sha, payload=payload, rows=rows)
    bound.info("rental_import_done", rows=len(rows), pages=pages_fetched, changed=changed)
    return ImportResult(city_slug=slug, period=period, pages=pages_fetched, rows=len(rows), changed=changed)


async def _store(
    session: AsyncSession,
    slug: str,
    period: date,
    *,
    sha: str,
    payload: dict[str, Any],
    rows: list[StoredComparable],
) -> bool:
    previous = await session.scalar(
        select(MarketSidecar.sha256).where(
            MarketSidecar.kind == SidecarKind.otodom_rental,
            MarketSidecar.city_slug == slug,
            MarketSidecar.period == period,
            MarketSidecar.size_bucket.is_(None),
        )
    )
    if previous == sha:
        return False
    stmt = insert(MarketSidecar).values(
        kind=SidecarKind.otodom_rental,
        price_basis="rent",
        city_slug=slug,
        period=period,
        size_bucket=None,
        source_stem=f"otodom-rental-{slug}-{period:%Y-%m}",
        sha256=sha,
        payload=payload,
        generated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_sidecar_grain",
        set_={
            "sha256": stmt.excluded.sha256,
            "payload": stmt.excluded.payload,
            "generated_at": stmt.excluded.generated_at,
        },
    ).returning(MarketSidecar.id)
    sidecar_id = (await session.execute(stmt)).scalar_one()
    await replace_comparables(session, sidecar_id, rows)
    return True
