"""The engine child process (#186): same answer as in-process, and always killable.

No database: this is the process boundary. The stand-in engines (`tests/engine_targets.py`) hang, spawn a
grandchild, balloon, crash and lie; each must end the call promptly and leave no process behind.
"""

import asyncio
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import pytest
from deal_analyzer import FractionalOwnershipError, RentInput, analyse_listing, extract_listing
from rm_worker.engine_child import ChildEngine, EngineChildError
from test_audit_journey import sale_ad

pytestmark = [pytest.mark.integration]
RENT = RentInput(monthly_rent_pln=Decimal("2600"), basis="asking", comparables=14)
RISK_FREE = Decimal("0.055")
TESTS_DIR = str(Path(__file__).resolve().parent.parent)


@pytest.fixture(autouse=True)
def child_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("PYTHONPATH", TESTS_DIR)  # the child imports tests/engine_targets.py
    pid_file = tmp_path / "pids"
    monkeypatch.setenv("ENGINE_PID_FILE", str(pid_file))
    return pid_file


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def gone(pids: list[int], within_s: float = 5.0) -> bool:
    end = time.monotonic() + within_s
    while time.monotonic() < end:
        if not any(alive(p) for p in pids):
            return True
        await asyncio.sleep(0.05)
    return False


def pids_in(path: Path) -> list[int]:
    return [int(x) for x in path.read_text().split()] if path.exists() else []


async def run(engine: ChildEngine, timeout_s: float = 30.0) -> object:
    listing = extract_listing(sale_ad())
    return await engine.run(listing, rent=RENT, risk_free=RISK_FREE, timeout_s=timeout_s)


async def test_the_child_returns_exactly_what_the_in_process_engine_returns() -> None:
    listing = extract_listing(sale_ad())
    in_process = analyse_listing(listing, rent=RENT, risk_free=RISK_FREE)
    from_child = await run(ChildEngine())
    assert from_child == in_process  # byte-identical money: Decimal both ways (invariant 4)
    assert from_child.model_dump_json() == in_process.model_dump_json()  # type: ignore[attr-defined]


async def test_a_hung_engine_is_killed_at_the_deadline(child_env: Path) -> None:
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await run(ChildEngine(target="engine_targets:hang"), timeout_s=1.5)
    assert time.monotonic() - started < 6
    pids = pids_in(child_env)
    assert pids
    assert await gone(pids)


async def test_the_whole_process_group_dies_not_only_the_child(child_env: Path) -> None:
    with pytest.raises(TimeoutError):
        await run(ChildEngine(target="engine_targets:hang_with_grandchild"), timeout_s=2.0)
    pids = pids_in(child_env)
    assert len(pids) == 2  # the child and its grandchild
    assert await gone(pids)


async def test_cancelling_the_call_kills_the_child(child_env: Path) -> None:
    """A deploy restart or worker shutdown cancels the audit task: no orphan keeps running."""
    task = asyncio.create_task(run(ChildEngine(target="engine_targets:hang")))
    for _ in range(100):
        if pids_in(child_env):
            break
        await asyncio.sleep(0.1)
    pids = pids_in(child_env)
    assert pids
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await gone(pids)


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is enforced on Linux (the production host)")
async def test_a_runaway_allocation_ends_the_child_not_the_worker() -> None:
    with pytest.raises(EngineChildError):
        await run(ChildEngine(memory_mb=1024, target="engine_targets:balloon"))


async def test_a_crashing_child_is_an_engine_error() -> None:
    with pytest.raises(EngineChildError):
        await run(ChildEngine(target="engine_targets:crash"))


async def test_garbage_output_is_rejected_not_trusted() -> None:
    with pytest.raises(EngineChildError):
        await run(ChildEngine(target="engine_targets:garbage"))


async def test_fractional_ownership_keeps_its_type_across_the_process_boundary() -> None:
    with pytest.raises(FractionalOwnershipError) as caught:
        await run(ChildEngine(target="engine_targets:fractional"))
    assert caught.value.otodom_id == "ID1"
    assert caught.value.evidence == ("udział",)
