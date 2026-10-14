"""Typed settings. Names mirror `.env.example`; real values come from the environment only."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_APP_NAME = "Renti"  # the product name users see; override with APP_NAME


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field(
        default=DEFAULT_APP_NAME, min_length=1, max_length=40
    )  # shown in mail and the API docs
    app_env: Literal["development", "test", "production"] = "development"
    public_app_url: str = "http://localhost"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = ""
    procrastinate_dsn: str = ""

    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr(
        ""
    )  # only for a server-side code flow; ID-token sign-in needs the ID alone
    session_cookie_name: str = "rm_session"  # production adds the `__Host-` prefix (cookie_name property)
    session_ttl_days: int = Field(default=30, ge=1)
    magic_link_ttl_minutes: int = Field(default=30, ge=1)
    # Email/password sign-in (ADR 0013, docs/PASSWORD-AUTH-SPEC.md). Argon2id defaults are the OWASP minimum;
    # raise them after measuring on the VPS (L-019). Hashes are rehashed on login when these change.
    password_argon2_memory_kib: int = Field(default=19456, ge=8192, le=1048576)
    password_argon2_time_cost: int = Field(default=2, ge=1, le=10)
    password_argon2_parallelism: int = Field(default=1, ge=1, le=8)
    password_hash_concurrency: int = Field(default=2, ge=1, le=8)  # simultaneous hashes per API process
    register_token_ttl_hours: int = Field(default=24, ge=1)
    reset_token_ttl_minutes: int = Field(default=30, ge=1)

    free_signup_credits: int = Field(default=3, ge=0)
    pro_monthly_audit_allowance: int = Field(default=40, ge=0)  # placeholder until COGS is measured
    past_due_grace_days: int = Field(default=7, ge=0)

    worker_audit_concurrency: int = Field(default=1, ge=1)
    worker_batch_concurrency: int = Field(default=1, ge=1)
    audit_job_timeout_s: int = Field(default=900, ge=1)
    # `real` wires the Otodom client and the market-data store into the worker; `none` (default) fails every
    # audit closed and releases the credit, so a half-configured host never pretends to analyse (#187).
    audit_providers: Literal["none", "real"] = "none"
    # LEGAL[scraping]: kill switch for fetching listing pages; off ends audits `UPSTREAM_BLOCKED` (RM-187).
    legal_images_enabled: bool = True  # LEGAL[images] kill switch: false skips vision/OCR (degraded audits)
    legal_scraping_enabled: bool = True
    # Owner input until the macro source exists (ENGINE-SPEC row 9, N-12): PL 10Y yield as a fraction, e.g.
    # 0.055. Unset means audits end CONTEXT_UNAVAILABLE rather than run on an invented rate.
    risk_free_rate: Decimal | None = Field(default=None, gt=0, lt=1)
    # Paddle report packs (docs/PADDLE-INTEGRATION.md). `disabled` needs no credentials and is the default.
    billing_provider: Literal["disabled", "paddle"] = "disabled"
    paddle_environment: Literal["sandbox", "live"] = "sandbox"
    paddle_api_key: SecretStr = SecretStr("")
    paddle_webhook_secret: SecretStr = SecretStr("")
    paddle_webhook_secret_previous: SecretStr = SecretStr("")  # during a secret rotation only
    paddle_webhook_tolerance_s: int = Field(default=5, ge=1, le=300)  # Paddle SDK default
    retention_billing_event_days: int = Field(default=90, ge=1)  # GDPR[retention]: technical event log
    paddle_client_token: str = ""  # public Paddle.js token for the Phase 2 checkout; never the API key
    paddle_price_reports_1: str = ""  # the environment's approved `pri_...` ids
    paddle_price_reports_5: str = ""
    paddle_price_reports_10: str = ""
    # Owner-approved gross amounts in PLN minor units, e.g. "reports_1=1000,reports_5=4000,reports_10=7000".
    # No default: prices are the owner's decision, and sales stay off until all three are approved here.
    paddle_approved_amounts: str = ""
    audit_child_memory_mb: int = Field(default=1024, ge=128)  # RLIMIT_AS of the engine child process (#186)

    openrouter_api_key: SecretStr = Field(  # blueprint §4.2 spells it OPEN_ROUTER_API_KEY
        default=SecretStr(""), validation_alias=AliasChoices("OPEN_ROUTER_API_KEY", "OPENROUTER_API_KEY")
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_monthly_budget_usd: Decimal = Field(default=Decimal("50"), ge=0)
    openrouter_call_estimate_usd: Decimal = Field(
        default=Decimal("0.02"), ge=0
    )  # placeholder until L-003 is measured
    # Placeholder model until L-003 / #94 measure quality and cost; any OpenRouter vision model id works.
    openrouter_vision_model: str = Field(default="google/gemini-2.5-flash-lite", min_length=1, max_length=120)
    nominatim_user_agent: str = (
        f"{DEFAULT_APP_NAME}/1.0 (set-an-ops-contact)"  # OSM policy: identify yourself with a contact
    )
    image_host_allowlist: str = (
        "olxcdn.com,otodom.pl"  # comma-separated host suffixes photos may be fetched from
    )

    # GDPR[retention]: PROPOSED periods, to be confirmed by counsel (docs/BLOCKERS.md B-012).
    retention_session_days: int = Field(default=7, ge=0)  # days after `expires_at`
    retention_login_token_days: int = Field(default=1, ge=0)  # days after expiry or use
    retention_snapshot_days: int = Field(default=30, ge=1)  # raw listing payloads (may hold seller data)
    retention_audit_event_days: int = Field(default=30, ge=1)  # progress events; the audit result is kept

    resend_api_key: SecretStr = SecretStr("")  # empty: development logs the magic link instead of sending it
    mail_from: str = (
        f"{DEFAULT_APP_NAME} <onboarding@resend.dev>"  # local test sender; production needs a verified domain
    )

    # Better Stack heartbeat URLs carry their own secret; empty means that monitor is off
    # (docs/OBSERVABILITY-SPEC.md section 4).
    betterstack_heartbeat_ledger_url: SecretStr = SecretStr("")
    betterstack_heartbeat_retention_url: SecretStr = SecretStr("")

    sentry_dsn: str = ""
    sentry_traces_sample_rate: Decimal = Field(
        default=Decimal("0.05"), ge=0, le=1
    )  # a probability; Decimal keeps floats out of settings
    release: str = ""  # image tag / git sha, set by the deploy

    @property
    def cookie_name(self) -> str:
        """`__Host-` requires Secure, Path=/ and no Domain: only possible over HTTPS, so production only."""
        return (
            f"__Host-{self.session_cookie_name}" if self.app_env == "production" else self.session_cookie_name
        )

    @property
    def psycopg_dsn(self) -> str:
        """Plain libpq DSN for LISTEN/NOTIFY and Procrastinate (the SQLAlchemy URL minus its driver
        suffix)."""
        return self.procrastinate_dsn or self.database_url.replace(
            "postgresql+psycopg://", "postgresql://", 1
        )

    @property
    def public_origin(self) -> str:
        return self.public_app_url.strip().rstrip("/").lower()

    @property
    def image_hosts(self) -> tuple[str, ...]:
        return tuple(h.strip().lower() for h in self.image_host_allowlist.split(",") if h.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
