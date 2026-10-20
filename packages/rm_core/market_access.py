"""Who may see which Rynek places (RM-282, #43): a fixed, documented top list for the free tier.

GDPR[personal-data]: reads only the caller's user id and whether they hold a paid entitlement (RM-282).

Policy (delegated, recorded in `docs/LIMITATIONS.md` L-094): an account has **full** access when it is
an admin, holds the explicit `unlimited_reports` entitlement (RM-438), has Pro or an active pass, or has
bought a report pack that is not fully revoked. Every other verified account is **free** and sees exactly
`FREE_PLACE_LIMIT` places: those of the catalogue with the largest published sample of priced asking-rent
offers (`priced_count` of the newest `all` cohort), ties by place id. The list is recomputed from published
data, so it can change as samples grow, but at any moment it is one deterministic set; every route (list,
overview, detail, history, context, map data) filters by the same set, so a cursor, a direct id or a search
term cannot reach another place. A place outside the set answers 403 `FEATURE_NOT_IN_PLAN`."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import LotSource, ReportCreditLot
from rm_core.entitlements import load_entitlements
from rm_core.principal import Principal

FREE_PLACE_LIMIT = 20
Access = Literal["full", "free"]
FREE_RULE_PL = (
    "Darmowe konto widzi 20 miejsc z największą liczbą opublikowanych ofert z ceną; pełny rynek odblokowuje "
    "zakup pakietu raportów lub plan Pro."
)


@dataclass(frozen=True)
class MarketAccess:
    level: Access
    allowed_ids: frozenset[str] | None  # None = every place

    def allows(self, location_id: str) -> bool:
        return self.allowed_ids is None or location_id in self.allowed_ids


async def account_access(session: AsyncSession, principal: Principal) -> Access:
    if principal.is_admin:
        return "full"
    ent = await load_entitlements(session, principal.user_id)
    if ent.is_pro or ent.unlimited_reports:
        return "full"
    paid = await session.scalar(
        select(
            exists().where(
                ReportCreditLot.user_id == principal.user_id,
                ReportCreditLot.source == LotSource.purchase.value,
                ReportCreditLot.revoked < ReportCreditLot.granted,
            )
        )
    )
    return "full" if paid else "free"


def top_by_depth(depth: Sequence[tuple[str, int]], limit: int = FREE_PLACE_LIMIT) -> frozenset[str]:
    """`(location_id, priced_count)` pairs -> the ids of the `limit` deepest samples (ties by id)."""
    ranked = sorted(depth, key=lambda row: (-row[1], row[0]))
    return frozenset(location_id for location_id, _ in ranked[:limit])
