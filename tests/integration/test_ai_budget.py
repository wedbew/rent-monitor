"""AI budget on real Postgres: atomic holds, idempotent settle/release, sweep, warning, cap (RM-24)."""

import asyncio
import json
from datetime import timedelta
from decimal import Decimal as D
from uuid import uuid4

import httpx
import pytest
from deal_analyzer.vision import Condition  # noqa: F401  (keeps the engine import graph exercised)
from rm_core.ai_budget import (
    BudgetLevel,
    CallUsage,
    PostgresBudgetGate,
    budget_status,
    sweep_stale_reservations,
)
from rm_core.deadline import Deadline
from rm_worker.clients.openrouter import OpenRouterClient, VisionDisabled, VisionRequest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration, pytest.mark.money]


@pytest.fixture
async def sm(engine: AsyncEngine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    await _reset(engine)
    yield maker
    await _reset(engine)


async def _reset(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.ai_usage"))
        await conn.execute(text("DELETE FROM app.ai_reservation"))
        await conn.execute(text("DELETE FROM app.ai_budget"))


async def _status(sm: async_sessionmaker[AsyncSession]):
    async with sm() as s:
        return await budget_status(s)


async def test_concurrent_reservations_never_exceed_the_cap(sm) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("1.00"))
    tickets = await asyncio.gather(*(gate.reserve(D("0.30")) for _ in range(12)))
    granted = [t for t in tickets if t is not None]
    assert len(granted) == 3  # 3 x 0.30 = 0.90 fits; a fourth would reach 1.20
    status = await _status(sm)
    assert status is not None
    assert status.reserved_usd == D("0.900000")
    assert status.spent_usd == 0
    assert status.level is BudgetLevel.WARNING  # 90 % of the cap


async def test_settling_swaps_the_estimate_for_the_actual_cost_and_logs_the_usage(sm) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("10"))
    ticket = await gate.reserve(D("0.02"))
    assert ticket is not None
    audit_usage = CallUsage(model="vendor/vision-1", prompt_tokens=1200, completion_tokens=80)
    await ticket.settle(D("0.00014"), audit_usage)
    status = await _status(sm)
    assert status is not None
    assert (status.reserved_usd, status.spent_usd) == (D("0"), D("0.000140"))
    async with sm() as s:
        row = (
            await s.execute(
                text(
                    "SELECT model, prompt_tokens, completion_tokens, cost_usd, cost_estimated "
                    "FROM app.ai_usage"
                )
            )
        ).one()
    assert (row[0], row[1], row[2], row[3], row[4]) == ("vendor/vision-1", 1200, 80, D("0.000140"), False)


async def test_money_keeps_six_decimals_exactly_over_many_calls(sm) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("100"))
    for _ in range(50):
        ticket = await gate.reserve(D("0.02"))
        assert ticket is not None
        await ticket.settle(D("0.000140"))
    status = await _status(sm)
    assert status is not None
    assert status.spent_usd == D("0.007000")  # 50 x 0.00014, no float drift


async def test_settle_and_release_are_idempotent_and_exclusive(sm) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("10"))
    ticket = await gate.reserve(D("1"))
    assert ticket is not None
    await asyncio.gather(*(ticket.settle(D("0.5")) for _ in range(6)))
    await ticket.release()  # too late: it was settled
    await ticket.settle(D("9"))
    status = await _status(sm)
    assert status is not None
    assert (status.reserved_usd, status.spent_usd) == (D("0"), D("0.500000"))  # settled once, at 0.5
    async with sm() as s:
        assert await s.scalar(text("SELECT count(*) FROM app.ai_usage")) == 1


async def test_a_failed_call_releases_its_hold(sm) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("1"))
    ticket = await gate.reserve(D("0.60"))
    assert ticket is not None
    assert await gate.reserve(D("0.60")) is None  # no room while the first hold exists
    await ticket.release()
    again = await gate.reserve(D("0.60"))
    assert again is not None
    status = await _status(sm)
    assert status is not None
    assert (status.reserved_usd, status.spent_usd) == (D("0.600000"), D("0"))


