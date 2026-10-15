"""The fixture sanitiser is the privacy boundary between local captures and committed files (RM-268)."""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from derive_ui_fixtures import EMAIL_RE, PHONE_RE, Mapper, derive, run  # noqa: E402

REAL_EMAIL = "jan.kowalski@gmail.com"
REAL_PHONE = "+48 600 123 456"
AUDIT = "5f0c2d6a-1111-4222-8333-444455556666"
CAPTURED = datetime(2026, 10, 15, 7, 0, tzinfo=UTC)
WINDOW = (datetime(2026, 10, 15, 6, 55, tzinfo=UTC), datetime(2026, 10, 15, 9, 0, tzinfo=UTC))


def sample(
    body: Any, *, key: str = "GET /api/audits/{audit_id}", content_type: str = "application/json"
) -> dict[str, Any]:
    return {
        "operation": {"key": key, "operation_id": "op"},
        "scenario": "s",
        "request": {
            "method": "GET",
            "path": "/api/x/9d2c1a52-7a45-4b8c-9f55-0a4d3c2b1a00",
            "body": {"password": "hunter2hunter2", "email": REAL_EMAIL},
        },
        "status": 200,
        "content_type": content_type,
        "headers": {"set-cookie": "rm_session=abc", "content-type": content_type, "x-request-id": "r"},
        "body": body,
    }


def text_of(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


LIVE_LISTING = {
    "audit_id": "5f0c2d6a-1111-4222-8333-444455556666",
    "otodom_id": "ID4abcDEF",
    "created_at": "2026-10-15T07:01:02.345678Z",
    "finished_at": "2026-10-15T07:01:40.000000Z",
    "result": {
        "listing": {
            "otodom_id": "ID4abcDEF",
            "title": f"Sprzedam, dzwoń {REAL_PHONE}, pisz {REAL_EMAIL}",
            "description": "Właściciel Jan Kowalski, ul. Prawdziwa 5",
            "street": "Prawdziwa",
            "url": "https://www.otodom.pl/pl/oferta/prawdziwe-ID4abcDEF",
            "photo_urls": ["https://ireland.apollo.olxcdn.com/v1/files/abc/image"],
            "city": "Toruń",
            "rooms": 3,
            "area_m2": "61.5",
            "price_pln": "512345.67",
            "created_at": "2026-09-01T10:00:00Z",
        }
    },
}


def test_no_email_phone_or_foreign_url_survives() -> None:
    out = derive(sample(LIVE_LISTING), Mapper(), WINDOW)
    blob = text_of(out)
    assert REAL_EMAIL not in blob
    assert not [m for m in EMAIL_RE.findall(blob) if not m.endswith("@example.test")]
    assert not PHONE_RE.findall(blob.replace("+48 000 000 000", ""))
    assert "otodom.pl" not in blob
    assert "olxcdn" not in blob
    assert "Kowalski" not in blob
    assert "Prawdziwa 5" not in blob
    assert "hunter2" not in blob
    assert "rm_session" not in blob


def test_shapes_numbers_and_nullability_are_kept() -> None:
    body = derive(sample(LIVE_LISTING), Mapper(), WINDOW)["body"]
    listing = body["result"]["listing"]
    assert listing["price_pln"] == "512345.67"
    assert listing["area_m2"] == "61.5"
    assert listing["rooms"] == 3
    assert listing["city"] == "Toruń"
    assert listing["title"] == "Mieszkanie 3 pok., Toruń, 61.5 m2"
    assert listing["created_at"] == "2026-09-01T10:00:00Z"  # the advert's own date is not capture time


def test_capture_time_is_shifted_to_a_fixed_base_and_order_is_kept() -> None:
    body = derive(sample(LIVE_LISTING), Mapper(), WINDOW)["body"]
    assert body["created_at"] == "2026-10-01T10:00:00Z"
    assert body["finished_at"] == "2026-10-01T10:00:38Z"


def test_ids_are_numbered_consistently_across_files() -> None:
    mapper = Mapper()
    first = derive(sample(LIVE_LISTING), mapper, WINDOW)["body"]
    second = derive(sample(LIVE_LISTING), mapper, WINDOW)["body"]
    assert first["audit_id"] == second["audit_id"]
    assert first["otodom_id"] == second["otodom_id"] == first["result"]["listing"]["otodom_id"]
    assert first["audit_id"].startswith("00000000-0000-4000-8000-")


def test_problem_bodies_keep_their_wording_but_lose_the_request_id() -> None:
    problem = {
        "type": "urn:rentmonitor:problem:RATE_LIMITED",
        "title": "Too many requests",
        "status": 429,
        "code": "RATE_LIMITED",
        "instance": "/api/auth/login",
        "request_id": "abc123",
    }
    out = derive(sample(problem, key="POST /api/auth/login"), Mapper(), WINDOW)["body"]
    assert out["title"] == "Too many requests"
    assert out["request_id"] == "req_fixture"


def test_event_streams_become_frames_with_mapped_ids() -> None:
    stream = (
        f'id: 5\nevent: progress\ndata: {{"audit_id": "{AUDIT}", "stage": "fetch", "pct": 5}}\n\n'
        f'id: 6\nevent: done\ndata: {{"audit_id": "{AUDIT}", "status": "succeeded"}}\n\n'
    )
    out = derive(
        sample(stream, key="GET /api/audits/{audit_id}/events", content_type="text/event-stream"),
        Mapper(),
        WINDOW,
    )
    assert out["body"] is None
    assert [e["event"] for e in out["events"]] == ["progress", "done"]
    assert out["events"][0]["data"]["audit_id"].startswith("00000000-0000-4000-8000-")
    assert out["events"][0]["data"]["pct"] == 5


def test_only_safe_headers_are_kept_and_secrets_are_dropped() -> None:
    out = derive(sample({"a": 1}), Mapper(), WINDOW)
    assert out["headers"] == {"content-type": "application/json"}
    assert out["request"]["body"] == {"password": "[redacted]", "email": "user-1@example.test"}


def test_a_whole_capture_directory_is_derived_deterministically(tmp_path: Path) -> None:
    run_dir = tmp_path / "20261015T070000Z"
    (run_dir / "get_audit").mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {"captured_at": CAPTURED.isoformat(), "openapi_sha256": "x", "evidence": "fake-provider-data"}
        )
    )
    (run_dir / "get_audit" / "one.json").write_text(json.dumps(sample(LIVE_LISTING)))
    first, second = tmp_path / "a", tmp_path / "b"
    assert run(run_dir, first) == run(run_dir, second) == 0
    a, b = (first / "get_audit" / "one.json").read_text(), (second / "get_audit" / "one.json").read_text()
    assert a == b
    assert not re.search(EMAIL_RE.pattern.replace("example", "NOPE"), a.replace("@example.test", ""))
    assert json.loads((first / "manifest.json").read_text())["fixtures"] == 1
