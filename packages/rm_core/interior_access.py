"""Who may use the interior architect during the beta (RM-456, owner decision 2026-10-19).

Beta generation and storage are free only for authorised testers: an admin, an account holding the explicit
`unlimited_reports` entitlement (RM-438), or an account the `redesign` feature flag is on for (a staff
override, default off). Everyone else gets 403 `FEATURE_NOT_IN_PLAN`. Public paid use stays disabled, and the
reserved one-credit `redesign` ledger cost is never charged here.

GDPR[personal-data]: reads only the caller's user id and entitlement rows (RM-456).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.entitlements import load_entitlements
from rm_core.flags import flag_enabled
from rm_core.principal import Principal

FLAG = "redesign"


async def interior_allowed(session: AsyncSession, principal: Principal) -> bool:
    if principal.is_admin:
        return True
    ent = await load_entitlements(session, principal.user_id)
    if ent.unlimited_reports:
        return True
    return await flag_enabled(session, FLAG, user_id=principal.user_id, plan=ent.plan_code)
