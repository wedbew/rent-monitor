"""Seller questions persisted with the report (G-03, RM-404): real Postgres and worker path, offline.

Reuses the P0 journey harness: the API, session auth, Postgres, Procrastinate and the engine child are real;
the listing source and market context are the named fakes of `test_audit_journey`. Proves: the block is
stored once with the result and served by GET; repeated and concurrent runs never duplicate or change it;
an audit made before the block existed shows no questions; another user gets 404.
"""

# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from deal_analyzer import analyse_listing, extract_listing, seller_questions
from deal_analyzer.seller_questions import SellerQuestionBlock
from rm_worker.audit_pipeline import execute_audit
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# `clean_up` and `h` are fixtures: pytest requests them by name, so the import looks unused.
from test_audit_journey import RENT, RISK_FREE, Harness, clean_up, h, new_ref, sale_ad, submit  # noqa: F401
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]


def expected_block(ad: dict[str, Any]) -> SellerQuestionBlock:
    return seller_questions(analyse_listing(extract_listing(ad), rent=RENT, risk_free=RISK_FREE))


async def stored_block(engine: AsyncEngine, audit_id: str) -> Any:
    async with engine.connect() as conn:
        return await conn.scalar(
            text("SELECT seller_questions FROM app.audit WHERE id = :id"), {"id": UUID(audit_id)}
        )


async def test_the_block_is_stored_with_the_report_and_served_by_the_api(
    h: Harness, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    ad = sale_ad()  # no floor plan and no vision: the questions below are real gaps
    h.source.ads[ref] = ad
    audit_id = (await submit(c, ref)).json()["audit_id"]
    assert (await c.get(f"/api/audits/{audit_id}")).json()["seller_questions"] is None  # not made yet

    await h.run_worker()

    expected = expected_block(ad)
    assert [q.rule.value for q in expected.questions] == ["condition_unclear", "floor_plan_missing"]
    done = (await c.get(f"/api/audits/{audit_id}")).json()
    assert done["status"] == "succeeded_degraded"
    assert done["seller_questions"] == expected.model_dump(mode="json")
    assert await stored_block(engine, audit_id) == expected.model_dump(mode="json")
    assert (
        "seller_questions" not in done["result"]
    )  # the engine's DealAnalysis is unchanged (its schema is too)


async def test_running_the_step_again_neither_duplicates_nor_changes_the_block(
    h: Harness, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    ad = sale_ad()
    h.source.ads[ref] = ad
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker()
    first = await stored_block(engine, audit_id)

    assert await execute_audit(h.services(), UUID(audit_id)) is None  # the audit is no longer queued
    assert await stored_block(engine, audit_id) == first == expected_block(ad).model_dump(mode="json")


async def test_simultaneous_runs_of_one_audit_store_exactly_one_block(
    h: Harness, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    ad = sale_ad()
    h.source.ads[ref] = ad
    audit_id = (await submit(c, ref)).json()["audit_id"]

    results = await asyncio.gather(*(execute_audit(h.services(), UUID(audit_id)) for _ in range(3)))

    assert sum(r is not None for r in results) == 1
    assert await stored_block(engine, audit_id) == expected_block(ad).model_dump(mode="json")


async def test_an_audit_made_before_the_block_existed_shows_no_questions(
    h: Harness, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker()
    async with engine.begin() as conn:  # what an audit stored before RM-404 looks like
        await conn.execute(
            text("UPDATE app.audit SET seller_questions = NULL WHERE id = :id"), {"id": UUID(audit_id)}
        )

    old = (await c.get(f"/api/audits/{audit_id}")).json()
    assert old["status"] == "succeeded_degraded"
    assert old["seller_questions"] is None
    assert old["result"]["schema_version"] == 1


async def test_another_users_audit_has_no_questions_and_is_a_404(
    h: Harness, make_google_token: MakeToken
) -> None:
    a, _ = await sign_in(h.app, make_google_token)
    b, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    audit_id = (await submit(a, ref)).json()["audit_id"]
    await h.run_worker()

    foreign = await b.get(f"/api/audits/{audit_id}")
    unknown = await b.get(f"/api/audits/{uuid4()}")
    assert foreign.status_code == unknown.status_code == 404
    assert "seller_questions" not in foreign.text
