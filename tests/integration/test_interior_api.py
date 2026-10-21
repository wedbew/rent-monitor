# ruff: noqa: F811  (the `app` fixture is imported from test_me_saved_admin and used as a parameter)
"""`/api/interior/*` on real Postgres with an in-memory image store (RM-456, #284).

Smoke scenarios already cover every status; this file asserts what they cannot: who may use the beta, tenant
isolation between two entitled people, what an image response looks like on the wire, upload bounds, exact
basket figures and that deleting the account queues the bytes for deletion.
"""

import io
from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import FastAPI
from PIL import Image
from rm_core import interior as repo
from rm_core.db.models import (
    AccountEntitlement,
    FeatureFlag,
    FeatureOverride,
    InteriorMediaTombstone,
    User,
)
from rm_core.object_store import MemoryObjectStore
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import Browser
from test_me_saved_admin import app, plans, sign_in  # noqa: F401  (fixtures: `app`, `plans`)

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
P = "/api/interior/projects"
OCTET = {"Content-Type": "application/octet-stream"}
BRIEF = {"room_type": "bedroom", "budget_pln": "3000"}


def photo(size: tuple[int, int] = (800, 600), color: tuple[int, int, int] = (120, 90, 60)) -> bytes:
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    Image.new("RGB", size, color).save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


@pytest.fixture
async def store(app: FastAPI) -> AsyncIterator[MemoryObjectStore]:
    memory = MemoryObjectStore()
    previous, app.state.object_store = app.state.object_store, memory
    yield memory
    app.state.object_store = previous


async def tester(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> tuple[Browser, dict[str, str]]:
    c, me = await sign_in(app, make_google_token)
    async with async_sessionmaker(engine)() as s, s.begin():
        s.add(AccountEntitlement(user_id=me["id"], kind="unlimited_reports", note="test"))
    return c, me


async def test_only_authorised_testers_may_use_the_beta(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, plans: None
) -> None:
    del plans
    stranger, me = await sign_in(app, make_google_token)
    r = await stranger.get(P)
    assert r.status_code == 403
    assert r.json()["code"] == "FEATURE_NOT_IN_PLAN"
    assert (await stranger.post(P, json={"name": "x", "brief": BRIEF})).status_code == 403

    async with async_sessionmaker(engine)() as s, s.begin():  # a staff override of the `redesign` flag
        if await s.get(FeatureFlag, "redesign") is None:
            s.add(FeatureFlag(key="redesign", description="Interior architect", enabled_default=False))
            await s.flush()
        s.add(
            FeatureOverride(
                flag_key="redesign", user_id=me["id"], enabled=True, reason="beta", created_by="t"
            )
        )
    assert (await stranger.get(P)).status_code == 200

    async with async_sessionmaker(engine)() as s, s.begin():  # revoking the override closes it again
        await s.execute(delete(FeatureOverride).where(FeatureOverride.user_id == me["id"]))
    assert (await stranger.get(P)).status_code == 403

    entitled, _ = await tester(app, engine, make_google_token)
    assert (await entitled.get(P)).status_code == 200

    admin, admin_me = await sign_in(app, make_google_token)
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.id == admin_me["id"]).values(role="admin"))
    app.state.principal_cache.clear()
    assert (await admin.get(P)).status_code == 200


async def test_two_testers_cannot_see_or_touch_each_other(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, store: MemoryObjectStore
) -> None:
    a, _ = await tester(app, engine, make_google_token)
    b, _ = await tester(app, engine, make_google_token)
    project = (await a.post(P, json={"name": "Moje", "brief": BRIEF})).json()["project_id"]
    media = (await a.post(f"{P}/{project}/source", content=photo(), headers=OCTET)).json()["media_id"]
    item = (await a.post(f"{P}/{project}/items", json={"name": "Lampa"})).json()["items"][0]["item_id"]
    calls = [
        ("GET", f"{P}/{project}", {}),
        ("PUT", f"{P}/{project}", {"json": {"name": "x", "brief": BRIEF}}),
        ("DELETE", f"{P}/{project}", {}),
        ("POST", f"{P}/{project}/items", {"json": {"name": "x"}}),
        ("PUT", f"{P}/{project}/items/{item}", {"json": {"name": "x"}}),
        ("DELETE", f"{P}/{project}/items/{item}", {}),
        ("POST", f"{P}/{project}/source", {"content": photo(), "headers": OCTET}),
        ("PUT", f"{P}/{project}/items/{item}/photo", {"content": photo(), "headers": OCTET}),
        ("GET", f"{P}/{project}/media/{media}", {}),
        ("POST", f"{P}/{project}/revisions", {}),
    ]
    for method, path, kw in calls:
        r = await b.request(method, path, **kw)
        assert r.status_code == 404, (method, path)
        assert r.json()["code"] == "NOT_FOUND"
    assert (await b.get(P)).json() == []
    still = (await a.get(f"{P}/{project}")).json()
    assert still["name"] == "Moje"
    assert [i["name"] for i in still["items"]] == ["Lampa"]
    assert still["source"]["media_id"] == media


