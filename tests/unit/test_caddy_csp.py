"""The public Content-Security-Policy in `deploy/Caddyfile` (RM-277).

Caddy expands `{$NAME}` from the environment. With every Paddle value empty (billing off) the
policy must name no Paddle host and relax nothing; with the documented sandbox values it must
allow exactly Paddle.js's script, assets and frame, and only inline style *attributes* (never
inline style elements or scripts).
"""

import re
from pathlib import Path

CADDYFILE = Path(__file__).resolve().parents[2] / "deploy" / "Caddyfile"
SANDBOX = {
    "PADDLE_CSP_SCRIPT": "https://cdn.paddle.com",
    "PADDLE_CSP_ASSETS": "https://cdn.paddle.com https://sandbox-cdn.paddle.com",
    "PADDLE_CSP_FRAME": "https://sandbox-buy.paddle.com",
    "PADDLE_CSP_STYLE_ATTR": "'unsafe-inline'",
}


def everything(csp: dict[str, list[str]]) -> list[str]:
    return [source for sources in csp.values() for source in sources]


def policy(env: dict[str, str]) -> dict[str, list[str]]:
    line = next(ln for ln in CADDYFILE.read_text().splitlines() if "Content-Security-Policy" in ln)
    raw = re.search(r'Content-Security-Policy "([^"]+)"', line)
    assert raw is not None
    text = re.sub(r"\{\$(\w+)\}", lambda m: env.get(m.group(1), ""), raw.group(1))
    directives: dict[str, list[str]] = {}
    for part in text.split(";"):
        name, *sources = part.split()
        directives[name] = sources
    return directives


def test_with_billing_off_no_paddle_host_is_allowed_and_nothing_is_relaxed() -> None:
    csp = policy({})
    assert "paddle" not in " ".join(everything(csp)).lower()
    assert "'unsafe-inline'" not in everything(csp)
    assert csp["default-src"] == ["'none'"]
    assert csp["style-src-attr"] == []  # an empty source list is 'none'


def test_the_sandbox_values_allow_only_what_paddle_js_needs() -> None:
    csp = policy(SANDBOX)
    assert "https://cdn.paddle.com" in csp["script-src"]
    assert not any("sandbox-buy" in s for s in csp["script-src"] + csp["connect-src"])
    assert csp["frame-src"][-1] == "https://sandbox-buy.paddle.com"
    assert "https://sandbox-cdn.paddle.com" in csp["style-src"]
    assert "https://sandbox-cdn.paddle.com" in csp["img-src"]
    assert csp["style-src-attr"] == ["'unsafe-inline'"]
    # Only style attributes are relaxed: no inline script, no inline style element, no eval.
    assert "'unsafe-inline'" not in csp["script-src"] + csp["style-src"] + csp["default-src"]
    assert "'unsafe-eval'" not in everything(csp)
    assert csp["connect-src"] == ["'self'", "https://accounts.google.com/gsi/"]
