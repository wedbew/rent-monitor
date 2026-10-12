"""The committed `docs/openapi.json` must match the app (RM-167). Regenerate with `scripts/gen_openapi.py`."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from gen_openapi import SCHEMA_PATH, build_schema, render  # noqa: E402


def test_the_committed_schema_matches_the_app() -> None:
    assert SCHEMA_PATH.exists(), "run: uv run python scripts/gen_openapi.py"
    committed = SCHEMA_PATH.read_text(encoding="utf-8")
    assert committed == render(build_schema()), (
        "API changed: run `uv run python scripts/gen_openapi.py` and commit"
    )


def test_the_schema_is_deterministic() -> None:
    assert render(build_schema()) == render(build_schema())


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    return build_schema()


def test_every_route_group_of_the_route_map_is_present(schema: dict[str, object]) -> None:
    paths = set(json.loads(json.dumps(schema))["paths"])
    for expected in (
        "/api/auth/google",
        "/api/auth/email/start",
        "/api/auth/email/verify",
        "/api/auth/signout",
        "/api/auth/sessions",
        "/api/me",
        "/api/me/export",
        "/api/saved",
        "/api/saved/{otodom_id}",
        "/api/admin/flags",
        "/api/admin/credits/adjust",
        "/api/admin/jobs",
    ):
        assert expected in paths, expected


def test_internal_probes_are_not_part_of_the_public_contract(schema: dict[str, object]) -> None:
    paths = set(json.loads(json.dumps(schema))["paths"])
    assert not {"/healthz", "/readyz", "/api/health"} & paths


def test_no_money_field_is_a_float(schema: dict[str, object]) -> None:
    """agents.md section 3: `float` is banned in returned money fields (credits are integers)."""
    text = json.dumps(schema)
    for name in ("price", "amount", "balance", "delta", "allowance"):
        assert f'"{name}": {{"type": "number"' not in text
