# ruff: noqa: F811  (the `app` fixture is imported from test_me_saved_admin and used as a parameter)
"""Media manifest on real Postgres: persist, retrieve, tenant isolation, expiry, cascade (RM-376, G-01a).

The table comes from migration 0014 and the router is registered in `rm_api.app.ROUTERS`.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from rm_contracts.media import MediaItem, MediaKind, MediaManifest
from rm_core.db.models import MediaEvidence
from rm_core.media import AuditNotFoundError, get_manifest, persist_manifest
from rm_core.principal import Principal
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_audit_list import CREATED, clean, seed  # noqa: F401  (clean: autouse cleanup of seeded audits)
from test_me_saved_admin import app, sign_in  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
DIGEST = "b" * 64


def stored(ordinal: int, kind: MediaKind = MediaKind.photo, **kw: object) -> MediaItem:
    return MediaItem.model_validate(
        {
            "ordinal": ordinal,
            "kind": kind.value,
            "source_type": "url",
            "state": "stored",
            "content_digest": DIGEST,
            "mime": "image/webp",
            "width": 1600,
            "height": 900,
            **kw,
        }
    )


def principal(user_id: str) -> Principal:
    return Principal(
        user_id=user_id, email="x@test", role="user", email_verified=True, session_id=1, token_hash="h"
    )


async def test_persist_and_retrieve_round_trips_25_photos_and_2_plans(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, me["id"], 1)
    items = [stored(i) for i in range(25)] + [stored(25, MediaKind.plan), stored(26, MediaKind.plan)]
    async with async_sessionmaker(engine)() as s, s.begin():
        saved = await persist_manifest(s, user_id=me["id"], audit_id=audit_id, items=items)
    r = await c.get(f"/api/audits/{audit_id}/media")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "private, no-store"
    got = MediaManifest.model_validate(r.json())
    assert got.items == items == saved.items
    assert sum(i.kind is MediaKind.plan for i in got.items) == 2


async def test_a_foreign_or_unknown_audit_is_404_and_leaks_nothing(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    _, owner = await sign_in(app, make_google_token)
    other, _ = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, owner["id"], 1)
    async with async_sessionmaker(engine)() as s, s.begin():
        await persist_manifest(s, user_id=owner["id"], audit_id=audit_id, items=[stored(0)])
    foreign = await other.get(f"/api/audits/{audit_id}/media")
    unknown = await other.get(f"/api/audits/{uuid4()}/media")
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json()["code"] == unknown.json()["code"]
    async with async_sessionmaker(engine)() as s:
        with pytest.raises(AuditNotFoundError):
            await get_manifest(s, audit_id, principal("someone-else"))
        with pytest.raises(AuditNotFoundError):
            await persist_manifest(s, user_id="someone-else", audit_id=audit_id, items=[stored(0)])


async def test_unauthenticated_is_401(app: FastAPI) -> None:
    from test_auth import client_for  # noqa: PLC0415

    r = await client_for(app).get(f"/api/audits/{uuid4()}/media")
    assert r.status_code == 401


async def test_partial_failure_and_expiry_are_explicit(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, me["id"], 1)
    past = datetime.now(UTC) - timedelta(hours=1)
    items = [
        stored(0),
        stored(1, expires_at=past),
        MediaItem.model_validate(
            {
                "ordinal": 2,
                "kind": "photo",
                "source_type": "url",
                "state": "failed",
                "failure_code": "TIMEOUT",
            }
        ),
    ]
    async with async_sessionmaker(engine)() as s, s.begin():
        await persist_manifest(s, user_id=me["id"], audit_id=audit_id, items=items)
    body = (await c.get(f"/api/audits/{audit_id}/media")).json()
    assert [i["state"] for i in body["items"]] == ["stored", "expired", "failed"]
    assert body["items"][2]["failure_code"] == "TIMEOUT"


async def test_an_audit_without_media_has_an_empty_manifest(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, me["id"], 1)
    body = (await c.get(f"/api/audits/{audit_id}/media")).json()
    assert body["items"] == []
    assert body["created_at"] is None


async def test_persist_replaces_atomically_and_rejects_oversized_input(
    engine: AsyncEngine, make_google_token: MakeToken, app: FastAPI
) -> None:
    _, me = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, me["id"], 1)
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        await persist_manifest(s, user_id=me["id"], audit_id=audit_id, items=[stored(0), stored(1)])
    async with sm() as s, s.begin():
        again = await persist_manifest(s, user_id=me["id"], audit_id=audit_id, items=[stored(0)])
    assert len(again.items) == 1
    too_many = [stored(i) for i in range(26)] + [stored(26)]
    with pytest.raises(ValueError, match="at most 25 photos"):
        async with sm() as s, s.begin():
            await persist_manifest(s, user_id=me["id"], audit_id=audit_id, items=too_many)
    async with sm() as s:
        assert await s.scalar(select(func.count()).select_from(MediaEvidence)) is not None
        assert len((await get_manifest(s, audit_id, principal(me["id"]))).items) == 1


async def test_database_rejects_a_stored_row_without_digest(
    engine: AsyncEngine, make_google_token: MakeToken, app: FastAPI
) -> None:
    from sqlalchemy.exc import IntegrityError  # noqa: PLC0415

    _, me = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, me["id"], 1)
    with pytest.raises(IntegrityError, match="stored_complete"):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO app.media_evidence (audit_id, user_id, ordinal, kind, source_type, state) "
                    "VALUES (:a, :u, 0, 'photo', 'url', 'stored')"
                ),
                {"a": audit_id, "u": me["id"]},
            )


async def test_deleting_the_audit_removes_its_media(
    engine: AsyncEngine, make_google_token: MakeToken, app: FastAPI
) -> None:
    _, me = await sign_in(app, make_google_token)
    [audit_id] = await seed(engine, me["id"], 1)
    async with async_sessionmaker(engine)() as s, s.begin():
        await persist_manifest(s, user_id=me["id"], audit_id=audit_id, items=[stored(0)])
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.audit WHERE id = :a"), {"a": audit_id})
        left = await conn.scalar(
            text("SELECT count(*) FROM app.media_evidence WHERE audit_id = :a"), {"a": audit_id}
        )
    assert left == 0
