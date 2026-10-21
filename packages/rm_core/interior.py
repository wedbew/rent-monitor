"""Architekt wnetrz repository: projects, the person's own items, uploads, revisions, retention (RM-448).

Every function takes a `Principal` and filters on its user id; a foreign or unknown id is
`InteriorNotFoundError`, which the route maps to 404, never 403. Route code does not commit: the one flow that
must (`upload_photo`, which orders a database row against a bucket object) owns its short transactions.

Write order for bytes (ADR 0014): a `pending` row with its object key is committed first, then the object is
put, then the row is marked `stored`. A crash leaves a row to sweep, never an object nobody owns. Rows that
disappear (delete, retention, erasure) queue their object keys in `interior_media_tombstone` in the same
transaction, and `drain_tombstones` deletes the objects with retries.

LEGAL[images]: stores the person's room photo and item photos in the private media bucket (RM-448)
GDPR[personal-data]: free text and photos written by the person (RM-448)
GDPR[retention]: projects live 30 days from creation and are never extended; pending and failed uploads are
swept after 7 days (owner decision 2026-10-19, RM-448)
GDPR[erasure]: `erase_account_media` queues every object key before the account row is deleted (RM-448)
"""

import asyncio
import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from rm_contracts.interior import (
    MAX_ITEMS_PER_PROJECT,
    MAX_PROJECTS,
    Basket,
    Brief,
    CustomItemIn,
    CustomItemOut,
    ItemSnapshot,
    MediaPurpose,
    MediaRef,
    MediaState,
    ProjectCreate,
    ProjectOut,
    ProjectSummary,
    RevisionOut,
    RoomType,
)
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import (
    InteriorCustomItem,
    InteriorMedia,
    InteriorMediaTombstone,
    InteriorProject,
    InteriorRevision,
)
from rm_core.entitlements import db_now
from rm_core.interior_images import normalize_image
from rm_core.object_store import MediaPurpose as StorePurpose
from rm_core.object_store import ObjectStore, ObjectStoreError, media_key
from rm_core.principal import Principal
from rm_core.settings import Settings

log = structlog.get_logger()

PROJECT_LIFETIME = timedelta(days=30)  # owner decision 2026-10-19
MAX_SOURCES_PER_PROJECT = 5
TOMBSTONE_BATCH = 200
MAX_TOMBSTONE_ATTEMPTS_LOGGED = 5


# Money is added up in `deal_analyzer.shopping_budget` only (invariant 4). The caller injects that function,
# so `rm_core` never imports an engine; each line is (quantity, unit price or None for unknown).
BasketFn = Callable[[Sequence[tuple[int, Decimal | None]]], Basket]


class InteriorNotFoundError(Exception):
    """The project, item or media does not exist, is expired, or belongs to someone else."""


