"""`GET /api/audits/{audit_id}/media`: the audit's media manifest (RM-376, G-01a). Metadata only.

Tenant rule: a foreign or unknown audit is 404. Reading never fetches, downloads or analyses anything.

LEGAL[images]: lists identity and digest of listing photos and plans (RM-376)
LEGAL[republication]: echoes third-party image metadata to the tenant who requested the audit (RM-376)
"""

from uuid import UUID

from fastapi import APIRouter, Response
from rm_contracts.media import MediaManifest
from rm_core.media import AuditNotFoundError, get_manifest

from rm_api.deps import PrincipalDep, SessionDep
from rm_api.problems import Problem

router = APIRouter(prefix="/api/audits", tags=["media"])


@router.get("/{audit_id}/media", response_model=MediaManifest)
async def read_media_manifest(
    audit_id: UUID, db: SessionDep, principal: PrincipalDep, response: Response
) -> MediaManifest:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return await get_manifest(db, audit_id, principal)
    except AuditNotFoundError:
        raise Problem.not_found("Audit") from None
