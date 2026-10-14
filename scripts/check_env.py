"""Secret-safe check of an env file before a deploy: names and shapes only, values are never printed.

    uv run python scripts/check_env.py /path/to/.env --target vps

Exit 0 when nothing is blocking, 1 otherwise. Messages name the variable and the rule, never the value,
so the output is safe to paste into a PR or an issue. `--target local` only checks that the file parses.
"""

import argparse
import sys
from pathlib import Path

PLACEHOLDERS = {"change-me", "dev-only-change-me", "changeme", "password", "secret"}
REQUIRED_FOR_VPS = ("POSTGRES_PASSWORD", "PUBLIC_APP_URL", "APP_ENV")
MIN_PASSWORD_LEN = 24
SECRET_NAME_PARTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "DSN")


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip()
        if value[:1] in ('"', "'") and value.count(value[0]) >= 2:
            value = value[1 : value.index(value[0], 1)]
        else:
            value = value.split(" #", 1)[0].strip()
        values[name.strip()] = value
    return values


def is_secret_name(name: str) -> bool:
    return any(part in name for part in SECRET_NAME_PARTS)


def check(values: dict[str, str], target: str) -> list[str]:
    """Returns blocking problems as 'NAME: rule' strings. Never includes a value."""
    if target == "local":
        return []
    problems = [
        f"{n}: required on the VPS and empty or missing" for n in REQUIRED_FOR_VPS if not values.get(n)
    ]
    if values.get("APP_ENV") and values["APP_ENV"] != "production":
        problems.append("APP_ENV: must be 'production' on the VPS")
    url = values.get("PUBLIC_APP_URL", "")
    if url and not url.startswith("https://"):
        problems.append("PUBLIC_APP_URL: must start with https:// on the VPS")
    password = values.get("POSTGRES_PASSWORD", "")
    if password.lower() in PLACEHOLDERS:
        problems.append("POSTGRES_PASSWORD: is a placeholder value")
    elif password and len(password) < MIN_PASSWORD_LEN:
        problems.append(f"POSTGRES_PASSWORD: shorter than {MIN_PASSWORD_LEN} characters")
    for name in ("DATABASE_URL", "PROCRASTINATE_DSN"):
        if any(host in values.get(name, "") for host in ("localhost", "127.0.0.1")):
            problems.append(f"{name}: points at localhost; compose sets the in-network URL itself, remove it")
    if values.get("BILLING_PROVIDER", "disabled") == "paddle" and values.get("PADDLE_ENVIRONMENT") != "live":
        problems.append(
            "PADDLE_ENVIRONMENT: BILLING_PROVIDER=paddle on the VPS needs 'live'; keep billing disabled"
        )
    if (
        values.get("AUDIT_PROVIDERS") == "real"
        and values.get("LEGAL_SCRAPING_ENABLED", "true").lower() != "true"
    ):
        problems.append(
            "LEGAL_SCRAPING_ENABLED: false with AUDIT_PROVIDERS=real ends every audit UPSTREAM_BLOCKED"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("env_file", type=Path)
    parser.add_argument("--target", choices=("local", "vps"), default="vps")
    args = parser.parse_args(argv)
    if not args.env_file.is_file():
        print(f"check_env: {args.env_file} not found", file=sys.stderr)
        return 1
    values = parse_env(args.env_file.read_text(encoding="utf-8"))
    problems = check(values, args.target)
    secrets_set = sorted(n for n, v in values.items() if is_secret_name(n) and v)
    print(f"check_env: {len(values)} variables; secret-like names set: {', '.join(secrets_set) or 'none'}")
    for problem in problems:
        print(f"check_env: BLOCKING {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"check_env: OK for target {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
