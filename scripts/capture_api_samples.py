"""Capture API response samples into `data/api-samples/<UTC timestamp>/` (#263, FRONTEND-PLAN.md §3).

    make api-samples                      # offline: fake providers, a throwaway database in Compose
    make api-samples-clean                # delete every capture
    uv run python scripts/capture_api_samples.py --mode live --refs data/live-listings.txt  # owner only

It runs the scenario registry of `tests/smoke` (every operation in `docs/openapi.json`) over loopback
HTTP: a local uvicorn serves the real FastAPI app, the real Procrastinate worker and the real engine child run
in this process, and the database is a fresh `rm_samples_<timestamp>` created inside the Compose Postgres and
dropped afterwards. The listing source, market context, vision model, Paddle and Google are fakes
(`evidence: fake-provider-data`); the frontend is designed from the *shape* of these answers, not from what
any vendor says.

Samples can contain third-party listing text when captured live, so they stay local: `data/` is gitignored,
every capture carries a retention date (30 days, enforced on the next run and by `--clean`), cookies, tokens,
request ids and email addresses are redacted, and nothing here is ever pasted into an issue, PR or screenshot.
"""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tests" / "smoke")]

import psycopg  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from contract import check, load_spec, operations, parse_sse  # noqa: E402
from psycopg import sql  # noqa: E402
from scenarios import Scenario, all_scenarios  # noqa: E402
from world import ORIGIN, REDACTED, Exchange, World, redact_json  # noqa: E402

SAMPLES_DIR = ROOT / "data" / "api-samples"
RETENTION_DAYS = 30
COMPOSE = ["docker", "compose", "-f", str(ROOT / "deploy" / "compose.yml")]
LIVE_MAX_REFS = 10
LIVE_GUARD = "API_SAMPLES_LIVE_AUTHORISED"
EVENTS_SCENARIO_KEY = "GET /api/audits/{audit_id}/events"


def admin_url() -> str:
    """The Compose Postgres' maintenance database (the defaults of `deploy/compose.yml`, never `.env`)."""
    user = os.environ.get("POSTGRES_USER", "rentmonitor")
    password = os.environ.get("POSTGRES_PASSWORD", "dev-only-change-me")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return os.environ.get(
        "CAPTURE_ADMIN_URL", f"postgresql+psycopg://{user}:{password}@127.0.0.1:{port}/postgres"
    )


