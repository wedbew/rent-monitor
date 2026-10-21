"""Interior generation on real Postgres with the offline fake model and the real atomic AI budget (RM-450).

Every outcome is checked against the money: what is spent, what is still held, and that no path pays twice.
"""

import asyncio
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from PIL import Image
from rm_contracts.catalogue import Availability
from rm_contracts.generation import GenerationError
from rm_contracts.interior import Brief, CustomItemIn, MediaPurpose, ProjectCreate, RoomType
from rm_core import interior as repo
from rm_core import interior_generation as gen
from rm_core.ai_budget import PostgresBudgetGate
from rm_core.catalogue import CatalogueQuery, DemoCatalogue
from rm_core.db.models import (
    AiBudget,
    AiReservation,
    AiUsage,
    InteriorGeneration,
    InteriorMedia,
    User,
)
from rm_core.object_store import MemoryObjectStore, ObjectInfo
from rm_core.principal import Principal
from rm_core.settings import Settings
from rm_worker import interior_generation as flow
from rm_worker.clients.image_gen import FakeImageGenerator
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]
SETTINGS = Settings(_env_file=None, app_env="test", interior_image_provider="fake")  # pyright: ignore[reportCallIssue]
ESTIMATE = SETTINGS.interior_attempt_estimate_usd  # 0.10
COST = Decimal("0.034000")


@pytest.fixture(autouse=True)
async def clean_budget(engine: AsyncEngine) -> None:
    async with async_sessionmaker(engine)() as s, s.begin():
        await s.execute(delete(InteriorGeneration))  # recovery sweeps every stuck row, so start empty
        await s.execute(delete(AiUsage))
        await s.execute(delete(AiReservation))
        await s.execute(delete(AiBudget))


