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
from deal_analyzer.shopping_budget import BasketLine, basket_total, line_total
from fastapi import APIRouter, Depends, Path, Query, Request, Response
from rm_contracts.catalogue import (
    CandidateOut,
    CatalogueStatus,
    OfferState,
    SelectionIn,
    SelectionQuantity,
)
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
from rm_core.catalogue import (
    CatalogueQuery,
    CatalogueUnavailableError,
    ProductProvider,
    demo_image_png,
    offer_state,
    rank_offers,
)
from rm_core.entitlements import db_now as repo_now
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


class _Money:
    """The interior's only route to money arithmetic: `deal_analyzer.shopping_budget` (invariant 4)."""

    def basket(self, lines: Sequence[repo.InteriorLine]) -> Basket:
        total = basket_total(
            [
                BasketLine(l.quantity, l.unit_price_pln, l.stale, l.needs_delivery, l.delivery_pln)
                for l in lines  # noqa: E741
            ]
        )
        return Basket(
            known_subtotal_pln=f"{total.known_subtotal_pln:.2f}",
            priced_lines=total.priced_lines,
            unpriced_lines=total.unpriced_lines,
            stale_lines=total.stale_lines,
            delivery_known_pln=f"{total.delivery_known_pln:.2f}",
            delivery_unknown_lines=total.delivery_unknown_lines,
            complete=total.complete,
        )

    def line_total(self, quantity: int, unit_price_pln: Decimal | None) -> str | None:
        value = line_total(quantity, unit_price_pln)
        return None if value is None else f"{value:.2f}"


MONEY = _Money()


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
    return await repo.project_view(db, principal, project_id, MONEY)


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    response.headers.update(NO_STORE)
    try:
        return await repo.project_view(db, principal, project_id, MONEY)
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
        return await repo.project_view(db, principal, project_id, MONEY)
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
        return await repo.project_view(db, principal, project_id, MONEY)
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
        return await repo.project_view(db, principal, project_id, MONEY)
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
    project_id: UUID, request: Request, db: SessionDep, principal: InteriorDep, response: Response
) -> ProjectOut:
    """Snapshot the brief, items and current room photo. Immutable; later edits do not change it."""
    response.headers.update(NO_STORE)
    try:
        await repo.require_project(db, principal, project_id)
        provider: ProductProvider | None = request.app.state.catalogue
        if provider is not None:
            await _refresh_all(db, principal, project_id, provider)  # re-check the exact offers first
        await repo.create_revision(db, principal, project_id)
        return await repo.project_view(db, principal, project_id, MONEY)
    except repo.InteriorNotFoundError:
        raise _not_found() from None


# ---------- catalogue and picked products (RM-449) ----------
def _provider(request: Request) -> ProductProvider:
    provider: ProductProvider | None = request.app.state.catalogue
    if provider is None:
        raise Problem(503, ProblemCode.CATALOGUE_UNAVAILABLE, "No product source is connected")
    return provider


async def _refresh_all(
    db: SessionDep, principal: Principal, project_id: UUID, provider: ProductProvider
) -> None:
    """Fetch a fresh observation of every selection this provider owns. An unreachable source stops the round:
    the stored observations stay and are honestly shown as they are (fresh, expired or unavailable)."""
    for selection_id, name, product_id, variant_id in await repo.selection_keys(db, principal, project_id):
        if name != provider.name:
            continue
        try:
            offer = await provider.fetch(product_id, variant_id)
        except CatalogueUnavailableError:
            return
        await repo.store_observation(db, principal, project_id, selection_id, offer)


@router.get("/catalogue", response_model=CatalogueStatus)
async def catalogue_status(request: Request, principal: InteriorDep, response: Response) -> CatalogueStatus:
    """Whether a product source is connected, and whether it is only a demo. Cheap: no provider call."""
    del principal
    response.headers.update(NO_STORE)
    provider: ProductProvider | None = request.app.state.catalogue
    if provider is None:
        return CatalogueStatus(available=False, provider=None, source_label=None, is_demo=False)
    return CatalogueStatus(
        available=True, provider=provider.name, source_label=provider.source_label, is_demo=provider.is_demo
    )


