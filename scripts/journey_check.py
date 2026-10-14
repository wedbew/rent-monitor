"""Deployed-journey check: sign in, submit a listing, wait for a terminal state, read the result back.

    JOURNEY_EMAIL=... JOURNEY_PASSWORD=... uv run python scripts/journey_check.py \
        --base-url http://127.0.0.1:8000 --listing <otodom id or URL>

Credentials come from the environment only and are never printed. The check passes when the audit reaches
*any* terminal state with its charge settled (captured or released): with `AUDIT_PROVIDERS=none` the expected
outcome is a failed audit with a released credit, which proves API -> Postgres -> queue -> worker -> ledger
end to end. Use `--expect success` once providers are real. It also checks that an unauthenticated read is
refused.

LEGAL[url-analysis]: submits a user-chosen listing reference to our own API (RM-224).
"""

import argparse
import os
import sys
import time
from collections.abc import Callable

import httpx

TERMINAL = {
    "succeeded",
    "succeeded_degraded",
    "rejected",
    "failed_input",
    "failed_upstream",
    "failed_internal",
    "cancelled",
}
SUCCESS = {"succeeded", "succeeded_degraded"}
SETTLED = {"captured", "released"}


class JourneyError(Exception):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise JourneyError(message)


def run_journey(
    client: httpx.Client,
    *,
    email: str,
    password: str,
    listing: str,
    origin: str,
    expect: str = "settled",
    timeout_s: float = 300.0,
    poll_s: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    anonymous: httpx.Client | None = None,
) -> list[str]:
    """Runs the steps and returns one human line per passed step. Raises JourneyError on the first failure."""
    steps: list[str] = []
    headers = {"Origin": origin}

    health = client.get("/api/health")
    _require(health.status_code == 200, f"/api/health returned {health.status_code}")
    steps.append("health ok")

    login = client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
    _require(login.status_code == 200, f"login returned {login.status_code}")
    steps.append("login ok")

    created = client.post("/api/audits", json={"listing_ref": listing}, headers=headers)
    _require(created.status_code == 202, f"POST /api/audits returned {created.status_code}")
    audit_id = created.json()["audit_id"]
    steps.append(f"audit accepted {audit_id}")

    deadline = time.monotonic() + timeout_s
    audit: dict[str, object] = {}
    while True:
        got = client.get(f"/api/audits/{audit_id}")
        _require(got.status_code == 200, f"GET audit returned {got.status_code}")
        audit = got.json()
        if audit["status"] in TERMINAL:
            break
        _require(time.monotonic() < deadline, f"audit still {audit['status']} after {timeout_s:.0f} s")
        sleep(poll_s)
    status, charge = str(audit["status"]), str(audit["charge_state"])
    steps.append(f"terminal {status}, charge {charge}")

    _require(charge in SETTLED, f"charge_state {charge} is not settled")
    if expect == "success":
        _require(status in SUCCESS and audit.get("result") is not None, f"expected success, got {status}")
    elif status in SUCCESS:
        _require(charge == "captured", "a successful audit must capture its credit")
    else:
        _require(charge == "released", "a failed audit must release its credit")

    if anonymous is None:  # a second client without the session cookie: only the session may grant access
        anonymous = httpx.Client(base_url=str(client.base_url), timeout=client.timeout)
    with anonymous:
        refused = anonymous.get(f"/api/audits/{audit_id}")
    _require(refused.status_code in (401, 404), f"anonymous read returned {refused.status_code}")
    steps.append(f"anonymous read refused ({refused.status_code})")
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--listing", required=True)
    parser.add_argument("--origin", default=None, help="defaults to PUBLIC_APP_URL, else the base URL")
    parser.add_argument("--expect", choices=("settled", "success"), default="settled")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(argv)
    email, password = os.environ.get("JOURNEY_EMAIL", ""), os.environ.get("JOURNEY_PASSWORD", "")
    if not email or not password:
        print("journey_check: set JOURNEY_EMAIL and JOURNEY_PASSWORD in the environment", file=sys.stderr)
        return 2
    origin = args.origin or os.environ.get("PUBLIC_APP_URL") or args.base_url
    try:
        with httpx.Client(base_url=args.base_url, timeout=15.0) as client:
            steps = run_journey(
                client,
                email=email,
                password=password,
                listing=args.listing,
                origin=origin,
                expect=args.expect,
                timeout_s=args.timeout,
            )
    except (JourneyError, httpx.HTTPError) as exc:
        print(f"journey_check: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for step in steps:
        print(f"journey_check: {step}")
    print("journey_check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
