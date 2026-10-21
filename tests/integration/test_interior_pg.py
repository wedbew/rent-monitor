"""Interior architect repository on real Postgres with a fake object store (RM-448, #284).

Covers tenant isolation (404, never 403), the person's own items (only a name required), upload ordering and
failure, replacement, tombstoned deletion, immutable revisions under concurrency, 30-day retention that edits
cannot extend, 7-day abandoned uploads, and account erasure that cannot lose object keys.
"""

import asyncio
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from PIL import Image
from rm_api.interior import MONEY
from rm_contracts.interior import (
    Basket,
    Brief,
    CustomItemIn,
    MediaPurpose,
    ProjectCreate,
    RoomType,
)
from rm_core import interior as repo
from rm_core.db.models import (
    InteriorCustomItem,
    InteriorMedia,
    InteriorMediaTombstone,
    InteriorProject,
    User,
)
from rm_core.interior_images import ImageRejectedError
from rm_core.object_store import MemoryObjectStore, ObjectStoreError
from rm_core.principal import Principal
from rm_core.privacy import delete_account
from rm_core.settings import Settings
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]
SETTINGS = Settings(_env_file=None, app_env="test")  # pyright: ignore[reportCallIssue]


@pytest.fixture(autouse=True)
async def clean_tombstones(engine: AsyncEngine) -> None:
    """Modules share one database and the drain takes every queued key: start each test empty."""
    async with async_sessionmaker(engine)() as s, s.begin():
        await s.execute(delete(InteriorMediaTombstone))


BRIEF = Brief(room_type=RoomType.living_room, style="scandi", budget_pln=Decimal("5000"), keep=["sofa"])


def jpeg(color: tuple[int, int, int] = (200, 30, 30), size: tuple[int, int] = (640, 480)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


async def person(engine: AsyncEngine) -> Principal:
    uid = str(uuid4())
    async with async_sessionmaker(engine)() as s, s.begin():
        s.add(User(id=uid, email=f"{uid}@example.test"))
    return Principal(
        user_id=uid,
        email=f"{uid}@example.test",
        role="user",
        email_verified=True,
        session_id=1,
        token_hash="h",
    )


async def new_project(engine: AsyncEngine, who: Principal, name: str = "Salon") -> UUID:
    async with async_sessionmaker(engine)() as s, s.begin():
        return await repo.create_project(s, who, ProjectCreate(name=name, brief=BRIEF))


async def upload(engine: AsyncEngine, store: MemoryObjectStore, who: Principal, project: UUID, **kw: object):
    sm = async_sessionmaker(engine)
    args: dict[str, object] = {"purpose": MediaPurpose.source, "item_id": None, "raw": jpeg()}
    args.update(kw)
    return await repo.upload_photo(sm, store, SETTINGS, who, project, **args)  # pyright: ignore[reportArgumentType]


async def view(engine: AsyncEngine, who: Principal, project: UUID):
    async with async_sessionmaker(engine)() as s:
        return await repo.project_view(s, who, project, MONEY)


async def test_project_round_trip_and_30_day_lifetime(engine: AsyncEngine) -> None:
    who = await person(engine)
    pid = await new_project(engine, who)
    got = await view(engine, who, pid)
    assert got.brief == BRIEF
    assert got.source is None
    assert got.basket.complete is False
    lifetime = got.expires_at - got.created_at
    assert timedelta(days=29, hours=23) < lifetime < timedelta(days=30, hours=1)
    listing = await _list(engine, who)
    assert [p.project_id for p in listing] == [pid]
    assert listing[0].has_source is False


async def _list(engine: AsyncEngine, who: Principal):
    async with async_sessionmaker(engine)() as s:
        return await repo.list_projects(s, who)


async def test_editing_a_project_never_extends_its_lifetime(engine: AsyncEngine) -> None:
    who = await person(engine)
    pid = await new_project(engine, who)
    before = (await view(engine, who, pid)).expires_at
    async with async_sessionmaker(engine)() as s, s.begin():
        await repo.update_project(
            s, who, pid, name="Salon 2", brief=BRIEF.model_copy(update={"style": "loft"})
        )
    after = await view(engine, who, pid)
    assert after.expires_at == before
    assert (after.name, after.brief.style) == ("Salon 2", "loft")


async def test_account_is_limited_to_20_projects(engine: AsyncEngine) -> None:
    who = await person(engine)
    for i in range(20):
        await new_project(engine, who, f"P{i}")
    with pytest.raises(repo.InteriorLimitError) as err:
        await new_project(engine, who, "one too many")
    assert err.value.code == "projects"


async def test_concurrent_creates_cannot_exceed_the_project_cap(engine: AsyncEngine) -> None:
    who = await person(engine)
    for i in range(18):
        await new_project(engine, who, f"P{i}")
    results = await asyncio.gather(
        *(new_project(engine, who, f"R{i}") for i in range(6)), return_exceptions=True
    )
    assert sum(isinstance(r, UUID) for r in results) == 2
    assert all(isinstance(r, repo.InteriorLimitError) for r in results if not isinstance(r, UUID))


async def test_foreign_and_unknown_ids_are_not_found_everywhere(engine: AsyncEngine) -> None:
    owner, other = await person(engine), await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, owner)
    media = await upload(engine, store, owner, pid)
    sm = async_sessionmaker(engine)
    item_id = await _add(engine, owner, pid, CustomItemIn(name="Lampa"))
    for target in (pid, uuid4()):
        async with sm() as s:
            with pytest.raises(repo.InteriorNotFoundError):
                await repo.project_view(s, other, target, MONEY)
        for call in (
            lambda s, t=target: repo.update_project(s, other, t, name="x", brief=BRIEF),
            lambda s, t=target: repo.delete_project(s, other, t),
            lambda s, t=target: repo.add_item(s, other, t, CustomItemIn(name="x")),
            lambda s, t=target: repo.delete_item(s, other, t, item_id),
            lambda s, t=target: repo.update_item(s, other, t, item_id, CustomItemIn(name="x")),
            lambda s, t=target: repo.create_revision(s, other, t),
            lambda s, t=target: repo.read_media(s, store, other, t, media.media_id),
        ):
            async with sm() as s, s.begin():
                with pytest.raises(repo.InteriorNotFoundError):
                    await call(s)
    with pytest.raises(repo.InteriorNotFoundError):
        await upload(engine, store, other, pid)
    assert [p.project_id for p in await _list(engine, other)] == []
    assert (await view(engine, owner, pid)).items[0].name == "Lampa"  # the owner's data is untouched


