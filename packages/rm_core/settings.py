"""Typed settings. Names mirror `.env.example`; real values come from the environment only."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    free_signup_credits: int = Field(default=3, ge=0)
    pro_monthly_audit_allowance: int = Field(default=40, ge=0)  # placeholder until COGS is measured
    past_due_grace_days: int = Field(default=7, ge=0)

    worker_audit_concurrency: int = Field(default=1, ge=1)
    worker_batch_concurrency: int = Field(default=1, ge=1)
    audit_job_timeout_s: int = Field(default=900, ge=1)

    openrouter_api_key: SecretStr = Field(  # blueprint §4.2 spells it OPEN_ROUTER_API_KEY
        default=SecretStr(""), validation_alias=AliasChoices("OPEN_ROUTER_API_KEY", "OPENROUTER_API_KEY")
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_monthly_budget_usd: Decimal = Field(default=Decimal("50"), ge=0)
    openrouter_call_estimate_usd: Decimal = Field(
        default=Decimal("0.02"), ge=0
    )  # placeholder until L-003 is measured
    nominatim_user_agent: str = (
        "RentMonitor/1.0 (set-an-ops-contact)"  # OSM policy: identify yourself with a contact
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
        "RentMonitor <onboarding@resend.dev>"  # local test sender; production needs a verified domain
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
