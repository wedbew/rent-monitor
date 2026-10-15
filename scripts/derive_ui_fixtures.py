"""Turn a local API capture into committed, sanitised frontend fixtures (#268, FRONTEND-PLAN.md section 3).

    uv run python scripts/derive_ui_fixtures.py                    # newest capture under data/api-samples/
    uv run python scripts/derive_ui_fixtures.py data/api-samples/<run> [--out frontend/test/fixtures]

The captures in `data/` are local and gitignored because a *live* capture can hold third-party listing text,
seller data and real accounts. Fixtures are what the UI tests, the component catalog and the mocked end-to-end
lane render, and they are committed, so this script is the privacy boundary: whatever the input, the output
holds only synthetic identifiers, addresses, names, text, URLs and capture-relative timestamps. Shapes,
numbers and nullability are kept, because those are what the screens depend on.
`tests/unit/test_derive_ui_fixtures.py` fails when an email, phone number or foreign URL survives, and the
frontend validates every fixture against `docs/openapi.json`.

Everything is deterministic: ids are numbered in order of first appearance over files sorted by operation and
scenario, and timestamps made during the capture are shifted to a fixed base per file, so re-deriving a
capture of the same scenarios gives the same fixtures.

LEGAL[republication]: third-party listing text, photos and addresses are replaced, never copied (RM-268).
GDPR[personal-data]: emails, names, user agents, IPs, notes replaced; passwords and tokens dropped (RM-268).
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "api-samples"
DEFAULT_OUT = ROOT / "frontend" / "test" / "fixtures"
BASE_TIME = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
KEPT_HEADERS = {"content-type", "retry-after", "cache-control", "content-disposition"}
SECRET_KEYS = {"password", "current_password", "new_password", "token", "credential"}
EMAIL_KEYS = {"email", "confirm_email"}
URL_LIST_KEYS = {"photo_urls", "floor_plan_urls"}
NAMES = (
    "Anna Przykładowa",
    "Jan Testowy",
    "Maria Fikcyjna",
    "Piotr Próbny",
    "Ewa Wzorcowa",
    "Tomasz Testowski",
)

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
HEX32_RE = re.compile(r"\b[0-9a-f]{32}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
PHONE_RE = re.compile(r"(?<![\w.:/-])(?:\+\d{1,3}[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?![\w.:/-])")
IPV4_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
OTODOM_ID_RE = re.compile(r"^ID[0-9A-Za-z]{6,16}$")
PROVIDER_ID_RE = re.compile(r"^(txn|pri|pro|adj|ctm|evt)_[A-Za-z0-9_]+$")


class Mapper:
    """Stable synthetic stand-ins, numbered in order of first appearance."""

    def __init__(self) -> None:
        self.maps: dict[str, dict[str, str]] = {}

    def get(self, kind: str, original: str, make: Any) -> str:
        table = self.maps.setdefault(kind, {})
        if original not in table:
            table[original] = make(len(table) + 1)
        return table[original]

    def uuid(self, value: str) -> str:
        return self.get("uuid", value.lower(), lambda n: f"00000000-0000-4000-8000-{n:012d}")

    def hex32(self, value: str) -> str:
        return self.get("hex32", value.lower(), lambda n: f"{n:032x}")

    def email(self, value: str) -> str:
        return self.get("email", value.lower(), lambda n: f"user-{n}@example.test")

    def name(self, value: str) -> str:
        return self.get("name", value, lambda n: NAMES[(n - 1) % len(NAMES)])

    def otodom(self, value: str) -> str:
        return self.get("otodom", value, lambda n: f"IDFIX{n:04d}")

    def url(self, value: str) -> str:
        return self.get("url", value, lambda n: f"https://example.test/fixture/{n}")

    def ip(self, value: str) -> str:
        return self.get("ip", value, lambda n: f"203.0.113.{n % 250}")

    def provider(self, value: str) -> str:
        prefix = value.split("_", 1)[0]
        return self.get("provider", value, lambda n: f"{prefix}_fixture{n:04d}")

    def note(self, value: str) -> str:
        return self.get("note", value, lambda n: f"Notatka testowa {n}")


def _collect_times(value: Any, out: list[datetime]) -> None:
    if isinstance(value, str) and ISO_RE.match(value):
        out.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
    elif isinstance(value, list):
        for item in value:
            _collect_times(item, out)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_times(item, out)


class Sanitiser:
    def __init__(self, mapper: Mapper, window: tuple[datetime, datetime] | None = None) -> None:
        self.m = mapper
        self.window = window  # timestamps inside it were made by the capture itself
        self.origin: datetime | None = None

    # ------------------------------------------------------------------------------------- strings
    def text(self, value: str) -> str:
        """Replace identifiers inside any string; the string's own shape stays."""
        value = UUID_RE.sub(lambda m: self.m.uuid(m.group(0)), value)
        value = HEX32_RE.sub(lambda m: self.m.hex32(m.group(0)), value)
        value = EMAIL_RE.sub(lambda m: self.m.email(m.group(0)), value)
        value = URL_RE.sub(lambda m: self.m.url(m.group(0)), value)
        value = PHONE_RE.sub("+48 000 000 000", value)
        return IPV4_RE.sub(lambda m: self.m.ip(m.group(0)), value)

    def in_window(self, at: datetime) -> bool:
        return self.window is None or self.window[0] <= at <= self.window[1]

    def timestamp(self, value: str) -> str:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not self.in_window(at):
            return value  # data the fixtures were built from (a listing's own dates), not capture time
        origin = self.origin or at
        shifted = BASE_TIME + timedelta(seconds=round((at - origin).total_seconds()))
        return shifted.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------------------------ structure
    def value(self, key: str | None, value: Any, parent: dict[str, Any] | None = None) -> Any:
        if isinstance(value, dict):
            return self.mapping(value)
        if isinstance(value, list):
            return [self.value(key, item, parent) for item in value]
        return self.scalar((key or "").lower(), value, parent) if isinstance(value, str) else value

    def scalar(self, low: str, value: str, parent: dict[str, Any] | None) -> str:
        keyed = self.by_key(low, value, parent)
        if keyed is not None:
            return keyed
        if OTODOM_ID_RE.match(value):
            return self.m.otodom(value)
        if PROVIDER_ID_RE.match(value):
            return self.m.provider(value)
        return self.timestamp(value) if ISO_RE.match(value) else self.text(value)

    def by_key(self, low: str, value: str, parent: dict[str, Any] | None) -> str | None:
        """What a field's *name* says about its value; None when the name decides nothing."""
        fixed = {
            "request_id": "req_fixture",
            "next_cursor": "cursor-fixture",
            "user_agent": "Mozilla/5.0 (fixture) Chrome/130",
        }
        if low in SECRET_KEYS:
            return "[redacted]"
        if low in fixed:
            return fixed[low]
        makers = {
            "ip": self.m.ip,
            "otodom_id": self.m.otodom,
            "note": self.m.note,
            "avatar_url": self.m.url,
        }
        if low in EMAIL_KEYS:
            return self.m.email(value)
        if low == "name" and parent is not None and "email" in parent:
            return self.m.name(value)
        if low == "url" and URL_RE.fullmatch(value):
            return self.m.url(value)
        return makers[low](value) if low in makers else None

    def mapping(self, node: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        is_listing = "otodom_id" in node and "title" in node
        for key, value in node.items():
            if is_listing and key == "title":
                out[key] = self.listing_title(node)
            elif is_listing and key == "description":
                out[key] = None if value is None else "Opis testowy ogłoszenia."
            elif is_listing and key == "street":
                out[key] = None if value is None else "Przykładowa"
            elif key in URL_LIST_KEYS and isinstance(value, list):
                out[key] = [self.m.url(str(u)) for u in value]
            else:
                out[key] = self.value(key, value, node)
        return out

    def listing_title(self, node: dict[str, Any]) -> str:
        rooms, city, area = node.get("rooms"), node.get("city"), node.get("area_m2")
        parts = [f"Mieszkanie {rooms} pok." if rooms else "Mieszkanie", str(city) if city else None]
        if area:
            parts.append(f"{area} m2")
        return ", ".join(p for p in parts if p)

    def document(self, doc: Any) -> Any:
        times: list[datetime] = []
        _collect_times(doc, times)
        inside = [t for t in times if self.in_window(t)]
        self.origin = min(inside) if inside else None
        return self.value(None, doc)


def _events(body: str, san: Sanitiser) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":")
        )
        if fields:
            data = json.loads(fields["data"])
            frames.append({"id": fields.get("id"), "event": fields.get("event"), "data": san.document(data)})
    return frames