class InteriorLimitError(Exception):
    """A per-account or per-project bound. `code` is stable: projects, items, sources."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ---------- projects ----------
async def create_project(db: AsyncSession, principal: Principal, data: ProjectCreate) -> UUID:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": principal.user_id})
    count = await db.scalar(
        select(func.count()).select_from(InteriorProject).where(InteriorProject.user_id == principal.user_id)
    )
    if (count or 0) >= MAX_PROJECTS:
        raise InteriorLimitError("projects")
    now = await db_now(db)
    brief = data.brief
    row = InteriorProject(
        user_id=principal.user_id,
        name=data.name,
        room_type=brief.room_type.value,
        style=brief.style,
        budget_pln=brief.budget_pln,
        notes=brief.notes,
        keep={"items": list(brief.keep)},
        expires_at=now + PROJECT_LIFETIME,
    )
    db.add(row)
    await db.flush()
    return row.id


async def _project(
    db: AsyncSession, principal: Principal, project_id: UUID, *, lock: bool = False
) -> InteriorProject:
    stmt = select(InteriorProject).where(
        InteriorProject.id == project_id,
        InteriorProject.user_id == principal.user_id,
        InteriorProject.expires_at > func.clock_timestamp(),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = await db.scalar(stmt)
    if row is None:
        raise InteriorNotFoundError
    return row


async def update_project(
    db: AsyncSession, principal: Principal, project_id: UUID, *, name: str, brief: Brief
) -> None:
    row = await _project(db, principal, project_id, lock=True)
    row.name = name
    row.room_type = brief.room_type.value
    row.style = brief.style
    row.budget_pln = brief.budget_pln
    row.notes = brief.notes
    row.keep = {"items": list(brief.keep)}
    row.updated_at = await db_now(
        db
    )  # `expires_at` is deliberately untouched: editing never extends retention


async def list_projects(db: AsyncSession, principal: Principal) -> list[ProjectSummary]:
    projects = (
        await db.scalars(
            select(InteriorProject)
            .where(
                InteriorProject.user_id == principal.user_id,
                InteriorProject.expires_at > func.clock_timestamp(),
            )
            .order_by(InteriorProject.created_at.desc(), InteriorProject.id)
        )
    ).all()
    ids = [p.id for p in projects]
    sources = set(
        (
            await db.scalars(
                select(InteriorMedia.project_id).where(
                    InteriorMedia.project_id.in_(ids),
                    InteriorMedia.purpose == "source",
                    InteriorMedia.state == "stored",
                )
            )
        ).all()
    )
    revisions = dict(
        (
            await db.execute(
                select(InteriorRevision.project_id, func.count())
                .where(InteriorRevision.project_id.in_(ids))
                .group_by(InteriorRevision.project_id)
            )
        )
        .tuples()
        .all()
    )
    return [
        ProjectSummary(
            project_id=p.id,
            name=p.name,
            room_type=RoomType(p.room_type),
            has_source=p.id in sources,
            revisions=revisions.get(p.id, 0),
            created_at=p.created_at,
            expires_at=p.expires_at,
        )
        for p in projects
    ]


async def delete_project(db: AsyncSession, principal: Principal, project_id: UUID) -> None:
    """Queue the project's object keys, then delete it (rows cascade). Bytes go on the next drain."""
    await _project(db, principal, project_id, lock=True)
    await _queue_keys(db, InteriorMedia.project_id == project_id)
    await db.execute(
        delete(InteriorProject).where(
            InteriorProject.id == project_id, InteriorProject.user_id == principal.user_id
        )
    )


# ---------- the person's own items ----------
def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def _media_ref(row: InteriorMedia) -> MediaRef:
    return MediaRef(
        media_id=row.id,
        purpose=MediaPurpose(row.purpose),
        state=MediaState(row.state),
        width=row.width,
        height=row.height,
        content_digest=row.content_digest,
        expires_at=row.expires_at,
    )


def _item_out(row: InteriorCustomItem, photo: InteriorMedia | None) -> CustomItemOut:
    return CustomItemOut(
        item_id=row.id,
        name=row.name,
        quantity=row.quantity,
        price_pln=_money(row.price_pln),
        url=row.url,
        photo=_media_ref(photo) if photo is not None and photo.state == "stored" else None,
        created_at=row.created_at,
    )


async def add_item(db: AsyncSession, principal: Principal, project_id: UUID, data: CustomItemIn) -> UUID:
    await _project(db, principal, project_id, lock=True)  # serialises concurrent adds for the bound below
    count = await db.scalar(
        select(func.count())
        .select_from(InteriorCustomItem)
        .where(InteriorCustomItem.project_id == project_id)
    )
    if (count or 0) >= MAX_ITEMS_PER_PROJECT:
        raise InteriorLimitError("items")
    row = InteriorCustomItem(
        user_id=principal.user_id,
        project_id=project_id,
        name=data.name,
        quantity=data.quantity,
        price_pln=data.price_pln,
        url=data.url,
    )
    db.add(row)
    await db.flush()
    return row.id


async def update_item(
    db: AsyncSession, principal: Principal, project_id: UUID, item_id: UUID, data: CustomItemIn
) -> None:
    await _project(db, principal, project_id, lock=True)
    item = await _item(db, principal, project_id, item_id)
    item.name, item.quantity, item.price_pln, item.url = data.name, data.quantity, data.price_pln, data.url


async def _item(
    db: AsyncSession, principal: Principal, project_id: UUID, item_id: UUID
) -> InteriorCustomItem:
    row = await db.scalar(
        select(InteriorCustomItem).where(
            InteriorCustomItem.id == item_id,
            InteriorCustomItem.project_id == project_id,
            InteriorCustomItem.user_id == principal.user_id,
        )
    )
    if row is None:
        raise InteriorNotFoundError
    return row


