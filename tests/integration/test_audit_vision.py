# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
"""Vision and OCR in the audit pipeline (#244), offline: a fake assessor stands in for OpenRouter.

Real: API, Postgres, ledger, Procrastinate worker, the engine child process. Faked, by name: the listing
source, the market context and the vision assessor (`FakeVision`). This proves the wiring and the degrade
rules, not that any vision provider works (docs/STATUS.md levels 3 and 4).
"""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from deal_analyzer import VisionOutput, parse_vision_output
from rm_core.deadline import Deadline
from rm_worker.engine_child import ChildEngine
from rm_worker.vision_stage import VisionAssessment
from sqlalchemy import text
from test_audit_journey import (  # noqa: F401  (fixtures: `h`, the autouse `clean_up`)
    Harness,
    MakeToken,
    clean_up,
    h,
    new_ref,
    sale_ad,
    submit,
)
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
ANSWER = '{"condition": "renovation", "photos": [{"kind": "interior"}], "capex_adjustment": 0.9}'


class FakeVision:
    def __init__(self, output: VisionOutput | None = None, fail: Exception | None = None) -> None:
        self.output, self.fail = output, fail
        self.calls: list[object] = []

    async def assess(
        self,
        ad: Any,
        *,
        audit_id: UUID,
        deadline: Deadline,
        progress: Callable[[str, str], Awaitable[None]],
    ) -> VisionAssessment | None:
        self.calls.append(ad)
        if self.fail is not None:
            raise self.fail
        if self.output is None:
            return None
        await progress("vision", "1 photos")
        await progress("ocr", "1 floor plans")
        return VisionAssessment(self.output, model="vendor/vision-1")


async def run_one(h: Harness, make_google_token: MakeToken, vision: FakeVision) -> tuple[dict[str, Any], str]:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    audit_id = (await submit(c, ref)).json()["audit_id"]
    services = replace(h.services(), engine=ChildEngine(), vision=vision)
    await h.run_worker(services=services)
    got = (await c.get(f"/api/audits/{audit_id}")).json()
    assert await h.balance(me["id"]) == 2  # 3 sign-up credits, one spent either way (captured)
    await h.assert_ledger_consistent()
    return got, audit_id


async def test_a_vision_answer_reaches_the_engine_and_is_clamped(
    h: Harness, make_google_token: MakeToken
) -> None:
    vision = FakeVision(parse_vision_output(ANSWER))
    got, audit_id = await run_one(h, make_google_token, vision)
    assert got["status"] == "succeeded"
    assert got["error_code"] is None
    assert got["charge_state"] == "captured"
    record = got["result"]["vision"]
    assert record["model"] == "vendor/vision-1"
    assert record["condition"] == "renovation"
    assert Decimal(record["capex"]["proposed"]) == Decimal("0.9")
    assert Decimal(record["capex"]["applied"]) == Decimal("0.15")  # clamped to +15 % (invariant 4)
    assert record["capex"]["clamped"] is True
    assert "vision_unavailable" not in got["result"]["warnings"]
    assert len(vision.calls) == 1
    async with h.sm() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT stage, payload FROM app.audit_event"
                    " WHERE audit_id = :a AND stage IN ('vision','ocr')"
                ),
                {"a": audit_id},
            )
        ).all()
    assert sorted(r.stage for r in rows) == ["ocr", "vision"]
    assert all(r.payload["legal_tags"] == ["images", "processor"] for r in rows)


async def test_no_vision_answer_degrades_and_still_captures(h: Harness, make_google_token: MakeToken) -> None:
    got, _ = await run_one(h, make_google_token, FakeVision(None))
    assert (got["status"], got["error_code"], got["charge_state"]) == (
        "succeeded_degraded",
        "VISION_UNAVAILABLE",
        "captured",
    )
    assert got["result"]["vision"] is None


async def test_a_crashing_vision_stage_never_fails_the_audit(
    h: Harness, make_google_token: MakeToken
) -> None:
    got, _ = await run_one(h, make_google_token, FakeVision(fail=RuntimeError("boom")))
    assert (got["status"], got["error_code"]) == ("succeeded_degraded", "VISION_UNAVAILABLE")
