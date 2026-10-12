"""The process-wide `AuditServices`, set once at worker start (production wiring: #187) or by a test.

Unset means no listing source or market context is configured: the task then fails closed (the audit ends
`failed_internal` and the credit is released, see `audit_pipeline.fail_unconfigured`) instead of pretending
to analyse anything.
"""

from rm_worker.audit_pipeline import AuditServices

_services: AuditServices | None = None


class NotConfiguredError(RuntimeError):
    """No `AuditServices` registered in this process."""


def configure(services: AuditServices | None) -> None:
    global _services  # noqa: PLW0603
    _services = services


def get() -> AuditServices:
    if _services is None:
        msg = "audit services are not configured (production adapters arrive with #187)"
        raise NotConfiguredError(msg)
    return _services
