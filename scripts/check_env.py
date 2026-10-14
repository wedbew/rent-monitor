"""Validate a deployment environment without ever printing a value (docs/RUNBOOK-DEPLOY.md, #15).

Usage (on the host, from the repo checkout):
    uv run python scripts/check_env.py [--env-file .env] [--private]

It reads the environment file (if given) and the process environment, builds the typed settings, and reports
problems by variable NAME and a short reason only. Exit status 1 when any ERROR is found. `--private` accepts
an http `PUBLIC_APP_URL` on localhost (an SSH-tunnelled private beta); public exposure needs https.
"""

import argparse
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict
from rm_core.billing_catalog import CatalogError, load_catalog
from rm_core.paddle import PaddleError, build_paddle_client
from rm_core.settings import Settings

DEV_PASSWORD = "dev-only-change-me"  # noqa: S105  (the documented local default; must never reach a server)
PLACEHOLDER = re.compile(
    r"^(changeme|change-me|xxx+|todo|needs you|your[-_ ].*|<.*>|example)$", re.IGNORECASE
)
MIN_DB_PASSWORD = 24
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


@dataclass(frozen=True)
class Finding:
    level: str  # ERROR | WARN
    name: str
    reason: str


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.match(value.strip()))


class _EnvOnlySettings(Settings):
    """The same settings, read from the process environment only (no stray `.env` in the cwd)."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")


class _Report:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def error(self, name: str, reason: str) -> None:
        self.findings.append(Finding("ERROR", name, reason))

    def warn(self, name: str, reason: str) -> None:
        self.findings.append(Finding("WARN", name, reason))


def _load_settings(env: Mapping[str, str], report: _Report) -> Settings | None:
    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(env)
        try:
            return _EnvOnlySettings()
        except ValidationError as exc:
            for err in exc.errors():  # the type of each problem only, never the offending input
                report.error(".".join(str(p) for p in err["loc"]).upper() or "SETTINGS", err["type"])
            return None
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _check_runtime(settings: Settings, env: Mapping[str, str], report: _Report, *, private: bool) -> None:
    if settings.app_env != "production":
        report.error("APP_ENV", "must be production on a server (secure cookies, no dev conveniences)")
    origin = settings.public_origin
    host = origin.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    if not origin.startswith("https://"):
        if private and host in LOCAL_HOSTS:
            report.warn("PUBLIC_APP_URL", "http on localhost: private beta through an SSH tunnel only")
        else:
            report.error("PUBLIC_APP_URL", "must be https (or --private with a localhost URL)")
    if not settings.database_url or not settings.psycopg_dsn:
        report.error("DATABASE_URL", "not set")
    if DEV_PASSWORD in settings.database_url or DEV_PASSWORD in settings.procrastinate_dsn:
        report.error("DATABASE_URL", "contains the local development password")
    password = env.get("POSTGRES_PASSWORD", "")
    if password == DEV_PASSWORD or len(password) < MIN_DB_PASSWORD:
        report.error(
            "POSTGRES_PASSWORD", f"missing, the dev default, or shorter than {MIN_DB_PASSWORD} characters"
        )
    if not settings.sentry_dsn:
        report.warn("SENTRY_DSN", "not set: errors are not tracked")


def _check_mail_and_sign_in(settings: Settings, report: _Report) -> None:
    if not settings.resend_api_key.get_secret_value():
        report.error("RESEND_API_KEY", "not set: sign-in and recovery mail cannot be sent")
    elif "onboarding@resend.dev" in settings.mail_sender:
        report.error("MAIL_FROM", "is the Resend onboarding sender; verify a domain first")
    if not settings.google_client_id:
        report.warn("GOOGLE_CLIENT_ID", "not set: Google sign-in is unavailable")


def _check_audits(settings: Settings, report: _Report) -> None:
    if settings.audit_providers != "real":
        report.warn("AUDIT_PROVIDERS", "none: every audit fails closed and releases its credit")
        return
    if settings.risk_free_rate is None:
        report.error(
            "RISK_FREE_RATE", "AUDIT_PROVIDERS=real needs it, or every audit ends CONTEXT_UNAVAILABLE"
        )
    if not settings.legal_scraping_enabled:
        report.warn("LEGAL_SCRAPING_ENABLED", "false: every audit will end UPSTREAM_BLOCKED")


def _check_billing(settings: Settings, report: _Report) -> None:
    if settings.billing_provider != "paddle":
        return
    try:
        load_catalog(settings)
        build_paddle_client(settings)
    except (CatalogError, PaddleError) as exc:
        report.error("BILLING_PROVIDER", str(exc))
    if not settings.paddle_webhook_secret.get_secret_value():
        report.error("PADDLE_WEBHOOK_SECRET", "not set")


def check(env: Mapping[str, str], *, private: bool = False) -> list[Finding]:
    report = _Report()
    for name, value in env.items():
        if value.lstrip().startswith("#"):
            report.error(name, "the value is a copied comment (empty value with an inline comment)")
        elif value and _is_placeholder(value):
            report.error(name, "still a placeholder")
    settings = _load_settings(env, report)
    if settings is None:
        return report.findings
    _check_runtime(settings, env, report, private=private)
    _check_mail_and_sign_in(settings, report)
    _check_audits(settings, report)
    _check_billing(settings, report)
    return report.findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    if args.env_file is not None:
        env = {**parse_env_file(args.env_file), **env}
    findings = check(env, private=args.private)
    for f in findings:
        print(f"{f.level:5} {f.name}: {f.reason}")
    errors = sum(f.level == "ERROR" for f in findings)
    print(f"check_env: {errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
