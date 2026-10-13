"""Comparable-rent store (RM-106): asking rents only, cached by sidecar sha256, feeds `estimate_rent`."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from deal_analyzer.rent import RentComparable, estimate_rent
from rm_core.comparables import (
    ComparableCache,
    SidecarNotRentalError,
    StoredComparable,
    load_comparables,
    replace_comparables,
)
from rm_core.db.models import MarketSidecar, RentComparableRow, SidecarKind
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]

AREA = Decimal(50)


def sidecar(
    kind: SidecarKind = SidecarKind.otodom_rental,
    *,
    city: str = "bydgoszcz",
    period: date = date(2026, 10, 1),
    bucket: str | None = "30-50",
    sha: str = "a" * 64,
) -> MarketSidecar:
    basis = {"otodom_rental": "rent", "bdl_deed": "deed", "cenogram_deed": "deed"}.get(kind.value, "asking")
    return MarketSidecar(
        kind=kind,
        price_basis=basis,
        city_slug=city,
        period=period,
        size_bucket=bucket,
        source_stem=f"{kind.value}-{city}",
        sha256=sha,
        payload={},
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


def rows(ppm2: list[int], area: int = 50) -> list[StoredComparable]:
    return [StoredComparable(Decimal(p * area), Decimal(area)) for p in ppm2]


def as_engine(found: tuple[StoredComparable, ...]) -> list[RentComparable]:
    return [RentComparable(monthly_rent_pln=c.monthly_rent_pln, area_m2=c.area_m2) for c in found]


async def test_estimate_rent_receives_comparables_from_postgres(session: AsyncSession) -> None:
    sc = sidecar()
    session.add(sc)
    await session.flush()
    await replace_comparables(session, sc.id, rows([60, 61, 62, 63]))
    found = await load_comparables(session, "bydgoszcz", ComparableCache())
    estimate = estimate_rent(AREA, as_engine(found.comparables))
    assert not estimate.refused
    assert estimate.ppm2_median == Decimal("61.50")
    assert estimate.comparables_used == 4


async def test_a_thin_market_still_refuses_a_number(session: AsyncSession) -> None:
    sc = sidecar(city="thinville")
    session.add(sc)
    await session.flush()
    await replace_comparables(session, sc.id, rows([60, 61]))
    found = await load_comparables(session, "thinville", ComparableCache())
    estimate = estimate_rent(AREA, as_engine(found.comparables))
    assert estimate.refused
    assert "rent_refused_too_few_comparables" in estimate.warnings


@pytest.mark.invariant
@pytest.mark.parametrize("kind", [SidecarKind.bdl_deed, SidecarKind.cenogram_deed, SidecarKind.otodom_sale])
async def test_asking_or_deed_sidecars_never_own_rent_comparables(
    session: AsyncSession, kind: SidecarKind
) -> None:
    sc = sidecar(kind, city="mixcity", sha="b" * 64)
    session.add(sc)
    await session.flush()
    with pytest.raises(SidecarNotRentalError):
        await replace_comparables(session, sc.id, rows([60, 61, 62]))
    assert (await load_comparables(session, "mixcity", ComparableCache())).comparables == ()


@pytest.mark.invariant
async def test_rows_attached_to_a_non_rental_sidecar_are_never_returned(session: AsyncSession) -> None:
    """Even if a row were forced in underneath the store, the read path filters on the sidecar kind."""
    sc = sidecar(SidecarKind.bdl_deed, city="forced", sha="c" * 64)
    session.add(sc)
    await session.flush()
    await session.execute(
        text("INSERT INTO app.rent_comparable (sidecar_id, monthly_rent_pln, area_m2) VALUES (:s, 3000, 50)"),
        {"s": sc.id},
    )
    assert (await load_comparables(session, "forced", ComparableCache())).comparables == ()


async def test_cache_hits_while_the_sidecar_sha256_is_unchanged_and_misses_when_it_changes(
    session: AsyncSession,
) -> None:
    sc = sidecar(city="cacheville", sha="d" * 64)
    session.add(sc)
    await session.flush()
    await replace_comparables(session, sc.id, rows([60, 61, 62, 63]))
    cache = ComparableCache()
    first = await load_comparables(session, "cacheville", cache)
    assert (cache.hits, cache.misses) == (0, 1)
    second = await load_comparables(session, "cacheville", cache)
    assert (cache.hits, cache.misses) == (1, 1)
    assert second.comparables == first.comparables

    sc.sha256 = "e" * 64  # a refreshed sidecar with new content
    await replace_comparables(session, sc.id, rows([70, 71, 72, 73]))
    third = await load_comparables(session, "cacheville", cache)
    assert (cache.hits, cache.misses) == (1, 2)
    assert third.comparables != first.comparables


async def test_the_cache_serves_stale_rows_only_for_an_unchanged_hash(session: AsyncSession) -> None:
    """Same sha256 means same content by definition: rows are not re-read from Postgres."""
    sc = sidecar(city="samehash", sha="f" * 64)
    session.add(sc)
    await session.flush()
    await replace_comparables(session, sc.id, rows([60, 61, 62]))
    cache = ComparableCache()
    first = await load_comparables(session, "samehash", cache)
    await replace_comparables(session, sc.id, rows([90, 91, 92]))  # hash column untouched
    assert (await load_comparables(session, "samehash", cache)).comparables == first.comparables


async def test_the_latest_period_wins_and_all_size_buckets_of_it_are_combined(session: AsyncSession) -> None:
    old = sidecar(city="periods", period=date(2026, 9, 1), bucket=None, sha="1" * 64)
    small = sidecar(city="periods", bucket="0-30", sha="2" * 64)
    mid = sidecar(city="periods", bucket="30-50", sha="3" * 64)
    session.add_all([old, small, mid])
    await session.flush()
    await replace_comparables(session, old.id, rows([10, 11, 12]))
    await replace_comparables(session, small.id, rows([50, 51], area=25))
    await replace_comparables(session, mid.id, rows([60, 61]))
    found = await load_comparables(session, "periods", ComparableCache())
    assert found.period == date(2026, 10, 1)
    assert len(found.comparables) == 4
    assert all(c.monthly_rent_pln >= 1000 for c in found.comparables)  # nothing from the old period


async def test_replace_is_idempotent_and_returns_the_row_count(session: AsyncSession) -> None:
    sc = sidecar(city="idem", sha="9" * 64)
    session.add(sc)
    await session.flush()
    assert await replace_comparables(session, sc.id, rows([60, 61, 62])) == 3
    assert await replace_comparables(session, sc.id, rows([60, 61, 62])) == 3
    count = await session.scalar(select(func.count()).select_from(RentComparableRow))
    assert count == 3


async def test_the_database_rejects_non_positive_rent_and_area(session: AsyncSession) -> None:
    sc = sidecar(city="checks", sha="8" * 64)
    session.add(sc)
    await session.flush()
    for bad in (StoredComparable(Decimal(0), Decimal(40)), StoredComparable(Decimal(2000), Decimal(0))):
        async with session.begin_nested():
            with pytest.raises(IntegrityError):
                await replace_comparables(session, sc.id, [bad])


async def test_an_unknown_city_has_no_comparables_and_is_cached_as_empty(session: AsyncSession) -> None:
    cache = ComparableCache()
    found = await load_comparables(session, "nowhere", cache)
    assert found.comparables == ()
    assert found.period is None


def test_the_cache_is_bounded() -> None:
    cache = ComparableCache(max_entries=2)
    for i in range(5):
        cache.put(("c", str(i)), (), None)
    assert len(cache) == 2
