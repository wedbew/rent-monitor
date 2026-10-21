"""`/api/interior/*`: Architekt wnetrz projects, own items, room photos and revisions (RM-456, #284).

Beta access is limited to authorised testers (`rm_core.interior_access`); everyone else gets 403
`FEATURE_NOT_IN_PLAN`. Every route is tenant-scoped through `rm_core.interior` (a foreign or unknown id
is 404, never 403). Images are uploaded as raw bytes (`application/octet-stream`), normalised and stored
by the server; they are delivered only through the authenticated content route, never by a bucket URL.
Money in responses is an exact decimal string computed by `deal_analyzer.shopping_budget`.

LEGAL[images]: accepts, stores and serves the person's room photo and item photos (RM-456)
GDPR[personal-data]: free text, links and photos written by the person (RM-456)
GDPR[processor]: Cloudflare R2 holds the stored images (RM-456)
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from deal_analyzer.shopping_budget import BasketLine, basket_total
from fastapi import APIRouter, Depends, Request, Response
from rm_contracts.interior import (
    Basket,
    CustomItemIn,
    MediaPurpose,
    MediaRef,
    ProjectCreate,
    ProjectOut,
    ProjectSummary,
)
from rm_contracts.problems import ProblemCode
from rm_core import interior as repo
from rm_core.interior_access import interior_allowed
from rm_core.interior_images import MAX_UPLOAD_BYTES, ImageRejectedError
from rm_core.legal import LegalTag, tag_names
from rm_core.object_store import ObjectStore, ObjectStoreError
from rm_core.principal import Principal

from rm_api.deps import PrincipalDep, SessionDep, SettingsDep
from rm_api.problems import Problem

router = APIRouter(prefix="/api/interior", tags=["interior"])
log = structlog.get_logger(__name__)
LEGAL_TAGS = tag_names(LegalTag.images, LegalTag.personal_data, LegalTag.processor)
NO_STORE = {"Cache-Control": "private, no-store"}
OCTET_STREAM_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


def _basket(lines: Sequence[tuple[int, Decimal | None]]) -> Basket:
    total = basket_total([BasketLine(q, p) for q, p in lines])
    return Basket(
        known_subtotal_pln=f"{total.known_subtotal_pln:.2f}",
        priced_lines=total.priced_lines,
        unpriced_lines=total.unpriced_lines,
        complete=total.complete,
    )


async def interior_principal(db: SessionDep, principal: PrincipalDep) -> Principal:
    if not await interior_allowed(db, principal):
        raise Problem(403, ProblemCode.FEATURE_NOT_IN_PLAN, "The interior architect is in a closed beta")
    return principal


InteriorDep = Annotated[Principal, Depends(interior_principal)]


def _store(request: Request) -> ObjectStore:
    store: ObjectStore | None = request.app.state.object_store
    if store is None or not request.app.state.settings.legal_images_enabled:
        raise Problem(503, ProblemCode.MEDIA_STORAGE_UNAVAILABLE, "Image storage is not available")
    return store


def _not_found() -> Problem:
    return Problem.not_found("Project")


def _limit(exc: repo.InteriorLimitError) -> Problem:
    return Problem(409, ProblemCode.INTERIOR_LIMIT_REACHED, "A limit was reached", reason=exc.code)


async def _body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise _rejected("too_large")
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > MAX_UPLOAD_BYTES:
            raise _rejected("too_large")
    return bytes(buf)


def _rejected(reason: str) -> Problem:
    return Problem(422, ProblemCode.IMAGE_REJECTED, "The image cannot be used", reason=reason)


# ---------- projects ----------
@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects(db: SessionDep, principal: InteriorDep, response: Response) -> list[ProjectSummary]:
    response.headers.update(NO_STORE)
    return await repo.list_projects(db, principal)


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    response.headers.update(NO_STORE)
    try:
        project_id = await repo.create_project(db, principal, body)
    except repo.InteriorLimitError as exc:
        raise _limit(exc) from None
    return await repo.project_view(db, principal, project_id, _basket)


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    response.headers.update(NO_STORE)
    try:
        return await repo.project_view(db, principal, project_id, _basket)
    except repo.InteriorNotFoundError:
        raise _not_found() from None


@router.put("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID, body: ProjectCreate, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    """Rename and re-brief. The 30-day lifetime is not extended by editing."""
    response.headers.update(NO_STORE)
    try:
        await repo.update_project(db, principal, project_id, name=body.name, brief=body.brief)
        return await repo.project_view(db, principal, project_id, _basket)
    except repo.InteriorNotFoundError:
        raise _not_found() from None


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, db: SessionDep, principal: InteriorDep) -> Response:
    try:
        await repo.delete_project(db, principal, project_id)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    return Response(status_code=204)


# ---------- the person's own items ----------
@router.post("/projects/{project_id}/items", response_model=ProjectOut, status_code=201)
async def add_item(
    project_id: UUID, body: CustomItemIn, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    """Only `name` is required; photo, price and link are optional. An absent price stays unknown."""
    response.headers.update(NO_STORE)
    try:
        await repo.add_item(db, principal, project_id, body)
        return await repo.project_view(db, principal, project_id, _basket)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    except repo.InteriorLimitError as exc:
        raise _limit(exc) from None


@router.put("/projects/{project_id}/items/{item_id}", response_model=ProjectOut)
async def update_item(
    project_id: UUID,
    item_id: UUID,
    *,
    body: CustomItemIn,
    db: SessionDep,
    principal: InteriorDep,
    response: Response,
) -> ProjectOut:
    response.headers.update(NO_STORE)
    try:
        await repo.update_item(db, principal, project_id, item_id, body)
        return await repo.project_view(db, principal, project_id, _basket)
    except repo.InteriorNotFoundError:
        raise _not_found() from None


@router.delete("/projects/{project_id}/items/{item_id}", status_code=204)
async def delete_item(project_id: UUID, item_id: UUID, db: SessionDep, principal: InteriorDep) -> Response:
    try:
        await repo.delete_item(db, principal, project_id, item_id)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    return Response(status_code=204)


# ---------- photos ----------
async def _upload(
    request: Request,
    *,
    settings: SettingsDep,
    principal: Principal,
    project_id: UUID,
    purpose: MediaPurpose,
    item_id: UUID | None,
) -> MediaRef:
    store = _store(request)
    raw = await _body(request)
    try:
        ref = await repo.upload_photo(
            request.app.state.sessionmaker,
            store,
            settings,
            principal,
            project_id,
            purpose=purpose,
            item_id=item_id,
            raw=raw,
        )
    except ImageRejectedError as exc:
        raise _rejected(exc.code) from None
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    except repo.InteriorLimitError as exc:
        raise _limit(exc) from None
    except ObjectStoreError as exc:
        log.warning("interior_upload_store_failed", code=exc.code, legal_tags=LEGAL_TAGS)
        raise Problem(503, ProblemCode.MEDIA_STORAGE_UNAVAILABLE, "Image storage did not answer") from None
    log.info("interior_photo_stored", purpose=purpose.value, legal_tags=LEGAL_TAGS)
    return ref


@router.post(
    "/projects/{project_id}/source",
    response_model=MediaRef,
    status_code=201,
    openapi_extra=OCTET_STREAM_BODY,
)
async def upload_source_photo(
    project_id: UUID, request: Request, settings: SettingsDep, principal: InteriorDep, response: Response
) -> MediaRef:
    """The room photo, as raw JPEG/PNG/WebP bytes (at most 10 MB). Normalised, stripped of metadata and kept
    beside any earlier photo (a project keeps up to five; none is overwritten)."""
    response.headers.update(NO_STORE)
    return await _upload(
        request,
        settings=settings,
        principal=principal,
        project_id=project_id,
        purpose=MediaPurpose.source,
        item_id=None,
    )


@router.put(
    "/projects/{project_id}/items/{item_id}/photo",
    response_model=MediaRef,
    openapi_extra=OCTET_STREAM_BODY,
)
async def upload_item_photo(
    project_id: UUID,
    item_id: UUID,
    *,
    request: Request,
    settings: SettingsDep,
    principal: InteriorDep,
    response: Response,
) -> MediaRef:
    """A photo of the person's own item; replaces the previous one (its bytes are queued for deletion)."""
    response.headers.update(NO_STORE)
    return await _upload(
        request,
        settings=settings,
        principal=principal,
        project_id=project_id,
        purpose=MediaPurpose.custom_item,
        item_id=item_id,
    )


@router.get(
    "/projects/{project_id}/media/{media_id}",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def read_photo(
    project_id: UUID, media_id: UUID, request: Request, db: SessionDep, principal: InteriorDep
) -> Response:
    """An image the caller owns, served only here (no bucket URL exists). Never cached by shared caches."""
    store = _store(request)
    try:
        content = await repo.read_media(db, store, principal, project_id, media_id)
    except repo.InteriorNotFoundError:
        raise Problem.not_found("Image") from None
    except ObjectStoreError:
        raise Problem(503, ProblemCode.MEDIA_STORAGE_UNAVAILABLE, "Image storage did not answer") from None
    return Response(
        content.data,
        media_type=content.mime,
        headers={**NO_STORE, "X-Content-Type-Options": "nosniff", "ETag": f'"{content.digest}"'},
    )


# ---------- revisions ----------
@router.post("/projects/{project_id}/revisions", response_model=ProjectOut, status_code=201)
async def create_revision(
    project_id: UUID, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    """Snapshot the brief, items and current room photo. Immutable; later edits do not change it."""
    response.headers.update(NO_STORE)
    try:
        await repo.create_revision(db, principal, project_id)
        return await repo.project_view(db, principal, project_id, _basket)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