def jpeg(color: tuple[int, int, int] = (120, 90, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


class World:
    def __init__(self, engine: AsyncEngine, *, cap: str = "5") -> None:
        self.engine = engine
        self.sm = async_sessionmaker(engine)
        self.store = MemoryObjectStore()
        self.fake = FakeImageGenerator()
        self.gate = PostgresBudgetGate(self.sm, monthly_cap_usd=Decimal(cap))
        self.deps = flow.Deps(self.sm, self.store, self.fake, self.gate, SETTINGS)

    async def person(self) -> Principal:
        uid = str(uuid4())
        async with self.sm() as s, s.begin():
            s.add(User(id=uid, email=f"{uid}@example.test"))
        return Principal(uid, f"{uid}@example.test", "user", True, 1, "h")

    async def revision(
        self, who: Principal, *, notes: str | None = None, photo: bool = True
    ) -> tuple[UUID, UUID]:
        """A project with a room photo, two own items (one with a photo), a demo product and a revision."""
        async with self.sm() as s, s.begin():
            project = await repo.create_project(
                s, who, ProjectCreate(name="Salon", brief=Brief(room_type=RoomType.living_room, notes=notes))
            )
        if photo:
            await repo.upload_photo(
                self.sm,
                self.store,
                SETTINGS,
                who,
                project,
                purpose=MediaPurpose.source,
                item_id=None,
                raw=jpeg(),
            )
        async with self.sm() as s, s.begin():
            with_photo = await repo.add_item(
                s, who, project, CustomItemIn(name="Mój fotel", price_pln=Decimal("300"))
            )
            await repo.add_item(s, who, project, CustomItemIn(name="Stara lampa"))
            offer = (await DemoCatalogue().fetch("sofa-nordic", "grey")) or pytest.fail("no demo offer")
            await repo.add_selection(s, who, project, offer, 1)
        await repo.upload_photo(
            self.sm,
            self.store,
            SETTINGS,
            who,
            project,
            purpose=MediaPurpose.custom_item,
            item_id=with_photo,
            raw=jpeg((9, 9, 9)),
        )
        async with self.sm() as s, s.begin():
            revision = await repo.create_revision(s, who, project)
        return project, revision

    async def queue(self, who: Principal, project: UUID, revision: UUID, key: UUID | None = None) -> UUID:
        async with self.sm() as s, s.begin():
            generation_id, _ = await gen.create_generation(
                s, who, project, revision, SETTINGS, idempotency_key=key
            )
        return generation_id

    async def row(self, generation_id: UUID) -> InteriorGeneration:
        async with self.sm() as s:
            return await s.get_one(InteriorGeneration, generation_id)

    async def money(self) -> tuple[Decimal, Decimal]:
        async with self.sm() as s:
            budget = await s.scalar(select(AiBudget))
            return (budget.spent_usd, budget.reserved_usd) if budget else (Decimal(0), Decimal(0))


async def test_success_keeps_the_original_settles_the_provider_cost_and_counts_references(
    engine: AsyncEngine,
) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who)
    source_keys = {k: v for k, v in w.store.objects.items() if "/source/" in k}
    generation_id = await w.queue(who, project, revision)
    await flow.run_generation(w.deps, generation_id)

    row = await w.row(generation_id)
    assert (row.state, row.error_code, row.cost_usd, row.cost_estimated) == ("succeeded", None, COST, False)
    assert (row.references_used, row.references_skipped) == (
        2,
        1,
    )  # demo product + own item photo; one item has none
    assert await w.money() == (COST, Decimal(0))  # settled, nothing left held
    assert w.fake.calls == 1
    request = w.fake.requests[0]
    assert len(request.images) == 3  # the room photo first, then two references
    assert request.model == SETTINGS.interior_image_model
    assert "Mój fotel" in request.prompt
    assert "no reference image" in request.prompt  # the item without a photo is described by name only
    # the output exists as a separate render; the original photo is untouched
    async with w.sm() as s:
        out = await s.get_one(InteriorMedia, row.output_media_id)
        assert (out.purpose, out.state) == ("render", "stored")
        usage = (await s.scalars(select(AiUsage))).one()
        assert (usage.cost_usd, usage.cost_estimated) == (COST, False)
    assert {k: v for k, v in w.store.objects.items() if "/source/" in k} == source_keys
    assert len([k for k in w.store.objects if "/render/" in k]) == 1


async def test_duplicate_delivery_and_a_second_run_never_call_the_model_twice(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who)
    generation_id = await w.queue(who, project, revision)
    await asyncio.gather(*(flow.run_generation(w.deps, generation_id) for _ in range(5)))
    await flow.run_generation(w.deps, generation_id)
    assert w.fake.calls == 1
    assert await w.money() == (COST, Decimal(0))
    async with w.sm() as s:
        assert await s.scalar(select(func.count()).select_from(AiUsage)) == 1


async def test_no_budget_means_nothing_is_sent(engine: AsyncEngine) -> None:
    w = World(engine, cap="0.05")  # less than one attempt's estimate
    who = await w.person()
    project, revision = await w.revision(who)
    generation_id = await w.queue(who, project, revision)
    await flow.run_generation(w.deps, generation_id)
    row = await w.row(generation_id)
    assert (row.state, row.error_code) == ("failed", GenerationError.BUDGET_EXHAUSTED.value)
    assert w.fake.calls == 0
    assert await w.money() == (Decimal(0), Decimal(0))


@pytest.mark.parametrize(
    ("marker", "error"),
    [
        ("FAKE_NOT_REACHED", GenerationError.PROVIDER_UNAVAILABLE),
        ("FAKE_REJECT", GenerationError.PROVIDER_REJECTED),
    ],
)
async def test_a_refusal_or_unreached_provider_releases_the_hold(
    engine: AsyncEngine, marker: str, error: GenerationError
) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who, notes=marker)
    generation_id = await w.queue(who, project, revision)
    await flow.run_generation(w.deps, generation_id)
    row = await w.row(generation_id)
    assert (row.state, row.error_code, row.cost_usd) == ("failed", error.value, None)
    assert await w.money() == (Decimal(0), Decimal(0))  # not billed: released, not settled
    assert not [k for k in w.store.objects if "/render/" in k]


async def test_an_unknown_outcome_keeps_the_estimate_charged_and_is_not_retried_alone(
    engine: AsyncEngine,
) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who, notes="FAKE_UNKNOWN")
    generation_id = await w.queue(who, project, revision)
    await flow.run_generation(w.deps, generation_id)
    row = await w.row(generation_id)
    assert (row.state, row.error_code, row.cost_usd, row.cost_estimated) == (
        "failed",
        GenerationError.AMBIGUOUS.value,
        ESTIMATE,
        True,
    )
    assert await w.money() == (ESTIMATE, Decimal(0))  # the possible spend is counted, not forgotten
    await flow.run_generation(w.deps, generation_id)  # a redelivery does nothing
    assert w.fake.calls == 1
    # a deliberate new attempt is a new operation with its own reservation
    again = await w.queue(who, project, revision)
    assert again != generation_id


