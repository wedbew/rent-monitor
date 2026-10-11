"""Typed settings. Names mirror `.env.example`; real values come from the environment only."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    session_cookie_name: str = "rm_session"
    session_ttl_days: int = Field(default=30, ge=1)
    magic_link_ttl_minutes: int = Field(default=30, ge=1)

    free_signup_credits: int = Field(default=3, ge=0)
    pro_monthly_audit_allowance: int = Field(default=40, ge=0)  # placeholder until COGS is measured
    past_due_grace_days: int = Field(default=7, ge=0)

    worker_audit_concurrency: int = Field(default=1, ge=1)
    worker_batch_concurrency: int = Field(default=1, ge=1)
    audit_job_timeout_s: int = Field(default=900, ge=1)

    sentry_dsn: str = ""
    sentry_traces_sample_rate: Decimal = Field(
        default=Decimal("0.05"), ge=0, le=1
    )  # a probability; Decimal keeps floats out of settings
    release: str = ""  # image tag / git sha, set by the deploy


@lru_cache
def get_settings() -> Settings:
    return Settings()