async def test_the_image_response_is_private_stripped_and_typed(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, store: MemoryObjectStore
) -> None:
    c, _ = await tester(app, engine, make_google_token)
    project = (await c.post(P, json={"name": "Salon", "brief": BRIEF})).json()["project_id"]
    ref = (await c.post(f"{P}/{project}/source", content=photo((3200, 2400)), headers=OCTET)).json()
    assert ref["state"] == "stored"
    assert max(ref["width"], ref["height"]) == 1600
    r = await c.get(f"{P}/{project}/media/{ref['media_id']}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["etag"] == f'"{ref["content_digest"]}"'
    assert b"SecretCameraMaker" not in r.content
    with Image.open(io.BytesIO(r.content)) as im:
        assert im.format == "JPEG"
        assert not im.getexif()
    assert (await c.get(f"{P}/{project}")).headers["cache-control"] == "private, no-store"


async def test_uploads_are_bounded_and_refused_with_a_reason(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, store: MemoryObjectStore
) -> None:
    c, _ = await tester(app, engine, make_google_token)
    project = (await c.post(P, json={"name": "Salon", "brief": BRIEF})).json()["project_id"]
    big = await c.post(f"{P}/{project}/source", content=b"\0" * (10 * 1024 * 1024 + 1), headers=OCTET)
    assert big.status_code == 422
    assert (big.json()["code"], big.json()["reason"]) == ("IMAGE_REJECTED", "too_large")
    junk = await c.post(f"{P}/{project}/source", content=b"<html>not an image</html>", headers=OCTET)
    assert (junk.status_code, junk.json()["reason"]) == (422, "malformed")
    tiny = await c.post(f"{P}/{project}/source", content=photo((50, 50)), headers=OCTET)
    assert tiny.json()["reason"] == "too_small"
    assert store.objects == {}  # nothing stored for any refusal
    assert (await c.get(f"{P}/{project}")).json()["source"] is None


async def test_storage_switched_off_or_missing_answers_503_and_keeps_the_project(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, store: MemoryObjectStore
) -> None:
    c, _ = await tester(app, engine, make_google_token)
    project = (await c.post(P, json={"name": "Salon", "brief": BRIEF})).json()["project_id"]
    store.fail_next = "unavailable"
    down = await c.post(f"{P}/{project}/source", content=photo(), headers=OCTET)
    assert (down.status_code, down.json()["code"]) == (503, "MEDIA_STORAGE_UNAVAILABLE")
    assert "unavailable" not in down.text  # no provider detail leaks
    app.state.settings.legal_images_enabled = False  # the LEGAL[images] kill switch
    try:
        off = await c.post(f"{P}/{project}/source", content=photo(), headers=OCTET)
        assert off.status_code == 503
    finally:
        app.state.settings.legal_images_enabled = True
    assert (await c.get(f"{P}/{project}")).status_code == 200  # metadata keeps working without images
    ok = await c.post(f"{P}/{project}/source", content=photo(), headers=OCTET)
    assert ok.status_code == 201


async def test_basket_figures_are_exact_strings_and_unknown_prices_are_excluded(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, store: MemoryObjectStore
) -> None:
    c, _ = await tester(app, engine, make_google_token)
    project = (await c.post(P, json={"name": "Salon", "brief": BRIEF})).json()["project_id"]
    await c.post(f"{P}/{project}/items", json={"name": "Stary fotel"})
    await c.post(f"{P}/{project}/items", json={"name": "Regał", "quantity": 2, "price_pln": "199.99"})
    got = (await c.post(f"{P}/{project}/revisions")).json()
    assert got["basket"] == {
        "known_subtotal_pln": "399.98",
        "priced_lines": 1,
        "unpriced_lines": 1,
        "complete": False,
    }
    revision = got["revisions"][0]
    assert revision["number"] == 1
    assert revision["basket"] == got["basket"]
    assert [(i["name"], i["price_pln"]) for i in revision["items"]] == [
        ("Stary fotel", None),
        ("Regał", "199.99"),
    ]
    assert got["brief"]["budget_pln"] == "3000.00"


async def test_deleting_the_account_queues_every_object_for_deletion(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, store: MemoryObjectStore
) -> None:
    c, me = await tester(app, engine, make_google_token)
    other, _ = await tester(app, engine, make_google_token)
    project = (await c.post(P, json={"name": "Salon", "brief": BRIEF})).json()["project_id"]
    item = (await c.post(f"{P}/{project}/items", json={"name": "Lampa"})).json()["items"][0]["item_id"]
    await c.post(f"{P}/{project}/source", content=photo(), headers=OCTET)
    await c.put(f"{P}/{project}/items/{item}/photo", content=photo(color=(1, 2, 3)), headers=OCTET)
    other_project = (await other.post(P, json={"name": "Cudzy", "brief": BRIEF})).json()["project_id"]
    await other.post(f"{P}/{other_project}/source", content=photo(), headers=OCTET)
    async with async_sessionmaker(engine)() as s, s.begin():
        await s.execute(delete(InteriorMediaTombstone))
    assert len(store.objects) == 3

    r = await c.request("DELETE", "/api/me", json={"confirm_email": me["email"]})
    assert r.status_code == 204
    async with async_sessionmaker(engine)() as s:
        keys = (await s.scalars(select(InteriorMediaTombstone.object_key))).all()
        assert len(keys) == 2
        assert all(k.startswith(f"u/{me['id']}/") for k in keys)
    assert len(store.objects) == 3  # bytes survive until the worker drains the queue
    assert await repo.drain_tombstones(async_sessionmaker(engine), store) == 2
    assert all(not k.startswith(f"u/{me['id']}/") for k in store.objects)  # only the other tester remains
    assert len(store.objects) == 1
    async with async_sessionmaker(engine)() as s:
        assert await s.scalar(select(func.count()).select_from(InteriorMediaTombstone)) == 0