async def delete_item(db: AsyncSession, principal: Principal, project_id: UUID, item_id: UUID) -> None:
    await _project(db, principal, project_id, lock=True)
    item = await _item(db, principal, project_id, item_id)
    if item.photo_media_id is not None:
        await _queue_keys(db, InteriorMedia.id == item.photo_media_id)
        await db.execute(delete(InteriorMedia).where(InteriorMedia.id == item.photo_media_id))
    await db.execute(delete(InteriorCustomItem).where(InteriorCustomItem.id == item_id))


# ---------- reading a project ----------
def _revision_out(row: InteriorRevision, basket: BasketFn) -> RevisionOut:
    snap: dict[str, Any] = row.snapshot
    items = [ItemSnapshot.model_validate(i) for i in snap["items"]]
    return RevisionOut(
        revision_id=row.id,
        number=row.number,
        brief=Brief.model_validate(snap["brief"]),
        source_digest=row.source_digest,
        items=items,
        basket=basket([(i.quantity, None if i.price_pln is None else Decimal(i.price_pln)) for i in items]),
        created_at=row.created_at,
    )


async def project_view(
    db: AsyncSession, principal: Principal, project_id: UUID, basket: BasketFn
) -> ProjectOut:
    p = await _project(db, principal, project_id)
    media = {
        m.id: m
        for m in (await db.scalars(select(InteriorMedia).where(InteriorMedia.project_id == project_id))).all()
    }
    source = max(
        (m for m in media.values() if m.purpose == "source" and m.state == "stored"),
        key=lambda m: (m.created_at, m.id),
        default=None,
    )
    items = (
        await db.scalars(
            select(InteriorCustomItem)
            .where(InteriorCustomItem.project_id == project_id)
            .order_by(InteriorCustomItem.created_at, InteriorCustomItem.id)
        )
    ).all()
    revisions = (
        await db.scalars(
            select(InteriorRevision)
            .where(InteriorRevision.project_id == project_id)
            .order_by(InteriorRevision.number.desc())
        )
    ).all()
    keep: list[str] = list(p.keep.get("items", []))
    return ProjectOut(
        project_id=p.id,
        name=p.name,
        brief=Brief(
            room_type=RoomType(p.room_type), style=p.style, budget_pln=p.budget_pln, notes=p.notes, keep=keep
        ),
        source=_media_ref(source) if source is not None else None,
        items=[_item_out(i, media.get(i.photo_media_id) if i.photo_media_id else None) for i in items],
        basket=basket([(i.quantity, i.price_pln) for i in items]),
        revisions=[_revision_out(r, basket) for r in revisions],
        created_at=p.created_at,
        expires_at=p.expires_at,
    )


# ---------- revisions ----------
async def create_revision(db: AsyncSession, principal: Principal, project_id: UUID) -> UUID:
    """Snapshot the brief and items as they are now. Immutable; later edits do not change it."""
    p = await _project(db, principal, project_id, lock=True)
    media = (
        await db.scalars(
            select(InteriorMedia).where(
                InteriorMedia.project_id == project_id,
                InteriorMedia.purpose == "source",
                InteriorMedia.state == "stored",
            )
        )
    ).all()
    source = max(media, key=lambda m: (m.created_at, m.id), default=None)
    items = (
        await db.scalars(
            select(InteriorCustomItem)
            .where(InteriorCustomItem.project_id == project_id)
            .order_by(InteriorCustomItem.created_at, InteriorCustomItem.id)
        )
    ).all()
    photos = {
        m.id: m.content_digest
        for m in (
            await db.scalars(
                select(InteriorMedia).where(
                    InteriorMedia.id.in_([i.photo_media_id for i in items if i.photo_media_id]),
                    InteriorMedia.state == "stored",
                )
            )
        ).all()
    }
    brief = Brief(
        room_type=RoomType(p.room_type),
        style=p.style,
        budget_pln=p.budget_pln,
        notes=p.notes,
        keep=list(p.keep.get("items", [])),
    )
    snapshot: dict[str, Any] = {
        "brief": brief.model_dump(mode="json"),
        "items": [
            ItemSnapshot(
                name=i.name,
                quantity=i.quantity,
                price_pln=_money(i.price_pln),
                url=i.url,
                photo_digest=photos.get(i.photo_media_id) if i.photo_media_id else None,
            ).model_dump(mode="json")
            for i in items
        ],
    }
    number = (
        await db.scalar(
            select(func.coalesce(func.max(InteriorRevision.number), 0)).where(
                InteriorRevision.project_id == project_id
            )
        )
        or 0
    ) + 1
    row = InteriorRevision(
        user_id=principal.user_id,
        project_id=project_id,
        number=number,
        source_digest=source.content_digest if source is not None else None,
        snapshot=snapshot,
    )
    db.add(row)
    await db.flush()
    return row.id