async def test_a_missing_reported_cost_settles_the_estimate_and_says_so(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who, notes="FAKE_NO_COST")
    generation_id = await w.queue(who, project, revision)
    await flow.run_generation(w.deps, generation_id)
    row = await w.row(generation_id)
    assert (row.state, row.cost_usd, row.cost_estimated) == ("succeeded", ESTIMATE, True)
    assert await w.money() == (ESTIMATE, Decimal(0))


async def test_an_unusable_picture_is_paid_for_but_not_stored(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who, notes="FAKE_GARBAGE")
    generation_id = await w.queue(who, project, revision)
    await flow.run_generation(w.deps, generation_id)
    row = await w.row(generation_id)
    assert (row.state, row.error_code, row.output_media_id) == (
        "failed",
        GenerationError.OUTPUT_REJECTED.value,
        None,
    )
    assert await w.money() == (COST, Decimal(0))  # the provider billed it


async def test_a_storage_failure_after_a_paid_success_is_recorded_with_its_cost(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who)
    generation_id = await w.queue(who, project, revision)

    class FlakyStore(MemoryObjectStore):
        async def put(self, key: str, data: bytes, content_type: str) -> ObjectInfo:
            if "/render/" in key:
                self.fail_next = "unavailable"
            return await super().put(key, data, content_type)

    flaky = FlakyStore()
    flaky.objects = w.store.objects
    w.deps.store = flaky
    await flow.run_generation(w.deps, generation_id)
    row = await w.row(generation_id)
    assert (row.state, row.error_code, row.cost_usd) == ("failed", GenerationError.STORAGE_FAILED.value, COST)
    assert await w.money() == (COST, Decimal(0))


async def test_a_missing_room_photo_fails_before_any_reservation(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who, photo=False)
    with pytest.raises(gen.GenerationConflictError) as err:
        await w.queue(who, project, revision)
    assert err.value.reason == "no_source_photo"
    assert await w.money() == (Decimal(0), Decimal(0))


async def test_the_shared_cap_holds_under_concurrent_operations(engine: AsyncEngine) -> None:
    w = World(engine, cap="0.25")  # room for two reservations of 0.10, not three
    queued: list[UUID] = []
    for _ in range(4):
        who = await w.person()
        project, revision = await w.revision(who)
        queued.append(await w.queue(who, project, revision))
    await asyncio.gather(*(flow.run_generation(w.deps, g) for g in queued))
    states = [(await w.row(g)).state for g in queued]
    assert states.count("succeeded") == 2
    assert states.count("failed") == 2
    assert w.fake.calls == 2
    spent, reserved = await w.money()
    assert (spent, reserved) == (COST * 2, Decimal(0))
    assert spent + reserved <= Decimal("0.25")


async def test_one_active_operation_per_project_and_idempotent_creation(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who)

    async def create(key: UUID | None) -> tuple[UUID, bool]:
        async with w.sm() as s, s.begin():
            return await gen.create_generation(s, who, project, revision, SETTINGS, idempotency_key=key)

    results = await asyncio.gather(*(create(None) for _ in range(6)), return_exceptions=True)
    ok = [r for r in results if isinstance(r, tuple)]
    assert len({r[0] for r in ok}) == 1  # one operation, however many clicks
    assert sum(1 for r in ok if r[1]) == 1
    only = ok[0][0]
    key = uuid4()
    assert (await create(key))[0] == only  # the active one is returned for the same revision
    async with w.sm() as s, s.begin():
        second = await repo.create_revision(s, who, project)
    with pytest.raises(gen.GenerationConflictError) as err:
        async with w.sm() as s, s.begin():
            await gen.create_generation(s, who, project, second, SETTINGS, idempotency_key=None)
    assert (err.value.reason, err.value.generation_id) == ("active", only)