def with_database(url: str, name: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + name


def git(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# GDPR[retention]: a capture is deleted once its manifest `retain_until` (30 days) has passed (RM-263)
def purge_expired(now: datetime) -> list[str]:
    """Retention: delete captures past `retain_until` (no readable manifest: older than the limit)."""
    removed: list[str] = []
    if not SAMPLES_DIR.is_dir():
        return removed
    for run in sorted(SAMPLES_DIR.iterdir()):
        if not run.is_dir():
            continue
        try:
            retain_until = datetime.fromisoformat(
                json.loads((run / "manifest.json").read_text())["retain_until"]
            )
        except (OSError, ValueError, KeyError):
            retain_until = datetime.fromtimestamp(run.stat().st_mtime, UTC) + timedelta(days=RETENTION_DAYS)
        if retain_until < now:
            shutil.rmtree(run)
            removed.append(run.name)
    return removed


def clean_all() -> int:
    if SAMPLES_DIR.is_dir():
        shutil.rmtree(SAMPLES_DIR)
        print(f"deleted {SAMPLES_DIR.relative_to(ROOT)}")
    else:
        print("nothing to delete")
    return 0


def start_postgres() -> None:
    subprocess.run([*COMPOSE, "up", "-d", "--wait", "postgres"], cwd=ROOT, check=True)  # noqa: S603


def _admin_execute(admin: str, statement: sql.Composed) -> None:
    """Run one DDL statement; the database name inside it is quoted as an identifier, never interpolated."""
    with psycopg.connect(admin.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as conn:
        conn.execute(statement)


def create_database(admin: str, name: str) -> None:
    _admin_execute(admin, sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def drop_database(admin: str, name: str) -> None:
    _admin_execute(admin, sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


async def prepare_schema(url: str) -> None:
    from procrastinate import PsycopgConnector  # noqa: PLC0415
    from procrastinate.schema import SchemaManager  # noqa: PLC0415

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    await asyncio.to_thread(command.upgrade, cfg, "head")
    connector = PsycopgConnector(conninfo=url.replace("postgresql+psycopg://", "postgresql://"))
    await connector.open_async()
    try:
        await SchemaManager(connector).apply_schema_async()
    finally:
        await connector.close_async()


def slug(text_: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text_).strip("_")[:90]


# GDPR[personal-data]: accounts are synthetic; emails become pseudonyms, cookies and ids redacted (RM-263)
def write_sample(run_dir: Path, operation_id: str, scenario: Scenario, ex: Exchange, world: World) -> str:
    folder = run_dir / operation_id
    folder.mkdir(parents=True, exist_ok=True)
    name = slug(scenario.name)
    body: Any = redact_json(ex.body, world.aliases)
    if isinstance(body, dict) and "request_id" in body:
        body["request_id"] = REDACTED
    sample = {
        "operation": {"key": scenario.key, "operation_id": operation_id},
        "scenario": scenario.name,
        "note": scenario.note or None,
        "expected_status": scenario.status,
        "request": {
            "method": ex.method,
            "path": ex.path,
            "headers": ex.request_headers,
            "body": redact_json(ex.request_body, world.aliases),
        },
        "status": ex.status,
        "content_type": ex.content_type,
        "headers": ex.headers,
        "body": body,
        "elapsed_ms": ex.elapsed_ms,
    }
    path = folder / f"{name}.json"
    path.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if scenario.key == EVENTS_SCENARIO_KEY and isinstance(ex.body, str):
        lines = [
            json.dumps(
                {
                    "id": f.get("id"),
                    "event": f.get("event"),
                    "data": redact_json(json.loads(f["data"]), world.aliases),
                },
                ensure_ascii=False,
            )
            for f in parse_sse(ex.body)
        ]
        (folder / f"{name}.events.ndjson").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(run_dir))


async def capture_fake(run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    spec = load_spec()
    ops = operations(spec)
    stamp = run_dir.name.lower()
    database = f"rm_samples_{stamp.replace('t', '').replace('z', '')}"
    admin = admin_url()
    if not args.no_compose:
        start_postgres()
    create_database(admin, database)
    url = with_database(admin, database)
    results: list[dict[str, Any]] = []
    gaps: Counter[str] = Counter()
    failures: list[str] = []
    try:
        await prepare_schema(url)
        async with World(url, transport="tcp").running() as world:
            for scenario in all_scenarios():
                op = ops[scenario.key]
                try:
                    ex = await scenario.run(world)
                    found = check(spec, op, ex, scenario.status)
                    file = write_sample(run_dir, op.operation_id, scenario, ex, world)
                except Exception as exc:
                    failures.append(f"{scenario.id}: {type(exc).__name__}: {str(exc)[:300]}")
                    results.append({"operation": op.operation_id, "scenario": scenario.name, "ok": False})
                    print(f"FAIL {scenario.id}")
                    continue
                gaps.update(f"{op.key}: {g}" for g in found)
                results.append(
                    {
                        "operation": op.operation_id,
                        "scenario": scenario.name,
                        "status": ex.status,
                        "ok": True,
                        "file": file,
                    }
                )
                print(f"ok   {scenario.id} -> {ex.status}")
    finally:
        drop_database(admin, database)
    return {"results": results, "failures": failures, "contract_gaps": sorted(gaps)}


# LEGAL[scraping]: live mode fetches the listed Otodom pages via the product client and throttle (RM-263)
# LEGAL[republication]: live samples hold third-party listing fields; local, unshared, 30 days (RM-263)
async def capture_live(run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Owner-authorised: submit the listed refs through the real Otodom client, market context and vision
    (configured by the environment, as on the host), and keep what the API answers. Not exercised by CI or by
    the slice that added it (docs/LIMITATIONS.md)."""
    from rm_core.settings import get_settings  # noqa: PLC0415

    refs = [
        line.strip()
        for line in args.refs.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not 1 <= len(refs) <= LIVE_MAX_REFS:
        msg = f"--refs must list between 1 and {LIVE_MAX_REFS} listings"
        raise SystemExit(msg)
    spec, ops = load_spec(), operations(load_spec())
    admin = admin_url()
    if not args.no_compose:
        start_postgres()
    database = f"rm_samples_{run_dir.name.lower().replace('t', '').replace('z', '')}"
    create_database(admin, database)
    url = with_database(admin, database)
    os.environ.update(
        DATABASE_URL=url,
        PROCRASTINATE_DSN="",
        PUBLIC_APP_URL=ORIGIN,
        APP_ENV="test",
        AUDIT_PROVIDERS="real",
    )
    get_settings.cache_clear()
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        await prepare_schema(url)
        async with World(
            url, transport="tcp", settings=get_settings(), real_providers=True
        ).running() as world:
            who = await world.user(label="live", credits=len(refs))
            for n, ref in enumerate(refs, 1):
                try:
                    accepted = await world.submit(who, ref)
                    await world.run_worker()
                    audit_id = accepted.body["audit_id"]
                    steps = [
                        (Scenario("POST /api/audits", f"live_{n}", 202, _never), accepted),
                        (
                            Scenario("GET /api/audits/{audit_id}", f"live_{n}", 200, _never),
                            await world.send(who, "GET", f"/api/audits/{audit_id}"),
                        ),
                        (
                            Scenario(EVENTS_SCENARIO_KEY, f"live_{n}", 200, _never),
                            await world.send(who, "GET", f"/api/audits/{audit_id}/events"),
                        ),
                    ]
                    for scenario, ex in steps:
                        op = ops[scenario.key]
                        check(spec, op, ex, scenario.status)
                        write_sample(run_dir, op.operation_id, scenario, ex, world)
                    results.append({"operation": "live", "scenario": f"live_{n}", "ok": True})
                except Exception as exc:
                    failures.append(f"live_{n}: {type(exc).__name__}: {str(exc)[:300]}")
                    results.append({"operation": "live", "scenario": f"live_{n}", "ok": False})
    finally:
        drop_database(admin, database)
    return {"results": results, "failures": failures, "contract_gaps": []}


async def _never(world: World) -> Exchange:
    raise AssertionError("live scenarios are driven by capture_live")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--mode", choices=["fake", "live"], default="fake")
    parser.add_argument(
        "--refs", type=Path, help="live mode: a text file with one Otodom listing URL or id per line"
    )
    parser.add_argument("--no-compose", action="store_true", help="do not start the Compose Postgres")
    parser.add_argument("--clean", action="store_true", help="delete every capture and exit")
    args = parser.parse_args()
    if args.clean:
        return clean_all()
    if args.mode == "live" and (args.refs is None or os.environ.get(LIVE_GUARD) != "1"):
        print(
            f"live mode fetches real Otodom pages and calls real providers: it needs --refs <file> and the "
            f"owner's "
            f"authorisation for this run, stated as {LIVE_GUARD}=1 in the environment.",
            file=sys.stderr,
        )
        return 2
    now = datetime.now(UTC)
    for name in purge_expired(now):
        print(f"retention: deleted expired capture {name}")
    run_dir = SAMPLES_DIR / now.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    try:
        outcome = asyncio.run(
            capture_live(run_dir, args) if args.mode == "live" else capture_fake(run_dir, args)
        )
    except BaseException:
        shutil.rmtree(run_dir, ignore_errors=True)  # a crashed run leaves no half-written capture behind
        raise
    oks = [r for r in outcome["results"] if r["ok"]]
    manifest = {
        "captured_at": now.isoformat(),
        "retain_until": (now + timedelta(days=RETENTION_DAYS)).isoformat(),
        "retention": f"{RETENTION_DAYS} days; delete earlier with `make api-samples-clean`",
        "mode": args.mode,
        "evidence": "live" if args.mode == "live" else "fake-provider-data",
        "transport": "uvicorn on loopback, real HTTP",
        "commit": git("rev-parse", "HEAD"),
        "tree_dirty": bool(git("status", "--porcelain")),
        "openapi_sha256": sha256_of(ROOT / "docs" / "openapi.json"),
        "scenarios": len(outcome["results"]),
        "scenarios_ok": len(oks),
        "operations_covered": len({r["operation"] for r in oks}),
        "operations_total": len(operations(load_spec())),
        "redaction": "cookies, Set-Cookie values, request ids and email addresses; accounts are synthetic",
        "contract_gaps": outcome["contract_gaps"],
        "failures": outcome["failures"],
        "results": outcome["results"],
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\n{len(oks)}/{len(outcome['results'])} scenarios captured into {run_dir.relative_to(ROOT)}")
    for failure in outcome["failures"]:
        print(f"  FAILED {failure}", file=sys.stderr)
    return 0 if not outcome["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