# ---------- media: upload, read, tombstones ----------
async def _queue_keys(db: AsyncSession, where: Any) -> None:
    await db.execute(
        insert(InteriorMediaTombstone)
        .from_select(["object_key"], select(InteriorMedia.object_key).where(where))
        .on_conflict_do_nothing()
    )


async def upload_photo(
    sessionmaker: async_sessionmaker[AsyncSession],
    store: ObjectStore,
    settings: Settings,
    principal: Principal,
    project_id: UUID,
    *,
    purpose: MediaPurpose,
    item_id: UUID | None,
    raw: bytes,
) -> MediaRef:
    """Normalise, record a pending row, put the object, mark it stored. Raises `ImageRejectedError` (nothing
    recorded), `InteriorNotFoundError`, `InteriorLimitError` or `ObjectStoreError` (row marked failed and its
    key queued for deletion, in case a partial object landed)."""
    if purpose is MediaPurpose.render:
        raise ValueError("renders are written by the generation worker")
    image = await asyncio.to_thread(normalize_image, raw)
    media_id = uuid4()
    store_purpose = StorePurpose.source if purpose is MediaPurpose.source else StorePurpose.item
    key = media_key(principal.user_id, store_purpose, media_id)
    async with sessionmaker() as db, db.begin():
        project = await _project(db, principal, project_id, lock=True)
        if purpose is MediaPurpose.custom_item:
            if item_id is None:
                raise InteriorNotFoundError
            await _item(db, principal, project_id, item_id)
        else:
            sources = await db.scalar(
                select(func.count())
                .select_from(InteriorMedia)
                .where(
                    InteriorMedia.project_id == project_id,
                    InteriorMedia.purpose == "source",
                    InteriorMedia.state != "failed",
                )
            )
            if (sources or 0) >= MAX_SOURCES_PER_PROJECT:
                raise InteriorLimitError("sources")
        now = await db_now(db)
        db.add(
            InteriorMedia(
                id=media_id,
                user_id=principal.user_id,
                project_id=project_id,
                purpose=purpose.value,
                state="pending",
                object_key=key,
                expires_at=now + timedelta(days=settings.media_abandoned_upload_days),
            )
        )
        project_expires = project.expires_at
    try:
        await store.put(key, image.data, image.mime)
    except ObjectStoreError:
        async with sessionmaker() as db, db.begin():
            await db.execute(update(InteriorMedia).where(InteriorMedia.id == media_id).values(state="failed"))
            await db.execute(insert(InteriorMediaTombstone).values(object_key=key).on_conflict_do_nothing())
        raise
    async with sessionmaker() as db, db.begin():
        stored = await db.execute(
            update(InteriorMedia)
            .where(InteriorMedia.id == media_id, InteriorMedia.state == "pending")
            .values(
                state="stored",
                content_digest=image.sha256,
                mime=image.mime,
                width=image.width,
                height=image.height,
                size_bytes=len(image.data),
                expires_at=project_expires,
            )
            .returning(InteriorMedia.id)
        )
        lost = stored.scalar_one_or_none() is None
        if lost:
            # The sweep removed the pending row while the object was being written: drop the object too.
            await db.execute(insert(InteriorMediaTombstone).values(object_key=key).on_conflict_do_nothing())
        elif purpose is MediaPurpose.custom_item and item_id is not None:
            item = await db.scalar(
                select(InteriorCustomItem).where(InteriorCustomItem.id == item_id).with_for_update()
            )
            if item is None:  # the item was deleted meanwhile
                lost = True
                await _queue_keys(db, InteriorMedia.id == media_id)
                await db.execute(delete(InteriorMedia).where(InteriorMedia.id == media_id))
            else:
                if item.photo_media_id is not None:  # replacing: the old bytes go, the 30 days do not reset
                    await _queue_keys(db, InteriorMedia.id == item.photo_media_id)
                    await db.execute(delete(InteriorMedia).where(InteriorMedia.id == item.photo_media_id))
                item.photo_media_id = media_id
        ref = None if lost else _media_ref(await db.get_one(InteriorMedia, media_id))
    if ref is None:  # raised after the block so the tombstone above is committed, not rolled back
        raise InteriorNotFoundError
    return ref


