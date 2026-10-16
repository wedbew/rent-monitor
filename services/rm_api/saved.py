"""`/api/saved`: save or unsave audited listings and keep a note (blueprint §2 Route map).

Tenant rule (agents.md section 4): a listing can be saved only if the caller has audited it. Anything else
is a 404, so
saving cannot be used to discover which listings other users have analysed. GDPR[personal-data]: `note` is
free text.
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response
from rm_contracts.me import OtodomId, SavedOut, SavedPut
from rm_contracts.problems import ProblemCode
from rm_core.db.models import Audit, SavedListing
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from rm_api.deps import PrincipalDep, SessionDep
from rm_api.problems import Problem

router = APIRouter(prefix="/api/saved", tags=["saved"])
MAX_SAVED = 500  # per user: a bound on the table and on the list response


def _out(row: SavedListing) -> SavedOut:
    return SavedOut(
        otodom_id=row.otodom_id, note=row.note, latest_audit_id=row.latest_audit_id, created_at=row.created_at
    )


@router.get("", response_model=list[SavedOut])
async def list_saved(
    db: SessionDep, principal: PrincipalDep, limit: Annotated[int, Query(ge=1, le=MAX_SAVED)] = 100
) -> list[SavedOut]:
    """Newest first. `limit` may reach the per-account cap, so `limit=500` returns every saved listing."""
    rows = (
        await db.scalars(
            select(SavedListing)
            .where(SavedListing.user_id == principal.user_id)
            .order_by(SavedListing.created_at.desc(), SavedListing.otodom_id)
            .limit(limit)
        )
    ).all()
    return [_out(r) for r in rows]


@router.put("/{otodom_id}", response_model=SavedOut)
async def save_listing(
    otodom_id: Annotated[OtodomId, Path()], body: SavedPut, db: SessionDep, principal: PrincipalDep
) -> SavedOut:
    latest_audit = await db.scalar(
        select(Audit.id)
        .where(Audit.user_id == principal.user_id, Audit.otodom_id == otodom_id)
        .order_by(Audit.created_at.desc())
        .limit(1)
    )
    if latest_audit is None:
        raise Problem.not_found("Listing")  # never audited by this user: indistinguishable from unknown
    already = await db.scalar(
        select(SavedListing.otodom_id).where(
            SavedListing.user_id == principal.user_id, SavedListing.otodom_id == otodom_id
        )
    )
    if already is None:
        saved = await db.scalar(
            select(func.count()).select_from(SavedListing).where(SavedListing.user_id == principal.user_id)
        )
        if (saved or 0) >= MAX_SAVED:  # a soft bound: two simultaneous saves may overshoot by one
            raise Problem(409, ProblemCode.SAVED_LIMIT_REACHED, f"At most {MAX_SAVED} saved listings")
    stmt = insert(SavedListing).values(
        user_id=principal.user_id, otodom_id=otodom_id, note=body.note, latest_audit_id=latest_audit
    )
    # A body without a `note` key keeps the stored note; an explicit null clears it (RM-347).
    update: dict[str, object] = {"latest_audit_id": stmt.excluded.latest_audit_id}
    if "note" in body.model_fields_set:
        update["note"] = stmt.excluded.note
    stmt = stmt.on_conflict_do_update(
        index_elements=[SavedListing.user_id, SavedListing.otodom_id], set_=update
    ).returning(SavedListing)
    row = (await db.execute(stmt)).scalar_one()
    return _out(row)


@router.delete("/{otodom_id}", status_code=204)
async def unsave_listing(
    otodom_id: Annotated[OtodomId, Path()], db: SessionDep, principal: PrincipalDep
) -> Response:
    """Idempotent: unsaving something that is not saved is still 204."""
    await db.execute(
        delete(SavedListing).where(
            SavedListing.user_id == principal.user_id, SavedListing.otodom_id == otodom_id
        )
    )
    return Response(status_code=204)
