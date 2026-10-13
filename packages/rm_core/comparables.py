"""Comparable-rent store: asking rents from `otodom_rental` sidecars, cached by sidecar sha256 (RM-106).

LEGAL[third-party-data]: serves rents derived from Otodom rental listings; no seller data kept (RM-106).
Invariant 2 (asking is not deed): only `otodom_rental` sidecars own or yield rows. The write path rejects
any other kind and the read path filters on it, so deed or sale-asking sidecars cannot feed a rent estimate.
The engine (`deal_analyzer.rent.estimate_rent`) stays pure; callers map `StoredComparable` to its input type.
"""

import hashlib
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import MarketSidecar, RentComparableRow, SidecarKind

DEFAULT_CACHE_ENTRIES = 256
_KEY = tuple[str, str]  # (city_slug, digest of the sidecar sha256 values)


class SidecarNotRentalError(ValueError):
    """Only `otodom_rental` sidecars may own rent comparables (invariant 2)."""


@dataclass(frozen=True)
class StoredComparable:
    monthly_rent_pln: Decimal
    area_m2: Decimal


@dataclass(frozen=True)
class ComparableSet:
    comparables: tuple[StoredComparable, ...]
    period: date | None  # period of the sidecars these came from; None when the city has none


class ComparableCache:
    """Bounded LRU keyed by sidecar sha256: same hash, same content, so a hit skips the row read."""

    def __init__(self, max_entries: int = DEFAULT_CACHE_ENTRIES) -> None:
        self._max = max(1, max_entries)
        self._items: OrderedDict[_KEY, ComparableSet] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._items)

    def get(self, key: _KEY) -> ComparableSet | None:
        found = self._items.get(key)
        if found is None:
            self.misses += 1
            return None
        self._items.move_to_end(key)
        self.hits += 1
        return found

    def put(self, key: _KEY, comparables: Sequence[StoredComparable], period: date | None) -> ComparableSet:
        value = ComparableSet(tuple(comparables), period)
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self._max:
            self._items.popitem(last=False)
        return value


def _digest(shas: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(shas)).encode()).hexdigest()


async def replace_comparables(
    session: AsyncSession, sidecar_id: int, rows: Sequence[StoredComparable]
) -> int:
    """Replace every comparable of one rental sidecar; idempotent. Returns the number of rows stored."""
    kind = await session.scalar(
        select(MarketSidecar.kind).where(MarketSidecar.id == sidecar_id).with_for_update()
    )
    if kind != SidecarKind.otodom_rental:
        raise SidecarNotRentalError(f"sidecar {sidecar_id} is not an otodom_rental sidecar")
    await session.execute(delete(RentComparableRow).where(RentComparableRow.sidecar_id == sidecar_id))
    session.add_all(
        RentComparableRow(sidecar_id=sidecar_id, monthly_rent_pln=r.monthly_rent_pln, area_m2=r.area_m2)
        for r in rows
    )
    await session.flush()
    return len(rows)


async def load_comparables(session: AsyncSession, city_slug: str, cache: ComparableCache) -> ComparableSet:
    """Comparables of the city's newest rental period (all size buckets), through the sha256-keyed cache."""
    latest = (
        select(func.max(MarketSidecar.period))
        .where(MarketSidecar.city_slug == city_slug, MarketSidecar.kind == SidecarKind.otodom_rental)
        .scalar_subquery()
    )
    sidecars = (
        await session.execute(
            select(MarketSidecar.id, MarketSidecar.sha256, MarketSidecar.period).where(
                MarketSidecar.city_slug == city_slug,
                MarketSidecar.kind == SidecarKind.otodom_rental,
                MarketSidecar.period == latest,
            )
        )
    ).all()
    if not sidecars:
        return cache.put((city_slug, _digest(())), (), None)
    key = (city_slug, _digest([s.sha256 for s in sidecars]))
    cached = cache.get(key)
    if cached is not None:
        return cached
    found = await session.execute(
        select(RentComparableRow.monthly_rent_pln, RentComparableRow.area_m2)
        .join(MarketSidecar, MarketSidecar.id == RentComparableRow.sidecar_id)
        .where(
            RentComparableRow.sidecar_id.in_([s.id for s in sidecars]),
            MarketSidecar.kind == SidecarKind.otodom_rental,
        )
        .order_by(RentComparableRow.id)
    )
    return cache.put(key, [StoredComparable(rent, area) for rent, area in found.all()], sidecars[0].period)
