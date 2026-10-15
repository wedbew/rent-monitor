# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
"""The vision and OCR stages inside the audit pipeline, on real Postgres and the real engine child (#211).

Real: the API, Postgres, the Procrastinate worker, the killable engine child, the ledger, SSE events.
Faked, by name: the vision provider (a hand-built answer, no images, no model) and the market context.
Evidence class: offline. It proves the wiring, the clamp and the degrade/fail paths; it is NOT evidence about
any real model or photo (L-003, docs/STATUS.md level 3).
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from deal_analyzer import Listing
from deal_analyzer.vision import Condition, PhotoAssessment, PhotoKind, VisionOutput
from rm_core.deadline import Deadline
from rm_worker.vision_stage import PROMPT_VERSION, VisionAssessment
from test_audit_journey import SIGNUP_CREDITS, Harness, MakeToken, clean_up, h, new_ref, sale_ad, submit  # noqa: F401
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
PLAN = {"large": "https://ireland.apollo.olxcdn.com/v1/files/plan"}


@dataclass
class FakeVision:
    answer: VisionOutput | None = None
    calls: list[str] = field(default_factory=list[str])
    error: Exception | None = None

    async def assess(
        self, listing: Listing, *, audit_id: UUID, deadline: Deadline
    ) -> VisionAssessment | None:
        self.calls.append(listing.otodom_id)
        if self.error is not None:
            raise self.error
        return (
            None
            if self.answer is None
            else VisionAssessment(self.answer, "vendor/test-model", PROMPT_VERSION)
        )


def answer(**over: Any) -> VisionOutput:
    base: dict[str, Any] = {
        "condition": Condition.RENOVATION,
        "photos": (PhotoAssessment(kind=PhotoKind.INTERIOR), PhotoAssessment(kind=PhotoKind.RENDER)),
        "capex_adjustment": Decimal("0.05"),
        "rent_adjustment": Decimal("-0.02"),
    }
    return VisionOutput(**(base | over))


async def run(h: Harness, c: Any, ref: str, vision: FakeVision | None) -> tuple[dict[str, Any], str]:
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker(services=h.services(vision=vision))
    got = (await c.get(f"/api/audits/{audit_id}")).json()
    events = (await c.get(f"/api/audits/{audit_id}/events")).text
    return got, events


def stages(events: str) -> list[str]:
    return re.findall(r'"stage":\s*"([a-z]+)"', events)


async def test_with_a_vision_answer_the_audit_succeeds_undegraded_and_records_it(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    vision = FakeVision(answer())

    got, events = await run(h, c, ref, vision)

    assert (got["status"], got["error_code"], got["charge_state"]) == ("succeeded", None, "captured")
    assert "vision_unavailable" not in got["result"]["warnings"]
    record = got["result"]["vision"]
    assert record["condition"] == "renovation"
    assert (record["photos_total"], record["photos_excluded"]) == (2, 1)  # the render is never evidence
    assert record["model"] == "vendor/test-model"
    assert record["prompt_version"] == PROMPT_VERSION
    assert len(vision.calls) == 1  # called once, after context
    assert stages(events)[:5] == ["fetch", "extract", "context", "vision", "synthesize"]  # no plans: no ocr
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
    await h.assert_ledger_consistent()


async def test_floor_plans_add_the_ocr_stage(h: Harness, make_google_token: MakeToken) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad(floorPlans=[PLAN])
    got, events = await run(h, c, ref, FakeVision(answer(floor_plan_text="Salon 20 m2")))
    assert got["status"] == "succeeded"
    assert stages(events)[:6] == ["fetch", "extract", "context", "vision", "ocr", "synthesize"]


async def test_an_extreme_model_proposal_is_clamped_to_15_percent_through_the_child(
    h: Harness, make_google_token: MakeToken
) -> None:
    """Invariant 4: the model proposes, deterministic Python disposes (+/-15 %)."""
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    got, _ = await run(
        h, c, ref, FakeVision(answer(capex_adjustment=Decimal("9"), rent_adjustment=Decimal("-9")))
    )
    record = got["result"]["vision"]
    assert Decimal(record["capex"]["proposed"]) == Decimal(9)
    assert Decimal(record["capex"]["applied"]) == Decimal("0.15")
    assert record["capex"]["clamped"] is True
    assert Decimal(record["rent"]["applied"]) == Decimal("-0.15")


async def test_the_same_vision_answer_gives_a_byte_identical_result(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    results = []
    for _ in range(2):
        ref = new_ref()
        h.source.ads[ref] = sale_ad()
        got, _ = await run(h, c, ref, FakeVision(answer()))
        results.append(got["result"]["cash_flow"]["returns"])
    assert results[0] == results[1]


@pytest.mark.parametrize("vision", [None, FakeVision(answer=None)], ids=["stage_off", "no_assessment"])
async def test_without_an_assessment_the_audit_is_degraded_but_still_charged(
    h: Harness, make_google_token: MakeToken, vision: FakeVision | None
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    got, events = await run(h, c, ref, vision)
    assert (got["status"], got["error_code"], got["charge_state"]) == (
        "succeeded_degraded",
        "VISION_UNAVAILABLE",
        "captured",
    )
    assert "vision_unavailable" in got["result"]["warnings"]
    assert got["result"]["vision"] is None
    assert "synthesize" in stages(events)
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1


async def test_a_crashing_vision_provider_fails_the_audit_and_releases_the_credit(
    h: Harness, make_google_token: MakeToken
) -> None:
    """A bug in the stage must not charge for a result that was never produced."""
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    got, _ = await run(h, c, ref, FakeVision(error=RuntimeError("boom")))
    assert (got["status"], got["charge_state"]) == ("failed_internal", "released")
    assert await h.balance(me["id"]) == SIGNUP_CREDITS


@pytest.mark.parametrize(
    "ad",
    [sale_ad(adCategory={"type": "RENT"}), sale_ad(title="Sprzedam 1/2 udziału w mieszkaniu")],
    ids=["rent", "fraction"],
)
async def test_invariant_no_vision_call_for_a_listing_that_is_not_a_deal(
    h: Harness, make_google_token: MakeToken, ad: dict[str, Any]
) -> None:
    """Invariants 1 and 5: a RENT or fractional listing ends before any photo is downloaded or sent."""
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = ad
    vision = FakeVision(answer())
    got, _ = await run(h, c, ref, vision)
    assert got["status"] == "rejected"
    assert vision.calls == []
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