@router.get("/projects/{project_id}/catalogue/search", response_model=list[CandidateOut])
async def search_catalogue(
    project_id: UUID,
    request: Request,
    *,
    db: SessionDep,
    principal: InteriorDep,
    response: Response,
    q: Annotated[str, Query(max_length=120)] = "",
    category: Annotated[str | None, Query(max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")] = None,
    max_price_pln: Annotated[Decimal | None, Query(ge=0, le=10_000_000, decimal_places=2)] = None,
    limit: Annotated[int, Query(ge=1, le=24)] = 12,
) -> list[CandidateOut]:
    """Real offers from the connected source, hard-filtered (stock, freshness, budget, text) and ordered
    deterministically. Nothing is estimated; an unknown price or delivery is flagged, not guessed."""
    response.headers.update(NO_STORE)
    try:
        await repo.require_project(db, principal, project_id)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    provider = _provider(request)
    query = CatalogueQuery(text=q, category=category, max_price_pln=max_price_pln, limit=limit)
    try:
        offers = await provider.search(query)
    except CatalogueUnavailableError:
        raise Problem(503, ProblemCode.CATALOGUE_UNAVAILABLE, "The product source did not answer") from None
    now = await repo_now(db)
    return [
        CandidateOut(offer=repo.offer_out(r.offer, offer_state(r.offer, now)), flags=r.flags)
        for r in rank_offers(offers, query, now)
    ]


@router.post("/projects/{project_id}/selections", response_model=ProjectOut, status_code=201)
async def select_product(
    project_id: UUID,
    body: SelectionIn,
    *,
    request: Request,
    db: SessionDep,
    principal: InteriorDep,
    response: Response,
) -> ProjectOut:
    """Pick an exact variant. The server fetches the offer from the source itself and stores that observation;
    the client's idea of the price is never accepted."""
    response.headers.update(NO_STORE)
    try:
        await repo.require_project(db, principal, project_id)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    provider = _provider(request)
    if body.provider != provider.name:
        raise Problem(409, ProblemCode.OFFER_UNAVAILABLE, "That product source is not connected")
    try:
        offer = await provider.fetch(body.product_id, body.variant_id)
    except CatalogueUnavailableError:
        raise Problem(503, ProblemCode.CATALOGUE_UNAVAILABLE, "The product source did not answer") from None
    if offer is None or offer_state(offer, await repo_now(db)) is not OfferState.fresh:
        raise Problem(409, ProblemCode.OFFER_UNAVAILABLE, "This variant cannot be bought now")
    try:
        await repo.add_selection(db, principal, project_id, offer, body.quantity)
        return await repo.project_view(db, principal, project_id, MONEY)
    except repo.InteriorLimitError as exc:
        raise _limit(exc) from None


@router.put("/projects/{project_id}/selections/{selection_id}", response_model=ProjectOut)
async def set_selection_quantity(
    project_id: UUID,
    selection_id: UUID,
    *,
    body: SelectionQuantity,
    db: SessionDep,
    principal: InteriorDep,
    response: Response,
) -> ProjectOut:
    response.headers.update(NO_STORE)
    try:
        await repo.set_selection_quantity(db, principal, project_id, selection_id, body.quantity)
        return await repo.project_view(db, principal, project_id, MONEY)
    except repo.InteriorNotFoundError:
        raise _not_found() from None


@router.delete("/projects/{project_id}/selections/{selection_id}", status_code=204)
async def delete_selection(
    project_id: UUID, selection_id: UUID, db: SessionDep, principal: InteriorDep
) -> Response:
    try:
        await repo.delete_selection(db, principal, project_id, selection_id)
    except repo.InteriorNotFoundError:
        raise _not_found() from None
    return Response(status_code=204)


@router.post("/projects/{project_id}/selections/{selection_id}/refresh", response_model=ProjectOut)
async def refresh_selection(
    project_id: UUID,
    selection_id: UUID,
    *,
    request: Request,
    db: SessionDep,
    principal: InteriorDep,
    response: Response,
) -> ProjectOut:
    """Check the exact variant again at the source and keep the new observation (or mark it unavailable)."""
    response.headers.update(NO_STORE)
    try:
        keys = {k[0]: k for k in await repo.selection_keys(db, principal, project_id)}
        if selection_id not in keys:
            raise _not_found()
        _, name, product_id, variant_id = keys[selection_id]
        provider = _provider(request)
        if name != provider.name:
            raise Problem(409, ProblemCode.OFFER_UNAVAILABLE, "That product source is not connected")
        try:
            offer = await provider.fetch(product_id, variant_id)
        except CatalogueUnavailableError:
            raise Problem(
                503, ProblemCode.CATALOGUE_UNAVAILABLE, "The product source did not answer"
            ) from None
        await repo.store_observation(db, principal, project_id, selection_id, offer)
        return await repo.project_view(db, principal, project_id, MONEY)
    except repo.InteriorNotFoundError:
        raise _not_found() from None


@router.get(
    "/catalogue/demo-image/{product_id}/{variant_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def demo_product_image(
    product_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9._:-]{1,64}$")],
    variant_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9._:-]{1,64}$")],
    request: Request,
    principal: InteriorDep,
) -> Response:
    """A generated placeholder picture for the demo source only: not a product photo and labelled as such."""
    del principal
    provider: ProductProvider | None = request.app.state.catalogue
    if provider is None or not provider.is_demo:
        raise Problem.not_found("Image")
    return Response(
        demo_image_png(product_id, variant_id),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
