# ruff: noqa: F811, F401  (the db fixtures are imported and used as parameters)
"""Property-based contract test of the real API (#28).

Schemathesis reads `docs/openapi.json` and fuzzes every operation over real HTTP against the actual app,
Postgres, session auth and ledger, with the smoke test's named fakes for everything that would leave the
machine.

Evidence class: offline, fake provider data (docs/STATUS.md level 2). It proves that the answers to generated
and malformed requests agree with the document (status documented, content type, response schema, `Allow` on a
405, no 5xx, and, for ordinary inputs, that a schema-valid request is accepted); it says nothing about Otodom,
OpenRouter, Paddle or Google. The nightly contract test against one live listing (upstream drift) is a
different test and is never part of this one.

What is NOT fuzzed, and why, is written down in `EXCLUDED` (session-ending operations and a stream) and
`SEMANTIC_422` (operations with a rule JSON Schema cannot express: they run with one named check
relaxed). Both are audited below: every excluded operation must have a named smoke scenario, every entry
must name a real operation, and the junit report of each run must list every operation it was supposed to
fuzz, so a new route cannot be silently skipped.
"""

import asyncio
import contextlib
import html
import os
import re
import shutil
import signal
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from contract import OPENAPI_PATH, load_spec, operations
from db_fixtures import engine, migrated_url, pg_url, procrastinate_schema
from scenarios import all_scenarios
from world import ORIGIN, World

pytestmark = [pytest.mark.integration]

CLI = Path(sys.executable).parent / "schemathesis"

# Not called by the fuzzing run. operationId -> why. Each is exercised by named smoke scenarios instead
# (`test_every_excluded_operation_has_a_named_success_scenario`).
EXCLUDED = {
    "sign_out_api_auth_signout_post": "ends the session the run uses",
    "sign_out_everywhere_api_auth_signout_all_post": "ends every session of the run's user",
    "password_change_api_auth_password_change_post": "revokes the run's sessions",
    "delete_my_account_api_me_delete": "erases the run's user",
    "audit_events_api_audits__audit_id__events_get": "a stream that stays open by design",
}

# Fuzzed with `positive_data_acceptance` relaxed, because the API enforces a rule JSON Schema cannot say and
# answers a schema-valid input with a documented 422 problem. Reviewed one by one; every other check stays on
# for them, and every other operation keeps positive_data_acceptance on (a valid request must be accepted).
SEMANTIC_422 = {
    "list_audits_api_audits_get": "`cursor` is opaque: only a cursor this API issued is valid",
    "create_audit_api_audits_post": "an optional UUID header is sent as the string `null` by the generator",
    "register_api_auth_register_post": "the password policy (length, common passwords) is not a schema rule",
    "adjust_credits_api_admin_credits_adjust_post": "`delta` must not be zero",
}

MAX_EXAMPLES = int(os.environ.get("CONTRACT_MAX_EXAMPLES", "25"))
RUN_BUDGET_S = (
    240  # the whole CLI run, enforced twice: by Schemathesis and by this test killing the process group
)
REPORT_CHARS = 6_000  # what a failing assertion shows: bounded, with the session cookie removed
BASELINE = Path(__file__).with_name("schemathesis-baseline.json")


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def world(migrated_url: str, procrastinate_schema: None) -> AsyncIterator[World]:
    # A real socket: the CLI is a separate process, so the app must serve over TCP, not in-process.
    async with World(migrated_url, transport="tcp").running() as w:
        yield w


def _append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text[:200_000])


def _scrub(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[session]")
    return text


async def _run(args: list[str], secrets: list[str]) -> tuple[int, str, list[str]]:
    """One CLI run: its exit code, its scrubbed output and the operations its junit report lists.

    The whole run has a deadline; on a timeout or a cancellation the process group is killed and reaped, so a
    hung run can neither stall the suite nor outlive it. Output is sanitised by Schemathesis itself (the
    default) and the session cookie is removed again here."""
    report_dir = Path(tempfile.mkdtemp(prefix="schemathesis-"))
    report = report_dir / "junit.xml"
    process = await asyncio.create_subprocess_exec(
        str(CLI),
        "run",
        str(OPENAPI_PATH),
        *args,
        "--report",
        "junit",
        "--report-junit-path",
        str(report),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "NO_COLOR": "1"},
        start_new_session=True,
    )
    try:
        out, _ = await asyncio.wait_for(process.communicate(), timeout=RUN_BUDGET_S)
    except (TimeoutError, asyncio.CancelledError):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()  # reaped, never a zombie
        raise
    text = _scrub(out.decode(errors="replace"), secrets)
    if dump := os.environ.get(
        "CONTRACT_DUMP"
    ):  # the (scrubbed, bounded) report, for working through a failing run
        await asyncio.to_thread(_append, Path(dump), text)
    listed: list[str] = []
    if report.exists():  # our own subprocess's file: read the case names with a pattern, no XML parser needed
        names = re.findall(r'<testcase\b[^>]*\bname="([^"]*)"', report.read_text(encoding="utf-8"))
        listed = [html.unescape(name) for name in names]
    shutil.rmtree(report_dir, ignore_errors=True)
    return process.returncode or 0, text, listed


