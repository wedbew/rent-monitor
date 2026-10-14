"""`.env.example` must be safe to feed to loaders that do not strip inline comments (RM-234)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_env_example_has_no_inline_comments() -> None:
    offenders: list[str] = []
    for number, raw in enumerate((ROOT / ".env.example").read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        _, _, value = line.partition("=")
        if value.startswith('"'):
            value = value[value.find('"', 1) + 1 :]
        if " #" in value or "\t#" in value:
            offenders.append(f"line {number}: {line.split('=', 1)[0]}")
    assert not offenders, f"move trailing comments above the setting: {offenders}"
