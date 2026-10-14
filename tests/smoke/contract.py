"""Check a recorded exchange against `docs/openapi.json` (#263).

Success bodies must validate against the response schema the operation documents. Error bodies are checked
against the RFC 9457 shape the API really sends (`application/problem+json` with a stable `code` from
`rm_contracts.problems`), because the document does not describe them yet: FE-A1 (#264, L-027) fixes that.
Every place where the document and the answer disagree is returned as a *gap*, so the capture manifest records
it instead of hiding it.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema_rs
from rm_contracts.problems import ProblemCode
from world import Exchange

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = ROOT / "docs" / "openapi.json"
METHODS = ("get", "put", "post", "delete", "patch")
PROBLEM_JSON = "application/problem+json"
CODES = {code.value for code in ProblemCode}


def load_spec() -> dict[str, Any]:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    operation_id: str
    responses: dict[str, Any]

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


def operations(spec: dict[str, Any]) -> dict[str, Operation]:
    found: dict[str, Operation] = {}
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                op = item[method]
                entry = Operation(method.upper(), path, op["operationId"], op["responses"])
                found[entry.key] = entry
    return found


def _validator(spec: dict[str, Any], schema: dict[str, Any]) -> Any:
    return jsonschema_rs.validator_for({**schema, "components": spec["components"]})


def parse_sse(text: str) -> list[dict[str, str]]:
    """The frames of an event stream as `{id, event, data}`; comments (keep-alives) are skipped."""
    frames: list[dict[str, str]] = []
    for block in text.split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith(":") or ": " not in line:
                continue
            name, value = line.split(": ", 1)
            fields[name] = value
        if fields:
            frames.append(fields)
    return frames


def check_problem(ex: Exchange) -> None:
    assert ex.content_type.startswith(PROBLEM_JSON), f"{ex.status} is {ex.content_type!r}, not {PROBLEM_JSON}"
    body = ex.body
    assert isinstance(body, dict), body
    assert body.get("status") == ex.status, body
    assert body.get("code") in CODES, f"code {body.get('code')!r} is not in rm_contracts.problems"
    assert body.get("type") == f"urn:rentmonitor:problem:{body['code']}", body
    assert isinstance(body.get("title"), str), body
    assert isinstance(body.get("instance"), str), body


def check_events(ex: Exchange) -> None:
    frames = parse_sse(str(ex.body or ""))
    assert frames, "an event stream with no events"
    kinds = [f.get("event") for f in frames]
    assert kinds[-1] in {"done", "error"}, f"the stream must end in done or error, got {kinds}"
    assert all(k == "progress" for k in kinds[:-1]), kinds
    for frame in frames:
        json.loads(frame["data"])  # every payload is JSON
    ids = [int(f["id"]) for f in frames if "id" in f]
    assert ids == sorted(ids), "event ids must increase"


def check(spec: dict[str, Any], op: Operation, ex: Exchange, expected: int) -> list[str]:
    """Raise AssertionError when the exchange breaks the contract; return the documentation gaps found."""
    assert ex.status == expected, f"{op.key}: expected {expected}, got {ex.status}: {ex.body}"
    documented = op.responses.get(str(ex.status))
    gaps: list[str] = []
    if ex.status >= 400:
        check_problem(ex)
        schema = (documented or {}).get("content", {}).get("application/json", {}).get("schema")
        if documented is None:
            gaps.append(f"{ex.status} is not documented")
        elif schema is not None and not _validator(spec, schema).is_valid(ex.body):
            gaps.append(
                f"{ex.status} is documented as {schema.get('$ref', 'a schema')} but sent as problem+json"
            )
        return gaps
    if documented is None:
        lowest = min(int(s) for s in op.responses if s.startswith("2"))
        documented = op.responses[str(lowest)]
        gaps.append(f"{ex.status} is not documented (using {lowest})")
    content = documented.get("content", {})
    if ex.status == 204:
        assert ex.body in (None, ""), f"204 with a body: {ex.body!r}"
        return gaps
    media = next(iter(content), None)
    assert media is not None, f"{op.key} documents no body but sent {ex.content_type!r}"
    assert ex.content_type.startswith(media), f"content type {ex.content_type!r}, documented {media!r}"
    if media == "text/event-stream":
        check_events(ex)
        return gaps
    schema = content[media].get("schema")
    if schema is not None:
        errors = [e.message for e in _validator(spec, schema).iter_errors(ex.body)][:5]
        assert not errors, f"{op.key} body does not match its schema: {errors}"
    return gaps
