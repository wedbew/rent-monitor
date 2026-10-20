# ruff: noqa: F811, F401  (the db fixtures are imported and used as parameters)
"""Every API operation, in-process: real API, Postgres, session auth, ledger, worker and engine, with fakes
for providers (#263). Each scenario's answer is checked against `docs/openapi.json`.

Evidence class: offline fake provider data (docs/STATUS.md level 2). Nothing here says anything about Otodom,
OpenRouter, Paddle or Google.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from contract import check, load_spec, operations
from db_fixtures import engine, migrated_url, pg_url, procrastinate_schema, template_url
from rm_core.ledger import ledger_mismatches, lot_mismatches
from scenarios import Scenario, all_scenarios
from world import Exchange, World

pytestmark = [pytest.mark.integration]
SPEC = load_spec()
OPS = operations(SPEC)
RESULTS: dict[str, Exchange] = {}

# (status, error_code, charge_state) of the audit each GET /api/audits/{id} scenario ends with.
AUDIT_OUTCOMES = {
    "succeeded_warszawa": ("succeeded", None, "captured"),
    "succeeded_krakow": ("succeeded", None, "captured"),
    "succeeded_lodz": ("succeeded", None, "captured"),
    "succeeded_gdansk": ("succeeded", None, "captured"),
    "succeeded_torun": ("succeeded", None, "captured"),
    "succeeded_degraded": ("succeeded_degraded", "VISION_UNAVAILABLE", "captured"),
    "rejected_rent_is_not_a_deal": ("rejected", "RENT_NOT_DEAL", "released"),
    "rejected_fractional_ownership": ("rejected", "FRACTIONAL_OWNERSHIP", "released"),
    "failed_upstream_blocked": ("failed_upstream", "UPSTREAM_BLOCKED", "released"),
    "failed_input_listing_gone": ("failed_input", "LISTING_GONE", "released"),
    "queued_not_yet_run": ("queued", None, "reserved"),
}


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def world(migrated_url: str, procrastinate_schema: None) -> AsyncIterator[World]:
    async with World(migrated_url, transport="asgi").running() as w:
        yield w


@pytest.mark.parametrize("s", all_scenarios(), ids=lambda s: s.id)
async def test_scenario(world: World, s: Scenario) -> None:
    exchange = await s.run(world)
    RESULTS[s.id] = exchange
    assert check(SPEC, OPS[s.key], exchange, s.status) == []  # no gap between the document and the answer
    if s.key == "GET /api/audits/{audit_id}" and s.name in AUDIT_OUTCOMES:
        body = exchange.body
        assert (body["status"], body["error_code"], body["charge_state"]) == AUDIT_OUTCOMES[s.name]


def _results(prefix: str) -> list[dict[str, Any]]:
    wanted = [
        r.body for sid, r in RESULTS.items() if sid.startswith("GET /api/audits/{audit_id} :: " + prefix)
    ]
    if not wanted:
        pytest.skip("scenarios were not run in this session")
    return wanted


def test_five_succeeded_audits_are_distinct() -> None:
    """The listings differ in city, size, price, admin fee and photo count: so must the results."""
    done = [b for b in _results("succeeded_") if b["status"] == "succeeded"]
    assert len(done) >= 5
    assert len({b["otodom_id"] for b in done}) == len(done)
    assert len({b["asking_price_pln"] for b in done}) == len(done)
    assert len({b["max_bid_pln"] for b in done}) == len(done)
    assert len({b["result"]["listing"]["city"] for b in done}) == len(done)


async def test_the_ledger_is_consistent_after_every_scenario(world: World) -> None:
    """Credits and report lots add up to the balances, whatever the scenarios did."""
    async with world.sm() as session:
        assert await ledger_mismatches(session) == []
        assert await lot_mismatches(session) == []