def _common(world: World, cookie: str, *, strict: bool) -> list[str]:
    assert not BASELINE.exists(), (
        f"{BASELINE.name} would hide regressions from this test. A baseline needs an explicit, reviewed "
        "policy "
        "(a named list of operations and reasons in this file); delete the file."
    )
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
        "--warnings",
        "off",
    ]
    if not strict:
        args += ["--exclude-checks", "positive_data_acceptance"]
    if os.environ.get("CONTRACT_UNSANITIZED") == "1":
        # Debug only, on a machine that holds nothing but this test's synthetic data. Never in CI.
        assert "CI" not in os.environ, "CONTRACT_UNSANITIZED is a local debugging switch, not for CI"
        args += ["--output-sanitize", "false"]
    return args


def _ids(*groups: dict[str, str]) -> list[str]:
    return [part for group in groups for op in group for part in ("--exclude-operation-id", op)]


def _only(ids: dict[str, str]) -> list[str]:
    return [part for op in ids for part in ("--include-operation-id", op)]


def _expected(ids: set[str]) -> set[str]:
    """The `METHOD path` names Schemathesis uses for these operations in its report."""
    by_id = {op.operation_id: op for op in operations(load_spec()).values()}
    return {f"{by_id[i].method} {by_id[i].path}" for i in ids}


def _assert_ran(listed: list[str], expected: set[str], what: str) -> None:
    missing = sorted(expected - set(listed))
    assert missing == [], f"{what}: the run did not fuzz {missing}"


def _admin_ids() -> set[str]:
    return {o.operation_id for o in operations(load_spec()).values() if o.path.startswith("/api/admin/")}


def _all_ids() -> set[str]:
    return {o.operation_id for o in operations(load_spec()).values()}


async def test_ordinary_operations_keep_every_check_including_acceptance_of_valid_input(world: World) -> None:
    who = await world.user(label="fuzz", credits=3)
    cookie = who.cookie or ""
    args = [
        *_common(world, cookie, strict=True),
        *_ids(EXCLUDED, SEMANTIC_422),
        "--exclude-path-regex",
        "^/api/admin/",
    ]
    code, out, listed = await _run(args, [cookie])
    assert code == 0, out[-REPORT_CHARS:]
    expected = _all_ids() - set(EXCLUDED) - set(SEMANTIC_422) - _admin_ids()
    _assert_ran(listed, _expected(expected), "ordinary operations")


async def test_operations_with_a_semantic_rule_run_with_acceptance_relaxed_and_nothing_else(
    world: World,
) -> None:
    who = await world.user(label="fuzzsem", credits=3)
    cookie = who.cookie or ""
    user_ops = {op: why for op, why in SEMANTIC_422.items() if op not in _admin_ids()}
    code, out, listed = await _run([*_common(world, cookie, strict=False), *_only(user_ops)], [cookie])
    assert code == 0, out[-REPORT_CHARS:]
    _assert_ran(listed, _expected(set(user_ops)), "semantic operations")


async def test_admin_operations_agree_with_the_document(world: World) -> None:
    admin = await world.user(label="fuzzadmin", credits=3, role="admin")
    cookie = admin.cookie or ""
    args = [
        *_common(world, cookie, strict=True),
        *_ids(SEMANTIC_422),
        "--include-path-regex",
        "^/api/admin/",
    ]
    code, out, listed = await _run(args, [cookie])
    assert code == 0, out[-REPORT_CHARS:]
    _assert_ran(listed, _expected(_admin_ids() - set(SEMANTIC_422)), "admin operations")


async def test_admin_semantic_operations_run_with_acceptance_relaxed(world: World) -> None:
    admin = await world.user(label="fuzzadminsem", credits=3, role="admin")
    cookie = admin.cookie or ""
    admin_ops = {op: why for op, why in SEMANTIC_422.items() if op in _admin_ids()}
    code, out, listed = await _run([*_common(world, cookie, strict=False), *_only(admin_ops)], [cookie])
    assert code == 0, out[-REPORT_CHARS:]
    _assert_ran(listed, _expected(set(admin_ops)), "admin semantic operations")


def test_every_exclusion_names_a_real_operation_and_a_reason() -> None:
    known = _all_ids()
    for group in (EXCLUDED, SEMANTIC_422):
        assert sorted(set(group) - known) == [], "an exclusion points at an operation that no longer exists"
        assert all(reason.strip() for reason in group.values())
    assert set(EXCLUDED).isdisjoint(SEMANTIC_422)


def test_every_excluded_operation_has_a_named_success_scenario() -> None:
    """What the fuzzing run cannot call is covered by name in the smoke registry, not by a comment."""
    by_id = {op.operation_id: op.key for op in operations(load_spec()).values()}
    ok = {s.key for s in all_scenarios() if 200 <= s.status < 300}
    assert sorted(op for op in EXCLUDED if by_id[op] not in ok) == []


def test_no_baseline_file_may_hide_regressions() -> None:
    assert not BASELINE.exists(), "delete the baseline: this suite has no baseline policy (see _common)"