async def _add(engine: AsyncEngine, who: Principal, pid: UUID, data: CustomItemIn) -> UUID:
    async with async_sessionmaker(engine)() as s, s.begin():
        return await repo.add_item(s, who, pid, data)


async def test_an_item_needs_only_a_name_and_unknown_price_is_never_zero(engine: AsyncEngine) -> None:
    who = await person(engine)
    pid = await new_project(engine, who)
    await _add(engine, who, pid, CustomItemIn(name="Stary fotel"))
    await _add(
        engine,
        who,
        pid,
        CustomItemIn(
            name="Regał", quantity=2, price_pln=Decimal("199.99"), url="https://sklep.example/regal"
        ),
    )
    got = await view(engine, who, pid)
    plain, priced = got.items
    assert (plain.price_pln, plain.url, plain.photo, plain.quantity) == (None, None, None, 1)
    assert (priced.price_pln, priced.url) == ("199.99", "https://sklep.example/regal")
    assert got.basket == Basket(
        known_subtotal_pln="399.98",
        priced_lines=1,
        unpriced_lines=1,
        stale_lines=0,
        delivery_known_pln="0.00",
        delivery_unknown_lines=0,
        complete=False,
    )


async def test_items_are_bounded_per_project_even_when_added_concurrently(engine: AsyncEngine) -> None:
    who = await person(engine)
    pid = await new_project(engine, who)
    for i in range(28):
        await _add(engine, who, pid, CustomItemIn(name=f"I{i}"))
    results = await asyncio.gather(
        *(_add(engine, who, pid, CustomItemIn(name=f"R{i}")) for i in range(5)), return_exceptions=True
    )
    assert sum(isinstance(r, UUID) for r in results) == 2