async def test_cancel_is_queued_only_and_a_cancelled_operation_never_runs(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project, revision = await w.revision(who)
    generation_id = await w.queue(who, project, revision)
    async with w.sm() as s, s.begin():
        await gen.cancel_generation(s, who, project, generation_id)
        await gen.cancel_generation(s, who, project, generation_id)  # idempotent
    await flow.run_generation(w.deps, generation_id)
    assert (await w.row(generation_id)).state == "cancelled"
    assert w.fake.calls == 0
    assert await w.money() == (Decimal(0), Decimal(0))

    other = await w.queue(who, project, revision)
    claimed = await gen.claim(w.sm, other)
    assert claimed is not None
    with pytest.raises(gen.GenerationConflictError) as err:
        async with w.sm() as s, s.begin():
            await gen.cancel_generation(s, who, project, other)
    assert err.value.reason == "running"
    stranger = await w.person()
    with pytest.raises(repo.InteriorNotFoundError):
        async with w.sm() as s, s.begin():
            await gen.cancel_generation(s, stranger, project, other)


class Recorder:
    def __init__(self, gate: PostgresBudgetGate) -> None:
        self.gate = gate
        self.settled: list[UUID] = []
        self.released: list[UUID] = []

    async def settle(self, reservation_id: UUID, estimate: Decimal, model: str) -> None:
        from rm_core.ai_budget import CallUsage  # noqa: PLC0415

        self.settled.append(reservation_id)
        await self.gate.settle(reservation_id, estimate, CallUsage(model=model, estimated=True))

    async def release(self, reservation_id: UUID) -> None:
        self.released.append(reservation_id)
        await self.gate.release(reservation_id)


async def test_recovery_keeps_sent_spend_releases_unsent_and_closes_lost_queued(engine: AsyncEngine) -> None:
    w = World(engine)
    who = await w.person()
    project_a, revision_a = await w.revision(who)
    project_b, revision_b = await w.revision(who)
    project_c, revision_c = await w.revision(who)
    sent_id, unsent_id, lost_id = (
        await w.queue(who, project_a, revision_a),
        await w.queue(who, project_b, revision_b),
        await w.queue(who, project_c, revision_c),
    )
    # two workers "died" while running: one after the request went out, one before
    for generation_id, was_sent in ((sent_id, True), (unsent_id, False)):
        claimed = await gen.claim(w.sm, generation_id)
        assert claimed is not None
        ticket = await w.gate.reserve(ESTIMATE)
        assert ticket is not None
        await gen.record_reservation(w.sm, generation_id, ticket.reservation_id)
        if was_sent:
            await gen.mark_sent(w.sm, generation_id)
    async with w.sm() as s, s.begin():  # their deadlines passed; the third was never picked up
        await s.execute(
            update(InteriorGeneration).values(deadline_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    recorder = Recorder(w.gate)
    closed = await flow.reconcile(w.sm, recorder)
    assert closed == 3
    assert len(recorder.settled) == 1
    assert len(recorder.released) == 1
    sent_row, unsent_row, lost_row = await w.row(sent_id), await w.row(unsent_id), await w.row(lost_id)
    assert (sent_row.state, sent_row.error_code, sent_row.cost_usd, sent_row.cost_estimated) == (
        "failed",
        "TIMEOUT",
        ESTIMATE,
        True,
    )
    assert (unsent_row.state, unsent_row.cost_usd) == ("failed", None)
    assert (lost_row.state, lost_row.error_code) == ("failed", "TIMEOUT")
    assert await w.money() == (ESTIMATE, Decimal(0))  # only the possibly-sent request stays charged
    assert await flow.reconcile(w.sm, recorder) == 0  # idempotent
    # a late worker that wakes up cannot resurrect a closed operation
    await flow.run_generation(w.deps, sent_id)
    assert w.fake.calls == 0


async def test_the_attempt_cap_is_a_setting_that_cannot_be_exceeded_by_its_estimate() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            interior_attempt_estimate_usd=Decimal("0.60"),
            interior_attempt_cap_usd=Decimal("0.50"),
        )
    with pytest.raises(ValueError, match="refused in production"):
        Settings(_env_file=None, interior_image_provider="fake", app_env="production")  # pyright: ignore[reportCallIssue]
    assert SETTINGS.interior_attempt_cap_usd == Decimal("0.50")
    assert Availability.in_stock.value == "in_stock" and CatalogueQuery().limit == 24  # noqa: PT018
