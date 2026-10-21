# ruff: noqa: F811  (fixtures `app`, `plans` are imported from test_me_saved_admin)
"""`/api/interior/.../generations` with the fake model, an in-memory store and real Postgres (RM-450)."""

import io
from collections.abc import AsyncIterator, Callable
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from PIL import Image
from rm_core.ai_budget import PostgresBudgetGate
from rm_core.db.models import AccountEntitlement, AiBudget, AiReservation, AiUsage, InteriorGeneration
from rm_core.object_store import MemoryObjectStore
from rm_core.settings import Settings
from rm_worker import interior_generation as flow
from rm_worker.clients.image_gen import FakeImageGenerator
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import Browser
from test_me_saved_admin import app, plans, sign_in  # noqa: F401  (fixtures: `app`, `plans`)

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
P = "/api/interior/projects"
OCTET = {"Content-Type": "application/octet-stream"}
BRIEF = {"room_type": "bedroom"}


class Queue:
    def __init__(self) -> None:
        self.deferred: list[UUID] = []
        self.fail = False

    async def run_interior_generation(self, generation_id: UUID) -> None:
        if self.fail:
            raise RuntimeError("queue down")
        self.deferred.append(generation_id)


def photo() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (100, 110, 120)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
async def stack(
    app: FastAPI, engine: AsyncEngine
) -> AsyncIterator[tuple[Queue, MemoryObjectStore, FakeImageGenerator]]:
    queue, store, fake = Queue(), MemoryObjectStore(), FakeImageGenerator()
    saved = (app.state.generation_queue, app.state.object_store, app.state.settings.interior_image_provider)
    app.state.generation_queue, app.state.object_store = queue, store
    app.state.settings.interior_image_provider = "fake"
    async with async_sessionmaker(engine)() as s, s.begin():
        for table in (InteriorGeneration, AiUsage, AiReservation, AiBudget):
            await s.execute(delete(table))
    yield queue, store, fake
    app.state.generation_queue, app.state.object_store, app.state.settings.interior_image_provider = saved


async def entitled(app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken) -> Browser:
    c, me = await sign_in(app, make_google_token)
    async with async_sessionmaker(engine)() as s, s.begin():
        s.add(AccountEntitlement(user_id=me["id"], kind="unlimited_reports", note="test"))
    return c


async def revision(c: Browser, *, with_photo: bool = True) -> tuple[str, str]:
    pid = (await c.post(P, json={"name": "Sypialnia", "brief": BRIEF})).json()["project_id"]
    if with_photo:
        assert (await c.post(f"{P}/{pid}/source", content=photo(), headers=OCTET)).status_code == 201
    saved = (await c.post(f"{P}/{pid}/revisions")).json()
    return pid, saved["revisions"][0]["revision_id"]


