"""The OpenRouter-backed vision and OCR stage (#244): offline, with a fake OpenRouter and a mock image host.

Every failure must come back as `None` (the audit degrades); nothing here may raise.
"""

import io
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from PIL import Image
from rm_core.deadline import Deadline
from rm_worker.clients.openrouter import VisionRequest, VisionResult, VisionUnavailable
from rm_worker.vision_stage import (
    ENGINE_RESERVE_S,
    OpenRouterVisionStage,
    ad_media,
)

HOSTS = ("olxcdn.com",)
PHOTO = "https://img.olxcdn.com/photo-{n}.jpg"
PLAN = "https://img.olxcdn.com/plan-1.jpg"
GOOD = '{"condition": "good", "photos": [{"kind": "interior"}], "capex_adjustment": 0.5}'


def jpeg(seed: int) -> bytes:
    img = Image.new("RGB", (64, 64))
    px = img.load()
    assert px is not None
    for x in range(64):
        for y in range(64):
            px[x, y] = ((x * seed * 7) % 256, (y * (seed + 3) * 5) % 256, (x * y + seed * 31) % 256)
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


class FakeOpenRouter:
    def __init__(self, *answers: str | Exception) -> None:
        self.answers = list(answers)
        self.requests: list[VisionRequest] = []

    async def complete(self, req: VisionRequest, *, deadline: Deadline) -> VisionResult:
        self.requests.append(req)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return VisionResult(answer, "vendor/v1", 10, 5, Decimal("0.001"))


class Progress:
    def __init__(self) -> None:
        self.stages: list[str] = []

    async def __call__(self, stage: str, message: str) -> None:
        self.stages.append(stage)


def stage(or_client: FakeOpenRouter, *, enabled: bool = True, seen: list[str] | None = None) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(request.url))
        n = int(str(request.url).rsplit("-", 1)[-1].split(".")[0])
        return httpx.Response(200, content=jpeg(n))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenRouterVisionStage(
        openrouter=or_client,  # type: ignore[arg-type]
        images_http=http,
        model="vendor/v1",
        host_suffixes=HOSTS,
        enabled=enabled,
    )


def ad(photos: int = 2, plans: int = 0) -> dict[str, Any]:
    return {
        "images": [
            {"large": PHOTO.format(n=n), "small": "https://x.test/s.jpg"} for n in range(1, photos + 1)
        ],
        "floorPlan": [PLAN] * plans,
    }


async def assess(s: Any, advert: object, remaining_s: float = 600.0) -> Any:
    return await s.assess(advert, audit_id=uuid4(), deadline=Deadline.after(remaining_s), progress=Progress())


def test_ad_media_reads_strings_and_dicts_and_applies_the_limits() -> None:
    urls = [f"https://img.olxcdn.com/p-{n}.jpg" for n in range(40)]
    photos, plans = ad_media({"images": urls, "floorPlan": [PLAN, PLAN, "https://img.olxcdn.com/b.jpg", "x"]})
    assert len(photos) == 25
    assert plans == [PLAN, "https://img.olxcdn.com/b.jpg", "x"][:2]
    assert ad_media({"images": [{"medium": "https://a/b.jpg"}, {"nope": 1}, 3, None]})[0] == [
        "https://a/b.jpg"
    ]


@pytest.mark.parametrize("bad", [None, [], "text", {"images": "no"}, {"images": [1, 2]}, {}])
def test_ad_media_survives_any_shape(bad: object) -> None:
    assert ad_media(bad) == ([], [])


async def test_photos_are_assessed_and_the_answer_is_typed() -> None:
    fake = FakeOpenRouter(GOOD)
    progress = Progress()
    result = await stage(fake).assess(ad(), audit_id=uuid4(), deadline=Deadline.after(600), progress=progress)
    assert result is not None
    assert result.output.condition == "good"
    assert result.model == "vendor/v1"
    assert len(fake.requests) == 1
    assert len(fake.requests[0].images) == 2
    assert fake.requests[0].json_mode is True
    assert progress.stages == ["vision"]


async def test_floor_plans_are_transcribed_after_the_photos() -> None:
    fake = FakeOpenRouter(GOOD, "Salon 20 m2\x00\nSypialnia 12 m2")
    progress = Progress()
    result = await stage(fake).assess(
        ad(plans=1), audit_id=uuid4(), deadline=Deadline.after(600), progress=progress
    )
    assert result is not None
    assert result.output.floor_plan_text == "Salon 20 m2\nSypialnia 12 m2"
    assert progress.stages == ["vision", "ocr"]
    assert result.output.condition == "good"


async def test_a_failed_ocr_keeps_the_photo_assessment() -> None:
    fake = FakeOpenRouter(GOOD, VisionUnavailable("down"))
    result = await assess(stage(fake), ad(plans=1))
    assert result is not None
    assert result.output.floor_plan_text is None


@pytest.mark.parametrize(
    "answer",
    [VisionUnavailable("budget"), "not json", '{"condition": "castle"}', RuntimeError("boom")],
)
async def test_provider_and_parse_failures_degrade_instead_of_raising(answer: str | Exception) -> None:
    assert await assess(stage(FakeOpenRouter(answer)), ad()) is None


async def test_no_photos_means_no_download_and_no_call() -> None:
    fake, seen = FakeOpenRouter(), []
    assert await assess(stage(fake, seen=seen), {"images": []}) is None
    assert fake.requests == []
    assert seen == []


async def test_the_kill_switch_sends_nothing() -> None:
    fake, seen = FakeOpenRouter(), []
    assert await assess(stage(fake, enabled=False, seen=seen), ad()) is None
    assert fake.requests == []
    assert seen == []


async def test_photos_on_a_foreign_host_are_never_fetched() -> None:
    fake, seen = FakeOpenRouter(), []
    advert = {"images": ["https://evil.test/a-1.jpg", "http://img.olxcdn.com/a-2.jpg"]}
    assert await assess(stage(fake, seen=seen), advert) is None
    assert fake.requests == []
    assert seen == []


async def test_no_time_left_for_the_stage_skips_it() -> None:
    fake = FakeOpenRouter(GOOD)
    assert await assess(stage(fake), ad(), remaining_s=ENGINE_RESERVE_S + 1) is None
    assert fake.requests == []
