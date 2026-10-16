# ruff: noqa: F811, F401  (the db fixtures are imported and used as parameters)
"""Property-based contract test of the real API (#28).

Schemathesis reads `docs/openapi.json` and fuzzes every operation over real HTTP against the actual app,
Postgres, session auth and ledger, with the smoke test's named fakes for everything that would leave the
machine.

Evidence class: offline, fake provider data (docs/STATUS.md level 2). It proves that the answers to generated
and malformed requests agree with the document (status documented, content type, response schema, `Allow` on a
405, no 5xx); it says nothing about Otodom, OpenRouter, Paddle or Google. The nightly contract test against
one
live listing (upstream drift) is a different test and is never part of this one.

Operations left out of the fuzzing run, each with its reason (`EXCLUDED`): they end the very session the run
uses, are streams that never finish by design, or are covered by named scenarios instead.
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from contract import OPENAPI_PATH
from db_fixtures import engine, migrated_url, pg_url, procrastinate_schema
from world import ORIGIN, World

pytestmark = [pytest.mark.integration]

CLI = Path(sys.executable).parent / "schemathesis"

# operationId -> why the fuzzing run does not call it
EXCLUDED = {
    "sign_out_api_auth_signout_post": "ends the session the run uses; test_auth.py",
    "sign_out_everywhere_api_auth_signout_all_post": "ends every session of the run's user; test_auth.py",
    "password_change_api_auth_password_change_post": "revokes the run's sessions; test_password_recovery.py",
    "delete_my_account_api_me_delete": "erases the run's user; test_gdpr.py and the smoke scenarios",
    "audit_events_api_audits__audit_id__events_get": "a stream that stays open; test_audit_events.py",
}
MAX_EXAMPLES = int(os.environ.get("CONTRACT_MAX_EXAMPLES", "25"))
BASELINE = Path(__file__).with_name("schemathesis-baseline.json")


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def world(migrated_url: str, procrastinate_schema: None) -> AsyncIterator[World]:
    # A real socket: the CLI is a separate process, so the app must serve over TCP, not in-process.
    async with World(migrated_url, transport="tcp").running() as w:
        yield w


def _append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


async def _run(args: list[str]) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        str(CLI),
        "run",
        str(OPENAPI_PATH),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "NO_COLOR": "1"},
    )
    out, _ = await process.communicate()
    text = out.decode(errors="replace")
    if dump := os.environ.get("CONTRACT_DUMP"):  # the full report, for working through a failing run
        await asyncio.to_thread(_append, Path(dump), text)
    return process.returncode or 0, text


def _common(world: World, cookie: str) -> list[str]:
    args = [
        "--url",
        world.base_url,
        "--header",
        f"Cookie: {world.settings.cookie_name}={cookie}",
        "--header",
        f"Origin: {ORIGIN}",
        "--header",
        "X-Forwarded-For: 10.250.0.9",
        "--checks",
        "all",
        # The API also validates what JSON Schema cannot say (an Otodom reference, a cursor, a password rule,
        # a non-zero adjustment) and answers those with a documented 422 problem. Every other check, including
        # that the 422 is a well-formed documented problem, stays on.
        "--exclude-checks",
        "positive_data_acceptance",
        "--max-examples",
        str(MAX_EXAMPLES),
        "--seed",
        "1",
        "--generation-deterministic",
        "--no-shrink",
        "--workers",
        "1",
        "--request-timeout",
        "30",
        "--output-sanitize",
        "false",
        "--warnings",
        "off",
    ]
    if BASELINE.exists():
        args += ["--baseline", str(BASELINE)]
    return args


async def test_fuzzed_requests_agree_with_the_document(world: World) -> None:
    who = await world.user(label="fuzz", credits=3)
    skip = [part for op in EXCLUDED for part in ("--exclude-operation-id", op)]
    args = [*_common(world, who.cookie or ""), *skip, "--exclude-path-regex", "^/api/admin/"]
    code, out = await _run(args)
    assert code == 0, out[-6000:]


async def test_admin_operations_agree_with_the_document(world: World) -> None:
    admin = await world.user(label="fuzzadmin", credits=3, role="admin")
    args = [*_common(world, admin.cookie or ""), "--include-path-regex", "^/api/admin/"]
    code, out = await _run(args)
    assert code == 0, out[-6000:]
