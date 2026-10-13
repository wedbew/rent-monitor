"""Sanitised error report from the claude-code-action execution file (ADR 0012, docs/AUTONOMY.md).

The action hides its output ("full output hidden for security"), so a failed run shows only `is_error:true`.
This reads the execution JSON and prints just the failure facts: result/subtype/turns/cost, any `error`,
`errors` or `api_error_status` field, and the text of a message that carries an error flag or of the failed
result. It never prints tool inputs or outputs, prompts or the transcript, redacts credential-shaped strings,
and bounds every line and the number of lines.

    python3 scripts/claude_failure_report.py <execution_file>
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_LINE = 500
MAX_LINES = 14
REDACTIONS = (
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]+"), "[redacted-anthropic-key]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "[redacted-github-token]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer [redacted]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"), "[redacted-jwt]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[redacted-email]"),
    (re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"), "[redacted-long-token]"),
)
ERROR_KEYS = ("error", "errors", "api_error_status", "error_type", "error_message")


def sanitize(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    text = " ".join(text.split())
    return text if len(text) <= MAX_LINE else text[: MAX_LINE - 1] + "…"


def load(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = []
        for line in raw.splitlines():
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    items = data if isinstance(data, list) else [data]
    return [m for m in items if isinstance(m, dict)]


def _text_of(message: dict[str, Any]) -> str | None:
    content = message.get("message", {}).get("content") if isinstance(message.get("message"), dict) else None
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        return " ".join(p for p in parts if p) or None
    return content if isinstance(content, str) else None


def report(messages: list[dict[str, Any]]) -> list[str]:
    lines = [f"messages={len(messages)} types={sanitize(sorted({str(m.get('type')) for m in messages}))}"]
    for m in messages:
        kind = m.get("type")
        found = {k: m[k] for k in ERROR_KEYS if m.get(k) not in (None, "", [], {}, False)}
        if kind == "result":
            facts = {
                k: m.get(k) for k in ("subtype", "is_error", "num_turns", "duration_ms", "total_cost_usd")
            }
            lines.append("result " + sanitize(facts))
            if m.get("is_error") and m.get("result"):
                lines.append("result.text " + sanitize(m["result"]))
        elif kind == "system" and m.get("subtype") == "init":
            lines.append(
                "init " + sanitize({k: m.get(k) for k in ("model", "apiKeySource", "permissionMode")})
            )
        if found:
            lines.append(f"{kind}.errors " + sanitize(found))
            text = _text_of(m)
            if text and kind != "result":
                lines.append(f"{kind}.text " + sanitize(text))
    return lines[:MAX_LINES]


def final_result(messages: list[dict[str, Any]]) -> str | None:
    for m in reversed(messages):
        if m.get("type") == "result" and isinstance(m.get("result"), str):
            return sanitize(m["result"])
    return None


def main(argv: list[str]) -> int:
    show_result = "--show-result" in argv
    argv = [a for a in argv if a != "--show-result"]
    if not argv:
        print("usage: claude_failure_report.py [--show-result] <execution_file>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"no execution file at {path.name}")
        return 0
    messages = load(path)
    for line in report(messages):
        print(line)
    if show_result:  # a read-only canary's one-sentence answer
        print("answer " + (final_result(messages) or "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
