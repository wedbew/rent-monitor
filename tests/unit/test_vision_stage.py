"""The vision/OCR stage against a fake image host and a fake model: no network, no key (#211).

Evidence class: offline fakes. It proves the stage's behaviour and its failure paths; it says nothing about
how good a real model's answers are (L-003, #94).
"""

import asyncio
import io
import json
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from deal_analyzer import Listing
from deal_analyzer.vision import Condition, PhotoKind
from PIL import Image
from rm_core.deadline import Deadline
from rm_worker.clients.openrouter import VisionDisabled, VisionRequest, VisionResult, VisionUnavailable
from rm_worker.vision_stage import PROMPT_VERSION, OpenRouterVision

HOSTS = ("olxcdn.com",)
CDN = "https://ireland.apollo.olxcdn.com/v1/files/"
ANSWER = {
    "condition": "refresh",
    "photos": [{"kind": "interior"}, {"kind": "render"}, {"kind": "floor_plan"}],
    "capex_adjustment": 0.4,
    "rent_adjustment": -0.05,
    "floor_plan_text": "Salon 20 m2, sypialnia 12 m2",
    "notes": "Fresh paint, old bathroom.",
}


def jpeg(seed: int) -> bytes:
    img = Image.new("RGB", (320, 240))
    px = img.load()
    assert px is not None
    for x in range(320):
        for y in range(240):
            px[x, y] = ((x * seed) % 256, (y * (seed + 3)) % 256, ((x * y) // (seed + 1)) % 256)
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


def listing(photos: tuple[str, ...], plans: tuple[str, ...] = ()) -> Listing:
    return Listing(
        otodom_id="IDTEST01",
        title="Mieszkanie przy ulicy Tajnej 5, tel. 600 000 000",
        description="Prywatny opis z numerem telefonu.",
        kind="SALE",
        price_pln=Decimal(450000),
        area_m2=Decimal(48),
        rooms=2,
        city="Testowo",
        photo_urls=photos,
        floor_plan_urls=plans,
    )


@dataclass
class FakeHost:
    files: dict[str, bytes]
    requested: list[str] = field(default_factory=list[str])

    def client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requested.append(str(request.url))
            body = self.files.get(str(request.url))
            return httpx.Response(200, content=body) if body is not None else httpx.Response(404)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@dataclass
class FakeModel:
    content: str = json.dumps(ANSWER)
    model: str = "google/gemini-test"
    error: Exception | None = None
    delay_s: float = 0.0
    requests: list[VisionRequest] = field(default_factory=list[VisionRequest])

    async def complete(self, req: VisionRequest, *, deadline: Deadline) -> VisionResult:
        self.requests.append(req)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return VisionResult(self.content, self.model, 100, 50, Decimal("0.001"))


def stage(host: FakeHost, model: FakeModel, **kw: object) -> OpenRouterVision:
    return OpenRouterVision(
        model,
        host.client(),
        model="configured/model",
        image_hosts=HOSTS,
        **kw,  # type: ignore[arg-type]
    )


async def assess(s: OpenRouterVision, item: Listing):
    return await s.assess(item, audit_id=uuid4(), deadline=Deadline.after(60))


def files(*names: str) -> dict[str, bytes]:
    return {CDN + n: jpeg(i + 2) for i, n in enumerate(names)}


async def test_photos_and_plans_become_a_typed_assessment() -> None:
    host, model = FakeHost(files("a", "b", "plan")), FakeModel()
    got = await assess(stage(host, model), listing((CDN + "a", CDN + "b"), (CDN + "plan",)))
    assert got is not None
    assert got.output.condition == Condition.REFRESH
    assert [p.kind for p in got.output.photos] == [PhotoKind.INTERIOR, PhotoKind.RENDER, PhotoKind.FLOOR_PLAN]
    assert got.output.capex_adjustment == Decimal("0.4")  # kept as proposed: the engine clamps it, not us
    assert got.output.floor_plan_text == "Salon 20 m2, sypialnia 12 m2"
    assert (got.model, got.prompt_version) == ("google/gemini-test", PROMPT_VERSION)

    (req,) = model.requests
    assert req.model == "configured/model"
    assert req.json_mode is True
    assert [i.source_url for i in req.images] == [CDN + "a", CDN + "b", CDN + "plan"]  # photos, then plans
    assert "2 photo(s)" in req.prompt
    assert "1 floor plan" in req.prompt


async def test_nothing_from_the_listing_text_reaches_the_model() -> None:
    host, model = FakeHost(files("a")), FakeModel()
    await assess(stage(host, model), listing((CDN + "a",)))
    (req,) = model.requests
    sent = (req.prompt + (req.system or "")).lower()
    for private in ("tajnej", "600 000 000", "prywatny", "testowo", "idtest01"):
        assert private not in sent  # GDPR[processor]: images plus a fixed prompt only


async def test_the_exif_of_a_photo_never_leaves_the_worker() -> None:
    img = Image.new("RGB", (320, 240), (200, 10, 10))
    exif = Image.Exif()
    exif[0x010F] = "SECRET-CAMERA-MAKER"
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    host, model = FakeHost({CDN + "a": out.getvalue()}), FakeModel()
    await assess(stage(host, model), listing((CDN + "a",)))
    (req,) = model.requests
    assert b"SECRET-CAMERA-MAKER" not in req.images[0].jpeg


async def test_a_host_outside_the_allow_list_is_never_requested() -> None:
    host, model = FakeHost({**files("a"), "https://evil.test/x.jpg": jpeg(5)}), FakeModel()
    got = await assess(
        stage(host, model), listing((CDN + "a", "https://evil.test/x.jpg", "http://" + CDN[8:] + "a"))
    )
    assert got is not None
    assert host.requested == [CDN + "a"]  # not evil.test, not plain http
    assert len(model.requests[0].images) == 1


async def test_near_duplicate_photos_are_sent_once() -> None:
    same = jpeg(7)
    host = FakeHost({CDN + "a": same, CDN + "b": same, CDN + "c": jpeg(40)})
    model = FakeModel()
    await assess(stage(host, model), listing((CDN + "a", CDN + "b", CDN + "c")))
    assert len(model.requests[0].images) == 2


async def test_at_most_25_photos_and_2_plans_are_used() -> None:
    names = [f"photo{n}" for n in range(30)] + ["plan1", "plan2", "plan3"]
    host, model = FakeHost({CDN + n: jpeg(n_ + 2) for n_, n in enumerate(names)}), FakeModel()
    await assess(
        stage(host, model),
        listing(tuple(CDN + f"photo{n}" for n in range(30)), tuple(CDN + f"plan{n}" for n in (1, 2, 3))),
    )
    assert len([u for u in host.requested if "photo" in u]) == 25
    assert len([u for u in host.requested if "plan" in u]) == 2


async def test_the_switch_off_makes_no_download_and_no_model_call() -> None:
    host, model = FakeHost(files("a")), FakeModel()
    assert await assess(stage(host, model, enabled=False), listing((CDN + "a",))) is None
    assert host.requested == []
    assert model.requests == []


@pytest.mark.parametrize(
    "item",
    [listing(()), listing((CDN + "missing",)), listing(("https://evil.test/a.jpg",))],
    ids=["no_urls", "all_404", "all_blocked"],
)
async def test_no_usable_image_means_no_model_call(item: Listing) -> None:
    host, model = FakeHost({}), FakeModel()
    assert await assess(stage(host, model), item) is None
    assert model.requests == []


@pytest.mark.parametrize(
    "error",
    [VisionDisabled("AI budget exhausted"), VisionUnavailable("provider down")],
    ids=["budget", "provider"],
)
async def test_budget_and_provider_failures_degrade_instead_of_failing(error: Exception) -> None:
    host, model = FakeHost(files("a")), FakeModel(error=error)
    assert await assess(stage(host, model), listing((CDN + "a",))) is None


@pytest.mark.parametrize(
    "content",
    ["", "not json", "[]", '{"condition": "perfect"}', '{"capex_adjustment": 99}', "NaN", '{"photos": 5}'],
)
async def test_an_unusable_answer_degrades(content: str) -> None:
    host, model = FakeHost(files("a")), FakeModel(content=content)
    assert await assess(stage(host, model), listing((CDN + "a",))) is None


async def test_a_fenced_answer_is_accepted() -> None:
    host, model = FakeHost(files("a")), FakeModel(content="```json\n" + json.dumps(ANSWER) + "\n```")
    assert await assess(stage(host, model), listing((CDN + "a",))) is not None


async def test_a_slow_model_hits_the_stage_deadline_and_degrades() -> None:
    host, model = FakeHost(files("a")), FakeModel(delay_s=5.0)
    assert await assess(stage(host, model, budget_s=0.2), listing((CDN + "a",))) is None


async def test_a_hostile_model_id_is_reduced_to_id_characters() -> None:
    host, model = FakeHost(files("a")), FakeModel(model="evil\nmodel <script>/x")
    got = await assess(stage(host, model), listing((CDN + "a",)))
    assert got is not None
    assert got.model == "evilmodelscript/x"
    assert "\n" not in got.model
