"""Race tests on real connections: the database, not Python, must serialise duplicate work (agents.md §5)."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration, pytest.mark.money]


async def test_parallel_duplicate_ledger_grants_apply_exactly_once(engine: AsyncEngine) -> None:
    user_id = str(uuid4())
    key = f"signup:{user_id}"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO app.app_user (id, email) VALUES (:i, :e)"),
            {"i": user_id, "e": f"{user_id}@example.test"},
        )

    async def grant() -> bool:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO app.credit_ledger (user_id, delta, reason, idempotency_key) "
                        "VALUES (:u, 3, 'signup_grant', :k)"
                    ),
                    {"u": user_id, "k": key},
                )
        except IntegrityError:
            return False
        return True

    try:
        results = await asyncio.gather(*(grant() for _ in range(20)))
        assert results.count(True) == 1
        async with engine.connect() as conn:
            total = await conn.scalar(
                text("SELECT sum(delta) FROM app.credit_ledger WHERE user_id = :u"), {"u": user_id}
            )
        assert total == 3
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.app_user WHERE id = :u"), {"u": user_id})


async def test_parallel_active_audits_for_the_same_listing_admit_one(engine: AsyncEngine) -> None:
    user_id, oid = str(uuid4()), "RACE001"
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO app.app_user (id, email) VALUES (:i, :e)"),
            {"i": user_id, "e": f"{user_id}@example.test"},
        )
        await conn.execute(
            text(
                "INSERT INTO app.listing (otodom_id, url, transaction) "
                "VALUES (:o, 'https://example.test/x', 'SALE') ON CONFLICT DO NOTHING"
            ),
            {"o": oid},
        )

    async def submit() -> bool:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO app.audit (user_id, otodom_id, status, charge_source, charge_state, "
                        "engine_version, schema_version) "
                        "VALUES (:u, :o, 'queued', 'credit', 'reserved', 'test', 1)"
                    ),
                    {"u": user_id, "o": oid},
                )
        except IntegrityError:
            return False
        return True

    try:
        results = await asyncio.gather(*(submit() for _ in range(10)))
        assert results.count(True) == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.app_user WHERE id = :u"), {"u": user_id})
            await conn.execute(text("DELETE FROM app.listing WHERE otodom_id = :o"), {"o": oid})
