"""Errors are documented as `application/problem+json` in the OpenAPI document (RM-264, L-027)."""

import ast
import inspect
import json
from pathlib import Path
from typing import Any

import httpx
import jsonschema_rs
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel
from rm_api.app import ROUTERS
from rm_api.problem_docs import EXTRA, document_problems
from rm_api.problems import install_problem_handlers
from rm_contracts.problems import ProblemCode

ROOT = Path(__file__).resolve().parents[2]
SPEC: dict[str, Any] = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
PROBLEM_MEDIA = "application/problem+json"


def operations() -> list[tuple[str, str, dict[str, Any]]]:
    return [(method.upper(), path, op) for path, item in SPEC["paths"].items() for method, op in item.items()]


def test_there_is_a_problem_schema_and_no_fastapi_validation_schema() -> None:
    schemas = SPEC["components"]["schemas"]
    assert "Problem" in schemas
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert schemas["Problem"]["properties"]["code"]["$ref"] == "#/components/schemas/ProblemCode"
    assert schemas["ProblemCode"]["enum"] == [c.value for c in ProblemCode]
    assert "HTTPValidationError" not in json.dumps(SPEC)


def test_every_error_response_is_a_problem_with_its_codes_listed() -> None:
    for method, path, op in operations():
        errors = {s: r for s, r in op["responses"].items() if not s.startswith("2")}
        assert {"500", "503"} <= set(errors), f"{method} {path}: 500 and 503 are always possible"
        for status, response in errors.items():
            assert list(response["content"]) == [PROBLEM_MEDIA], f"{method} {path} {status}"
            assert response["content"][PROBLEM_MEDIA]["schema"] == {"$ref": "#/components/schemas/Problem"}
            codes = response["x-problem-codes"]
            assert codes, f"{method} {path} {status}"
            assert set(codes) <= {c.value for c in ProblemCode}, f"{method} {path} {status}"


def test_session_routes_say_401_and_unsafe_routes_say_403() -> None:
    by_key = {f"{m} {p}": op for m, p, op in operations()}
    assert "401" in by_key["GET /api/me"]["responses"]
    assert "401" not in by_key["POST /api/auth/email/start"]["responses"]
    assert "ORIGIN_NOT_ALLOWED" in by_key["POST /api/auth/email/start"]["responses"]["403"]["x-problem-codes"]
    assert "403" not in by_key["GET /api/me"]["responses"]
    assert by_key["GET /api/admin/jobs"]["responses"]["403"]["x-problem-codes"] == ["ADMIN_ONLY"]


def test_the_two_accepted_answers_are_documented_as_successes() -> None:
    by_key = {f"{m} {p}": op for m, p, op in operations()}
    for key in ("POST /api/billing/checkout", "POST /api/admin/billing/purchases/{purchase_id}/refund"):
        assert {"200", "202"} <= set(by_key[key]["responses"]), key


def _router_modules() -> dict[str, list[APIRoute]]:
    modules: dict[str, list[APIRoute]] = {}
    for router in ROUTERS:
        for route in router.routes:
            if isinstance(route, APIRoute) and route.include_in_schema:
                modules.setdefault(route.endpoint.__module__, []).append(route)
    return modules


def _codes_named_in(module: str) -> set[str]:
    tree = ast.parse(Path(inspect.getfile(__import__(module, fromlist=["x"]))).read_text(encoding="utf-8"))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"ProblemCode", "C"}
        and node.attr in ProblemCode.__members__
    }


@pytest.mark.parametrize("module", sorted(_router_modules()))
def test_every_raised_code_is_documented(module: str) -> None:
    """A handler module cannot raise a problem code that none of its operations lists."""
    routes = _router_modules()[module]
    documented: set[str] = set()
    for route in routes:
        for method in route.methods or ():
            for response in SPEC["paths"][route.path][method.lower()]["responses"].values():
                documented.update(response.get("x-problem-codes", []))
    raised = {ProblemCode[name].value for name in _codes_named_in(module)}
    assert raised - documented == set(), f"{module} raises codes no operation documents"


def test_the_hand_written_table_names_real_operations() -> None:
    keys = {f"{m} {p}" for m, p, _ in operations()}
    assert sorted(set(EXTRA) - keys) == []


async def test_a_validation_error_matches_the_documented_schema() -> None:
    class Body(BaseModel):
        name: str
        count: int

    app = FastAPI()
    install_problem_handlers(app)

    @app.post("/echo")
    def echo(body: Body) -> dict[str, str]:  # pragma: no cover - never reached
        return {"name": body.name}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        reply = await client.post("/echo", json={"name": 1})
    assert reply.status_code == 422
    assert reply.headers["content-type"].startswith(PROBLEM_MEDIA)
    validator = jsonschema_rs.validator_for(
        {"$ref": "#/components/schemas/Problem", "components": SPEC["components"]}
    )
    assert validator.is_valid(reply.json()), list(validator.iter_errors(reply.json()))[:3]
    assert reply.json()["errors"], "a 422 lists what was wrong"


def test_document_problems_is_idempotent() -> None:
    schema: dict[str, Any] = json.loads(json.dumps(SPEC))
    once = json.dumps(document_problems(ROUTERS, schema), sort_keys=True)
    assert once == json.dumps(SPEC, sort_keys=True)
