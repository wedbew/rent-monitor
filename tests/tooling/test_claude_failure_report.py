import json
from pathlib import Path

from claude_failure_report import MAX_LINE, load, report, sanitize

SECRET = "sk-ant-oat01-" + "A" * 60


def messages() -> list[dict]:
    return [
        {
            "type": "system",
            "subtype": "init",
            "model": "claude-sonnet-5-5",
            "apiKeySource": "none",
            "tools": ["Bash"],
        },
        {
            "type": "assistant",
            "error": "authentication_failed",
            "message": {
                "content": [{"type": "text", "text": f"Invalid API key {SECRET} · Please run /login"}]
            },
        },
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "SECRET FILE CONTENT"}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": "Invalid API key. Authorization: Bearer abcdefghijklmnop for a@b.example",
            "num_turns": 1,
            "duration_ms": 1867,
            "total_cost_usd": 0,
        },
    ]


def test_reports_the_error_and_never_the_transcript_or_credentials() -> None:
    out = "\n".join(report(messages()))
    assert "Invalid API key" in out
    assert "authentication_failed" in out
    assert '"is_error": true' in out
    assert "num_turns" in out
    for forbidden in (SECRET, "abcdefghijklmnop", "a@b.example", "SECRET FILE CONTENT", "Bash"):
        assert forbidden not in out


def test_lines_are_bounded_and_long_tokens_redacted() -> None:
    assert len(sanitize("x " * 5000)) <= MAX_LINE
    assert "[redacted-long-token]" in sanitize("Z" * 60)
    many = [{"type": "result", "is_error": True, "result": "boom", "error": f"e{i}"} for i in range(100)]
    assert len(report(many)) <= 14


def test_reads_json_array_and_json_lines_and_survives_garbage(tmp_path: Path) -> None:
    array = tmp_path / "a.json"
    array.write_text(json.dumps(messages()))
    lines = tmp_path / "b.jsonl"
    lines.write_text("\n".join(json.dumps(m) for m in messages()) + "\nnot json\n")
    assert report(load(array)) == report(load(lines))
