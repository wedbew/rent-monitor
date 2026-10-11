"""structlog JSON logging (blueprint §4.2). No print, no loguru.

Personal data and secrets are redacted by key name.

Context variables `request_id`, `user_id`, `audit_id`, `job_id` are bound with `bind_context` and appear on
every line, including lines emitted by stdlib loggers such as uvicorn.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, Processor

# GDPR[personal-data]: values logged under these keys are replaced; log ids and tag names instead of values.
SENSITIVE_KEYS = frozenset(
    {
        "email",
        "name",
        "phone",
        "ip",
        "user_agent",
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "token",
        "secret",
        "api_key",
        "id_token",
        "session",
    }
)
REDACTED = "[redacted]"
CONTEXT_KEYS = ("request_id", "user_id", "audit_id", "job_id")


def redact(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    for key in event_dict:
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
    return event_dict


def bind_context(**values: str | int | None) -> None:
    """Bind ids for the current task; `None` values are skipped."""
    structlog.contextvars.bind_contextvars(**{k: v for k, v in values.items() if v is not None})


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()


def configure_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    renderer: Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn installs its own handlers; route them through the root JSON handler instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