@dataclass(frozen=True)
class MediaContent:
    data: bytes
    mime: str
    digest: str


async def read_media(
    db: AsyncSession, store: ObjectStore, principal: Principal, project_id: UUID, media_id: UUID
) -> MediaContent:
    """The bytes of one stored image the caller owns. The digest is re-checked: a mismatch is never served."""
    await _project(db, principal, project_id)
    row = await db.scalar(
        select(InteriorMedia).where(
            InteriorMedia.id == media_id,
            InteriorMedia.project_id == project_id,
            InteriorMedia.user_id == principal.user_id,
            InteriorMedia.state == "stored",
        )
    )
    if row is None or row.content_digest is None or row.mime is None:
        raise InteriorNotFoundError
    try:
        data = await store.get(row.object_key)
    except ObjectStoreError as exc:
        if exc.code == "not_found":
            raise InteriorNotFoundError from None
        raise
    if hashlib.sha256(data).hexdigest() != row.content_digest:
        log.error("interior_media_digest_mismatch", media_id=str(media_id))
        raise ObjectStoreError("corrupt")
    return MediaContent(data, row.mime, row.content_digest)


async def drain_tombstones(
    sessionmaker: async_sessionmaker[AsyncSession], store: ObjectStore, limit: int = TOMBSTONE_BATCH
) -> int:
    """Delete queued objects. A failure keeps the tombstone and counts the attempt; returns deletions made."""
    async with sessionmaker() as db:
        keys = list(
            (
                await db.scalars(
                    select(InteriorMediaTombstone.object_key)
                    .order_by(InteriorMediaTombstone.created_at)
                    .limit(limit)
                )
            ).all()
        )
    deleted = 0
    for key in keys:
        try:
            await store.delete(key)
        except ObjectStoreError as exc:
            async with sessionmaker() as db, db.begin():
                attempts = await db.scalar(
                    update(InteriorMediaTombstone)
                    .where(InteriorMediaTombstone.object_key == key)
                    .values(attempts=InteriorMediaTombstone.attempts + 1)
                    .returning(InteriorMediaTombstone.attempts)
                )
            if (attempts or 0) >= MAX_TOMBSTONE_ATTEMPTS_LOGGED:
                log.error("interior_tombstone_stuck", attempts=attempts, code=exc.code)
            continue
        async with sessionmaker() as db, db.begin():
            await db.execute(delete(InteriorMediaTombstone).where(InteriorMediaTombstone.object_key == key))
        deleted += 1
    return deleted


@dataclass(frozen=True)
class SweepReport:
    projects: int
    abandoned_media: int


async def sweep_expired(sessionmaker: async_sessionmaker[AsyncSession]) -> SweepReport:
    """Retention: delete projects past `expires_at` and pending or failed uploads past their 7 days. Object
    keys are queued in the same transaction; call `drain_tombstones` afterwards."""
    async with sessionmaker() as db, db.begin():
        expired = (
            await db.scalars(
                select(InteriorProject.id)
                .where(InteriorProject.expires_at <= func.clock_timestamp())
                .with_for_update(skip_locked=True)
                .limit(TOMBSTONE_BATCH)
            )
        ).all()
        if expired:
            await _queue_keys(db, InteriorMedia.project_id.in_(expired))
            await db.execute(delete(InteriorProject).where(InteriorProject.id.in_(expired)))
        abandoned_where = (InteriorMedia.state != "stored") & (
            InteriorMedia.expires_at <= func.clock_timestamp()
        )
        abandoned = (
            await db.scalars(select(InteriorMedia.id).where(abandoned_where).limit(TOMBSTONE_BATCH))
        ).all()
        if abandoned:
            await _queue_keys(db, InteriorMedia.id.in_(abandoned))
            await db.execute(delete(InteriorMedia).where(InteriorMedia.id.in_(abandoned)))
    return SweepReport(len(expired), len(abandoned))


async def erase_account_media(db: AsyncSession, user_id: str) -> int:
    """Queue every object key of one account. Call in the erasure transaction before `delete_account`, so the
    cascade that removes the rows cannot lose the keys. Returns the number of keys queued."""
    queued = await db.scalars(
        insert(InteriorMediaTombstone)
        .from_select(["object_key"], select(InteriorMedia.object_key).where(InteriorMedia.user_id == user_id))
        .on_conflict_do_nothing()
        .returning(InteriorMediaTombstone.object_key)
    )
    return len(queued.all())