async def test_off_by_default_is_an_honest_503_and_nothing_is_created(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    queue, _, _ = stack
    c = await entitled(app, engine, make_google_token)
    pid, rev = await revision(c)
    app.state.settings.interior_image_provider = "none"
    r = await c.post(f"{P}/{pid}/generations", json={"revision_id": rev})
    assert (r.status_code, r.json()["code"]) == (503, "GENERATION_UNAVAILABLE")
    assert queue.deferred == []
    assert (await c.get(f"{P}/{pid}/generations")).json() == []
    assert (await c.get(f"{P}/{pid}")).status_code == 200  # the concept and revisions stay usable


async def test_create_is_202_once_and_repeats_return_the_same_operation_without_a_second_job(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    queue, _, _ = stack
    c = await entitled(app, engine, make_google_token)
    pid, rev = await revision(c)
    key = str(uuid4())
    first = await c.post(
        f"{P}/{pid}/generations", json={"revision_id": rev}, headers={"Idempotency-Key": key}
    )
    assert first.status_code == 202
    body = first.json()
    assert (body["state"], body["error_code"], body["output"], body["cost_usd"]) == (
        "queued",
        None,
        None,
        None,
    )
    assert body["model"] == app.state.settings.interior_image_model
    assert queue.deferred == [UUID(body["generation_id"])]
    for headers in ({"Idempotency-Key": key}, {}):  # a repeated click, with or without the key
        again = await c.post(f"{P}/{pid}/generations", json={"revision_id": rev}, headers=headers)
        assert (again.status_code, again.json()["generation_id"]) == (200, body["generation_id"])
    assert len(queue.deferred) == 1  # one job, however many clicks
    assert len((await c.get(f"{P}/{pid}/generations")).json()) == 1


async def test_conflicts_say_why(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    c = await entitled(app, engine, make_google_token)
    pid, rev = await revision(c)
    other = (await c.post(f"{P}/{pid}/revisions")).json()["revisions"][0]["revision_id"]
    started = (await c.post(f"{P}/{pid}/generations", json={"revision_id": rev})).json()["generation_id"]
    busy = await c.post(f"{P}/{pid}/generations", json={"revision_id": other})
    assert (busy.status_code, busy.json()["code"], busy.json()["reason"]) == (
        409,
        "GENERATION_CONFLICT",
        "active",
    )
    assert busy.json()["generation_id"] == started
    bare_pid, bare_rev = await revision(c, with_photo=False)
    none = await c.post(f"{P}/{bare_pid}/generations", json={"revision_id": bare_rev})
    assert (none.status_code, none.json()["reason"]) == (409, "no_source_photo")
    unknown = await c.post(f"{P}/{pid}/generations", json={"revision_id": str(uuid4())})
    assert (unknown.status_code, unknown.json()["code"]) == (404, "NOT_FOUND")


async def test_a_dead_queue_does_not_fail_the_request_and_the_operation_stays_queued(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    queue, _, _ = stack
    c = await entitled(app, engine, make_google_token)
    pid, rev = await revision(c)
    queue.fail = True
    r = await c.post(f"{P}/{pid}/generations", json={"revision_id": rev})
    assert (r.status_code, r.json()["state"]) == (202, "queued")  # the reconciler closes it at its deadline


async def test_cancel_works_while_queued_and_is_refused_once_running(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    from rm_core import interior_generation as gen  # noqa: PLC0415

    c = await entitled(app, engine, make_google_token)
    pid, rev = await revision(c)
    gid = (await c.post(f"{P}/{pid}/generations", json={"revision_id": rev})).json()["generation_id"]
    cancelled = await c.post(f"{P}/{pid}/generations/{gid}/cancel")
    assert (cancelled.status_code, cancelled.json()["state"]) == (200, "cancelled")
    assert (await c.post(f"{P}/{pid}/generations/{gid}/cancel")).json()["state"] == "cancelled"  # idempotent
    second = (await c.post(f"{P}/{pid}/generations", json={"revision_id": rev})).json()["generation_id"]
    assert await gen.claim(async_sessionmaker(engine), UUID(second)) is not None  # a worker took it
    running = await c.post(f"{P}/{pid}/generations/{second}/cancel")
    assert (running.status_code, running.json()["code"], running.json()["reason"]) == (
        409,
        "GENERATION_CONFLICT",
        "running",
    )


async def test_the_whole_journey_ends_in_a_stored_picture_beside_the_untouched_original(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    queue, store, fake = stack
    c = await entitled(app, engine, make_google_token)
    pid, rev = await revision(c)
    before = (await c.get(f"{P}/{pid}")).json()["source"]
    gid = (await c.post(f"{P}/{pid}/generations", json={"revision_id": rev})).json()["generation_id"]
    sm = async_sessionmaker(engine)
    deps = flow.Deps(
        sm,
        store,
        fake,
        PostgresBudgetGate(sm, monthly_cap_usd=Decimal("5")),
        Settings(_env_file=None, interior_image_provider="fake"),  # pyright: ignore[reportCallIssue]
    )
    await flow.run_generation(deps, queue.deferred[0])
    done = (await c.get(f"{P}/{pid}/generations/{gid}")).json()
    assert (done["state"], done["cost_usd"], done["cost_estimated"]) == ("succeeded", "0.034000", False)
    assert done["output"]["purpose"] == "render"
    image = await c.get(f"{P}/{pid}/media/{done['output']['media_id']}")
    assert (image.status_code, image.headers["content-type"], image.headers["cache-control"]) == (
        200,
        "image/jpeg",
        "private, no-store",
    )
    assert (await c.get(f"{P}/{pid}")).json()["source"] == before  # the original is the same object
    assert fake.calls == 1
    reloaded = (
        await c.get(f"{P}/{pid}/generations")
    ).json()  # a reload reads the stored result, no model call
    assert [g["state"] for g in reloaded] == ["succeeded"]
    assert fake.calls == 1


async def test_other_people_get_404_and_strangers_get_403(
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    stack: tuple[Queue, MemoryObjectStore, FakeImageGenerator],
) -> None:
    a = await entitled(app, engine, make_google_token)
    b = await entitled(app, engine, make_google_token)
    pid, rev = await revision(a)
    gid = (await a.post(f"{P}/{pid}/generations", json={"revision_id": rev})).json()["generation_id"]
    calls: list[tuple[str, str, dict[str, Any]]] = [
        ("POST", f"{P}/{pid}/generations", {"json": {"revision_id": rev}}),
        ("GET", f"{P}/{pid}/generations", {}),
        ("GET", f"{P}/{pid}/generations/{gid}", {}),
        ("POST", f"{P}/{pid}/generations/{gid}/cancel", {}),
    ]
    for method, path, kw in calls:
        r = await b.request(method, path, **kw)
        assert (r.status_code, r.json()["code"]) == (404, "NOT_FOUND"), (method, path)
    stranger, _ = await sign_in(app, make_google_token)
    assert (await stranger.get(f"{P}/{pid}/generations")).status_code == 403