async def test_upload_normalises_stores_and_records_the_digest(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    ref = await upload(engine, store, who, pid, raw=jpeg(size=(3200, 2400)))
    assert ref.state.value == "stored"
    assert max(ref.width or 0, ref.height or 0) == 1600
    got = await view(engine, who, pid)
    assert got.source is not None
    assert got.source.content_digest == ref.content_digest
    content = None
    async with async_sessionmaker(engine)() as s:
        content = await repo.read_media(s, store, who, pid, ref.media_id)
    assert content.mime == "image/jpeg"
    assert [k for k in store.objects if k.startswith(f"u/{who.user_id}/source/")] != []
    # the project's lifetime applies to a stored image; a pending one would have been 7 days
    assert ref.expires_at == got.expires_at


async def test_a_bad_image_records_nothing(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    with pytest.raises(ImageRejectedError):
        await upload(engine, store, who, pid, raw=b"not an image")
    async with async_sessionmaker(engine)() as s:
        assert await s.scalar(select(func.count()).select_from(InteriorMedia)) == await s.scalar(
            select(func.count()).select_from(InteriorMedia).where(InteriorMedia.user_id != who.user_id)
        )
    assert store.objects == {}


async def test_a_store_failure_marks_the_row_failed_and_queues_the_key(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    store.fail_next = "unavailable"
    with pytest.raises(ObjectStoreError):
        await upload(engine, store, who, pid)
    async with async_sessionmaker(engine)() as s:
        row = (await s.scalars(select(InteriorMedia).where(InteriorMedia.project_id == pid))).one()
        assert row.state == "failed"
        assert await s.get(InteriorMediaTombstone, row.object_key) is not None
    assert (await view(engine, who, pid)).source is None
    assert await repo.drain_tombstones(async_sessionmaker(engine), store) >= 1


async def test_sources_are_kept_not_overwritten_up_to_a_bound(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    first = await upload(engine, store, who, pid, raw=jpeg((10, 10, 10)))
    second = await upload(engine, store, who, pid, raw=jpeg((250, 250, 250)))
    assert first.content_digest != second.content_digest
    assert (await view(engine, who, pid)).source is not None
    assert len(store.objects) == 2  # the first photo was never overwritten
    for i in range(3):
        await upload(engine, store, who, pid, raw=jpeg((i * 20 + 5, 90, 90)))
    with pytest.raises(repo.InteriorLimitError) as err:
        await upload(engine, store, who, pid, raw=jpeg((1, 2, 3)))
    assert err.value.code == "sources"


async def test_item_photo_replacement_queues_and_deletes_the_old_bytes(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    item = await _add(engine, who, pid, CustomItemIn(name="Lampa"))
    a = await upload(
        engine, store, who, pid, purpose=MediaPurpose.custom_item, item_id=item, raw=jpeg((9, 9, 9))
    )
    b = await upload(
        engine, store, who, pid, purpose=MediaPurpose.custom_item, item_id=item, raw=jpeg((99, 9, 9))
    )
    got = await view(engine, who, pid)
    assert got.items[0].photo is not None
    assert got.items[0].photo.media_id == b.media_id
    assert a.media_id != b.media_id
    assert len(store.objects) == 2  # old bytes still there until the drain
    assert await repo.drain_tombstones(async_sessionmaker(engine), store) == 1
    assert len(store.objects) == 1
    with pytest.raises(repo.InteriorNotFoundError):
        await upload(engine, store, who, pid, purpose=MediaPurpose.custom_item, item_id=uuid4())


async def test_read_media_refuses_corrupted_bytes(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    ref = await upload(engine, store, who, pid)
    key = next(iter(store.objects))
    store.objects[key] = (b"tampered", "image/jpeg")
    async with async_sessionmaker(engine)() as s:
        with pytest.raises(ObjectStoreError) as err:
            await repo.read_media(s, store, who, pid, ref.media_id)
    assert err.value.code == "corrupt"


async def test_revisions_are_immutable_snapshots_with_unique_numbers_under_concurrency(
    engine: AsyncEngine,
) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    ref = await upload(engine, store, who, pid)
    item = await _add(engine, who, pid, CustomItemIn(name="Lampa", price_pln=Decimal("50")))

    async def revise() -> UUID:
        async with async_sessionmaker(engine)() as s, s.begin():
            return await repo.create_revision(s, who, pid)

    await revise()
    async with async_sessionmaker(engine)() as s, s.begin():  # edit everything after revision 1
        await repo.update_item(s, who, pid, item, CustomItemIn(name="Zmieniona", price_pln=Decimal("75")))
        await repo.update_project(s, who, pid, name="Inny", brief=BRIEF.model_copy(update={"style": "loft"}))
    await asyncio.gather(*(revise() for _ in range(5)))
    got = await view(engine, who, pid)
    assert sorted(r.number for r in got.revisions) == [1, 2, 3, 4, 5, 6]
    first = next(r for r in got.revisions if r.number == 1)
    assert (first.items[0].name, first.items[0].price_pln, first.brief.style) == ("Lampa", "50.00", "scandi")
    assert first.source_digest == ref.content_digest
    assert first.basket.known_subtotal_pln == "50.00"
    latest = next(r for r in got.revisions if r.number == 6)
    assert (latest.items[0].name, latest.brief.style) == ("Zmieniona", "loft")


async def test_deleting_a_project_queues_only_its_own_objects(engine: AsyncEngine) -> None:
    a, b = await person(engine), await person(engine)
    store = MemoryObjectStore()
    pa, pb = await new_project(engine, a), await new_project(engine, b)
    await upload(engine, store, a, pa)
    await upload(engine, store, b, pb)
    async with async_sessionmaker(engine)() as s, s.begin():
        await repo.delete_project(s, a, pa)
    assert len(store.objects) == 2
    assert await repo.drain_tombstones(async_sessionmaker(engine), store) == 1
    assert list(store.objects)
    assert all(k.startswith(f"u/{b.user_id}/") for k in store.objects)
    assert (await view(engine, b, pb)).source is not None


async def test_drain_keeps_a_tombstone_on_failure_and_finishes_later(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    pid = await new_project(engine, who)
    await upload(engine, store, who, pid)
    async with async_sessionmaker(engine)() as s, s.begin():
        await repo.delete_project(s, who, pid)
    sm = async_sessionmaker(engine)
    store.fail_next = "unavailable"
    assert await repo.drain_tombstones(sm, store) == 0
    async with sm() as s:
        attempts = await s.scalar(
            select(InteriorMediaTombstone.attempts).where(
                InteriorMediaTombstone.object_key.like(f"u/{who.user_id}/%")
            )
        )
    assert attempts == 1
    assert len(store.objects) == 1
    assert await repo.drain_tombstones(sm, store) == 1
    assert store.objects == {}


async def test_retention_sweeps_expired_projects_and_abandoned_uploads(engine: AsyncEngine) -> None:
    who = await person(engine)
    store = MemoryObjectStore()
    sm = async_sessionmaker(engine)
    old, keep = await new_project(engine, who, "old"), await new_project(engine, who, "keep")
    await upload(engine, store, who, old)
    await upload(engine, store, who, keep)
    store.fail_next = "unavailable"
    with pytest.raises(ObjectStoreError):
        await upload(engine, store, who, keep)  # a failed upload on the surviving project
    async with sm() as s, s.begin():
        past = datetime.now(UTC) - timedelta(days=1)
        await s.execute(update(InteriorProject).where(InteriorProject.id == old).values(expires_at=past))
        await s.execute(
            update(InteriorMedia)
            .where(InteriorMedia.project_id == keep, InteriorMedia.state == "failed")
            .values(expires_at=past)
        )
    with pytest.raises(repo.InteriorNotFoundError):  # an expired project is already invisible
        await view(engine, who, old)
    report = await repo.sweep_expired(sm)
    assert (report.projects, report.abandoned_media) == (1, 1)
    await repo.drain_tombstones(sm, store)
    assert len(store.objects) == 1  # only the surviving project's stored photo remains
    async with sm() as s:
        assert (
            await s.scalar(select(func.count()).select_from(InteriorProject).where(InteriorProject.id == old))
            == 0
        )
        assert (await view(engine, who, keep)).source is not None
    again = await repo.sweep_expired(sm)
    assert (again.projects, again.abandoned_media) == (0, 0)


async def test_a_pending_row_older_than_7_days_is_swept_with_its_possible_object(engine: AsyncEngine) -> None:
    who = await person(engine)
    sm = async_sessionmaker(engine)
    pid = await new_project(engine, who)
    async with sm() as s, s.begin():
        s.add(
            InteriorMedia(
                user_id=who.user_id,
                project_id=pid,
                purpose="source",
                state="pending",
                object_key=f"u/{who.user_id}/source/{uuid4()}",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
    assert (await repo.sweep_expired(sm)).abandoned_media == 1
    async with sm() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(InteriorMediaTombstone)
                .where(InteriorMediaTombstone.object_key.like(f"u/{who.user_id}/%"))
            )
            == 1
        )


async def test_account_erasure_cannot_lose_object_keys(engine: AsyncEngine) -> None:
    who, other = await person(engine), await person(engine)
    store = MemoryObjectStore()
    sm = async_sessionmaker(engine)
    pid, other_pid = await new_project(engine, who), await new_project(engine, other)
    item = await _add(engine, who, pid, CustomItemIn(name="Lampa"))
    await upload(engine, store, who, pid)
    await upload(engine, store, who, pid, purpose=MediaPurpose.custom_item, item_id=item)
    await upload(engine, store, other, other_pid)
    async with sm() as s, s.begin():
        queued = await repo.erase_account_media(s, who.user_id)
        report = await delete_account(s, who.user_id)
    assert queued == 2
    assert report.deleted
    async with sm() as s:
        assert (
            await s.scalar(
                select(func.count())
                .select_from(InteriorProject)
                .where(InteriorProject.user_id == who.user_id)
            )
            == 0
        )
        assert (
            await s.scalar(
                select(func.count())
                .select_from(InteriorCustomItem)
                .where(InteriorCustomItem.user_id == who.user_id)
            )
            == 0
        )
    assert len(store.objects) == 3
    assert await repo.drain_tombstones(sm, store) == 2
    assert [k.split("/")[1] for k in store.objects] == [other.user_id]
