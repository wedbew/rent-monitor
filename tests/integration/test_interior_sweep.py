"""The worker's interior sweep: expiry, then bytes, and a missing store keeps keys queued (RM-448)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from PIL import Image
from rm_contracts.interior import Brief, MediaPurpose, ProjectCreate, RoomType
from rm_core import interior as repo
from rm_core.db.models import InteriorMediaTombstone, InteriorProject, User
from rm_core.object_store import MemoryObjectStore
from rm_core.principal import Principal
from rm_core.settings import Settings
from rm_worker.tasks.interior import run_interior_sweep
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]


async def test_sweep_expires_then_deletes_bytes_and_survives_a_missing_store(engine: AsyncEngine) -> None:
    import io  # noqa: PLC0415

    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        await s.execute(delete(InteriorMediaTombstone))
        uid = str(uuid4())
        s.add(User(id=uid, email=f"{uid}@example.test"))
    who = Principal(uid, f"{uid}@example.test", "user", True, 1, "h")
    async with sm() as s, s.begin():
        pid = await repo.create_project(
            s, who, ProjectCreate(name="Salon", brief=Brief(room_type=RoomType.office, budget_pln=Decimal(1)))
        )
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (5, 5, 5)).save(buf, format="JPEG")
    store = MemoryObjectStore()
    await repo.upload_photo(
        sm,
        store,
        Settings(_env_file=None),  # pyright: ignore[reportCallIssue]
        who,
        pid,
        purpose=MediaPurpose.source,
        item_id=None,
        raw=buf.getvalue(),
    )
    async with sm() as s, s.begin():
        await s.execute(
            update(InteriorProject)
            .where(InteriorProject.id == pid)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    report, deleted = await run_interior_sweep(sm, None)  # store not configured: keys stay queued
    assert (report.projects, deleted) == (1, 0)
    assert len(store.objects) == 1
    async with sm() as s:
        assert await s.scalar(select(func.count()).select_from(InteriorMediaTombstone)) == 1
    again, deleted = await run_interior_sweep(sm, store)
    assert again.projects == 0
    assert deleted == 1
    assert store.objects == {}