def derive(
    sample: dict[str, Any], mapper: Mapper, window: tuple[datetime, datetime] | None = None
) -> dict[str, Any]:
    san = Sanitiser(mapper, window)
    operation = sample["operation"]
    method, template = operation["key"].split(" ", 1)
    headers = {k.lower(): v for k, v in sample["headers"].items() if k.lower() in KEPT_HEADERS}
    out: dict[str, Any] = {
        "operation": {
            "key": operation["key"],
            "operation_id": operation["operation_id"],
            "method": method,
            "path": template,
        },
        "scenario": sample["scenario"],
        "request": {
            "path": san.text(sample["request"]["path"]),
            "body": san.document(sample["request"]["body"]),
        },
        "status": sample["status"],
        "content_type": sample["content_type"],
        "headers": headers,
    }
    body = sample["body"]
    if sample["content_type"].startswith("text/event-stream"):
        out["events"] = _events(str(body or ""), san)
        out["body"] = None
    else:
        out["body"] = san.document(body)
    return out


def latest_run() -> Path:
    runs = sorted(p for p in SAMPLES.iterdir() if (p / "manifest.json").exists()) if SAMPLES.is_dir() else []
    if not runs:
        msg = "no capture under data/api-samples/: run `make api-samples`"
        raise SystemExit(msg)
    return runs[-1]


def run(source: Path, out_dir: Path) -> int:
    files = sorted(p for p in source.glob("*/*.json") if p.parent.name != "." and p.name != "manifest.json")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    taken = datetime.fromisoformat(manifest["captured_at"])
    window = (taken - timedelta(minutes=5), taken + timedelta(hours=2))  # the capture runs in minutes
    mapper = Mapper()
    keep: set[Path] = set()
    for path in files:
        sample = json.loads(path.read_text(encoding="utf-8"))
        fixture = derive(sample, mapper, window)
        target = out_dir / path.parent.name / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        keep.add(target)
    for stale in out_dir.glob("*/*.json"):
        if stale not in keep:
            stale.unlink()
    summary = {
        "evidence": manifest["evidence"],
        "fixtures": len(keep),
        "note": "derived by scripts/derive_ui_fixtures.py from a local capture; synthetic and sanitised",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"{len(keep)} fixtures written to {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", nargs="?", type=Path, help="a capture directory (default: the newest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    return run((args.source or latest_run()).resolve(), args.out.resolve())


if __name__ == "__main__":
    sys.exit(main())
