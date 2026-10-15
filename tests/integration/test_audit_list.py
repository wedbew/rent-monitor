# ruff: noqa: F811  (the `app` fixture is imported from test_me_saved_admin and used as a parameter)
"""`GET /api/audits`: keyset paging, filters and tenant isolation on real Postgres (RM-265, #265).

Real: the API, session auth, Postgres. The audits are inserted directly with chosen timestamps, grades and
statuses: this proves the list contract, not the engine.
"""

import base64
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from rm_core.db.models import Audit, AuditStatus, ChargeSource, ChargeState, Listing
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_me_saved_admin import app, sign_in  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
BASE = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
CREATED: list[str] = []  # listings this module made, removed again after each test


@pytest.fixture(autouse=True)
async def clean(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.audit WHERE otodom_id = ANY(:r)"), {"r": CREATED})
        await conn.execute(text("DELETE FROM app.listing WHERE otodom_id = ANY(:r)"), {"r": CREATED})
    CREATED.clear()


async def seed(
    engine: AsyncEngine,
    user_id: str,
    n: int,
    *,
    start: datetime = BASE,
    status: AuditStatus = AuditStatus.succeeded,
    grade: str | None = "B",
    prefix: str = "PG",
    same_second: int = 0,
) -> list[UUID]:
    """`n` audits for `user_id`, one minute apart ascending from `start`. The first `same_second` share one
    timestamp, so the id tie-break is exercised. Returns the ids, oldest first."""
    ids: list[UUID] = []
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s, s.begin():
        for i in range(n):
            oid = f"{prefix}{uuid4().hex[:10]}"
            CREATED.append(oid)
            s.add(Listing(otodom_id=oid, url="https://x.test"))
            await s.flush()
            audit_id = uuid4()
            ids.append(audit_id)
            s.add(
                Audit(
                    id=audit_id,
                    user_id=user_id,
                    otodom_id=oid,
                    status=status,
                    charge_source=ChargeSource.credit,
                    charge_state=ChargeState.captured,
                    engine_version="t",
                    schema_version=1,
                    grade=grade,
                    created_at=start if i < same_second else start + timedelta(minutes=i),
                )
            )
    return ids


async def page(c: Any, **params: Any) -> dict[str, Any]:
    r = await c.get("/api/audits", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def walk(c: Any, limit: int, **filters: Any) -> list[str]:
    """Follow `next_cursor` to the end; returns every audit id in the order received."""
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(50):
        body = await page(c, limit=limit, **({"cursor": cursor} if cursor else {}), **filters)
        seen += [i["audit_id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            return seen
    raise AssertionError("the cursor never ended")


async def test_an_empty_list_is_an_empty_page(app: FastAPI, make_google_token: MakeToken) -> None:
    c, _ = await sign_in(app, make_google_token)
    assert await page(c) == {"items": [], "next_cursor": None}


async def test_120_audits_paged_at_50_return_each_row_exactly_once_newest_first(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    ids = await seed(engine, me["id"], 120, same_second=10)  # ten rows share one timestamp
    first = await page(c, limit=50)
    assert len(first["items"]) == 50
    assert first["next_cursor"] is not None
    seen = await walk(c, 50)
    assert len(seen) == 120
    assert len(set(seen)) == 120
    assert set(seen) == {str(i) for i in ids}
    rows = await c.get("/api/audits", params={"limit": 100})
    created = [i["created_at"] for i in rows.json()["items"]]
    assert created == sorted(created, reverse=True)  # newest first, ties included
    assert [len(p) for p in (seen[:50], seen[50:100], seen[100:])] == [50, 50, 20]


async def test_a_row_inserted_between_pages_neither_repeats_nor_skips_one(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    old = await seed(engine, me["id"], 30)
    one = await page(c, limit=10)
    newer = await seed(engine, me["id"], 5, start=BASE + timedelta(days=2), prefix="PN")
    rest: list[str] = []
    cursor = one["next_cursor"]
    while cursor:
        body = await page(c, limit=10, cursor=cursor)
        rest += [i["audit_id"] for i in body["items"]]
        cursor = body["next_cursor"]
    together = [i["audit_id"] for i in one["items"]] + rest
    assert len(together) == len(set(together)) == 30
    assert set(together) == {str(i) for i in old}  # the five new ones belong to the next first page
    fresh = await page(c, limit=5)
    assert {i["audit_id"] for i in fresh["items"]} == {str(i) for i in newer}


async def test_other_users_rows_never_appear_and_a_foreign_cursor_pages_only_your_own(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    a, me_a = await sign_in(app, make_google_token)
    b, me_b = await sign_in(app, make_google_token)
    theirs = await seed(engine, me_a["id"], 12)
    mine = await seed(engine, me_b["id"], 4, prefix="PB")
    assert set(await walk(b, 3)) == {str(i) for i in mine}
    cursor_of_a = (await page(a, limit=5))["next_cursor"]
    reply = await page(b, limit=50, cursor=cursor_of_a)
    got = {i["audit_id"] for i in reply["items"]}
    assert got <= {str(i) for i in mine}
    assert not got & {str(i) for i in theirs}


@pytest.mark.parametrize(
    "cursor",
    [
        "garbage",
        base64.urlsafe_b64encode(b"not json").decode(),
        base64.urlsafe_b64encode(
            json.dumps(["2026-09-01T12:00:00", str(uuid4())]).encode()
        ).decode(),  # naive
        base64.urlsafe_b64encode(json.dumps(["2026-09-01T12:00:00+00:00", "not-a-uuid"]).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"a": 1}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps(["2026-09-01T12:00:00+00:00", 5]).encode()).decode(),
    ],
)
async def test_an_invalid_cursor_is_a_422_problem(
    app: FastAPI, make_google_token: MakeToken, cursor: str
) -> None:
    c, _ = await sign_in(app, make_google_token)
    r = await c.get("/api/audits", params={"cursor": cursor})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"][0]["loc"] == ["query", "cursor"]


async def test_limit_and_filter_values_are_bounded(app: FastAPI, make_google_token: MakeToken) -> None:
    c, _ = await sign_in(app, make_google_token)
    for params in (
        {"limit": 0},
        {"limit": 101},
        {"status": "exploded"},
        {"grade": "AAA"},
        {"q": "no spaces"},
        {"q": "x" * 17},
        {"cursor": "x" * 201},
    ):
        r = await c.get("/api/audits", params=params)
        assert (r.status_code, r.json()["code"]) == (422, "VALIDATION_ERROR"), params


async def test_filters_by_status_grade_and_id_prefix_combine_with_paging(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(app, make_google_token)
    good = await seed(engine, me["id"], 7, grade="A", prefix="AA")
    mid = await seed(engine, me["id"], 5, grade="C", prefix="BB", start=BASE + timedelta(days=1))
    rejected = await seed(
        engine,
        me["id"],
        4,
        status=AuditStatus.rejected,
        grade=None,
        prefix="AA",
        start=BASE + timedelta(days=2),
    )
    failed = await seed(
        engine, me["id"], 3, status=AuditStatus.failed_upstream, grade=None, start=BASE + timedelta(days=3)
    )
    as_str = lambda ids: {str(i) for i in ids}  # noqa: E731

    assert set(await walk(c, 3, status="rejected")) == as_str(rejected)
    both = await walk(c, 4, status=["rejected", "failed_upstream"])
    assert set(both) == as_str(rejected + failed)
    assert len(both) == len(set(both))
    assert set(await walk(c, 2, grade="a")) == as_str(good)  # case-insensitive
    assert set(await walk(c, 5, grade="C")) == as_str(mid)
    assert set(await walk(c, 3, q="aa")) == as_str(good + rejected)  # prefix, any case
    assert set(await walk(c, 3, q="AA", status="succeeded")) == as_str(good)
    assert await page(c, q="ZZZ") == {"items": [], "next_cursor": None}


async def test_the_list_query_can_use_the_user_created_index(engine: AsyncEngine) -> None:
    """Without a total and with a keyset, the page is an index range scan, not a sort of the user's rows."""
    async with engine.connect() as conn:
        await conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan = (
            await conn.execute(
                text(
                    "EXPLAIN SELECT id FROM app.audit WHERE user_id = :u"
                    " AND (created_at < :t OR (created_at = :t AND id < :i))"
                    " ORDER BY created_at DESC, id DESC LIMIT 51"
                ),
                {"u": "nobody", "t": BASE, "i": uuid4()},
            )
        ).all()
    assert "ix_audit_user_created" in "\n".join(row[0] for row in plan)