async def test_the_sweep_returns_holds_left_by_crashed_workers_only(sm, engine: AsyncEngine) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("10"))
    crashed, alive = await gate.reserve(D("1.00")), await gate.reserve(D("2.00"))
    assert crashed is not None
    assert alive is not None
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE app.ai_reservation SET created_at = now() - interval '2 hours' WHERE amount_usd = 1")
        )
    count, total = await sweep_stale_reservations(sm, older_than=timedelta(minutes=30))
    assert (count, total) == (1, D("1.000000"))
    status = await _status(sm)
    assert status is not None
    assert status.reserved_usd == D("2.000000")  # only the live worker's hold remains
    await crashed.settle(D("5"))  # a late settle from the "crashed" worker must not count
    status = await _status(sm)
    assert status is not None
    assert status.spent_usd == 0
    assert await sweep_stale_reservations(sm, older_than=timedelta(minutes=30)) == (0, D("0"))


async def test_the_cap_zero_kill_switch_disables_vision_and_a_cap_change_applies_at_once(sm) -> None:
    assert await PostgresBudgetGate(sm, monthly_cap_usd=D("0")).reserve(D("0.02")) is None
    status = await _status(sm)
    assert status is not None
    assert status.level is BudgetLevel.EXHAUSTED
    assert (
        await PostgresBudgetGate(sm, monthly_cap_usd=D("5")).reserve(D("0.02")) is not None
    )  # operator raises the cap
    lowered = PostgresBudgetGate(sm, monthly_cap_usd=D("0.03"))
    assert await lowered.reserve(D("0.02")) is None  # 0.02 held + 0.02 would exceed the new cap


async def test_the_eighty_percent_warning_fires_once_and_levels_follow_usage(sm, engine: AsyncEngine) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("10"))
    for cost in ("7.9", "0.1"):
        t = await gate.reserve(D(cost))
        assert t is not None
        await t.settle(D(cost))
    status = await _status(sm)
    assert status is not None
    assert status.level is BudgetLevel.WARNING
    async with sm() as s:
        first = await s.scalar(text("SELECT warned_at FROM app.ai_budget"))
    assert first is not None
    t2 = await gate.reserve(D("0.5"))
    assert t2 is not None
    await t2.settle(D("0.5"))
    async with sm() as s:
        assert await s.scalar(text("SELECT warned_at FROM app.ai_budget")) == first  # not re-armed
    last = await gate.reserve(D("1.5"))
    assert last is not None
    await last.settle(D("1.5"))
    status = await _status(sm)
    assert status is not None
    assert status.level is BudgetLevel.EXHAUSTED  # 10.0 of 10
    assert await gate.reserve(D("0.01")) is None


async def test_an_overrun_by_the_provider_is_recorded_and_blocks_further_calls(sm) -> None:
    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("1"))
    ticket = await gate.reserve(D("0.10"))
    assert ticket is not None
    await ticket.settle(D("1.50"))  # the real cost exceeded the estimate and the cap
    status = await _status(sm)
    assert status is not None
    assert status.spent_usd == D("1.500000")
    assert await gate.reserve(D("0.01")) is None


# ---- end to end with the real vision client ----
async def test_the_vision_client_stops_calling_the_provider_when_the_budget_is_gone(sm) -> None:
    from rm_worker.images import PreparedImage  # noqa: PLC0415

    calls: list[httpx.Request] = []
    body = {
        "model": "m",
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.4},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=json.dumps(body).encode())

    class OneSlot:
        def slot(self, max_wait_s: float):
            import contextlib  # noqa: PLC0415

            return contextlib.nullcontext()

    gate = PostgresBudgetGate(sm, monthly_cap_usd=D("0.50"))
    client = OpenRouterClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)), "k", gate, OneSlot(), D("0.30")
    )
    audit = uuid4()
    req = VisionRequest(
        model="m", prompt="p", images=[PreparedImage("u", b"\xff\xd8x", 1, 1, 0)], audit_id=audit
    )
    result = await client.complete(req, deadline=Deadline.after(30))
    assert result.cost_usd == D("0.4")
    with pytest.raises(VisionDisabled):  # 0.4 spent, so 0.30 more cannot fit under 0.50
        await client.complete(req, deadline=Deadline.after(30))
    assert len(calls) == 1  # the second audit never reached the provider
    async with sm() as s:
        row = (await s.execute(text("SELECT model, prompt_tokens, cost_usd FROM app.ai_usage"))).one()
    assert (row[0], row[1], row[2]) == ("m", 5, D("0.400000"))
