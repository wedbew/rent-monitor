"""Invariant 2 at the database level: asking prices are never stored as deed prices (blueprint §3, §4.6)."""

from datetime import UTC, date, datetime

import pytest
from rm_core.db.models import MarketSidecar, SidecarKind
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


def _sidecar(kind: SidecarKind, basis: str) -> MarketSidecar:
    return MarketSidecar(
        kind=kind,
        price_basis=basis,
        city_slug="leszno",
        period=date(2026, 9, 1),
        size_bucket=None,
        source_stem=f"{kind.value}-leszno-2026-09",
        sha256="0" * 64,
        payload={},
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


@pytest.mark.invariant
@pytest.mark.parametrize(
    ("kind", "bad_basis"),
    [
        (SidecarKind.bdl_deed, "asking"),
        (SidecarKind.cenogram_deed, "asking"),
        (SidecarKind.moniter_asking, "deed"),
        (SidecarKind.otodom_sale, "deed"),
        (SidecarKind.yield_ranking, "deed"),
        (SidecarKind.otodom_rental, "asking"),
        (SidecarKind.otodom_rental, "deed"),
        (SidecarKind.bdl_deed, "rent"),
    ],
)
async def test_invariant_asking_is_not_deed(session: AsyncSession, kind: SidecarKind, bad_basis: str) -> None:
    session.add(_sidecar(kind, bad_basis))
    with pytest.raises(IntegrityError, match="asking_is_not_deed"):
        await session.flush()


@pytest.mark.invariant
@pytest.mark.parametrize(
    ("kind", "good_basis"),
    [
        (SidecarKind.bdl_deed, "deed"),
        (SidecarKind.cenogram_deed, "deed"),
        (SidecarKind.moniter_asking, "asking"),
        (SidecarKind.otodom_sale, "asking"),
        (SidecarKind.yield_ranking, "asking"),
        (SidecarKind.otodom_rental, "rent"),
    ],
)
async def test_invariant_matching_price_basis_is_accepted(
    session: AsyncSession, kind: SidecarKind, good_basis: str
) -> None:
    session.add(_sidecar(kind, good_basis))
    await session.flush()
