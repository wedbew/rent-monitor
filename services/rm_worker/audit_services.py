"""The process-wide `AuditServices`, set once at worker start (production wiring: #187) or by a test.

Unset (and `AUDIT_PROVIDERS` not `real`) means no listing source or market context is configured: the task
then fails closed (the audit ends `failed_internal` and the credit is released, see
`audit_pipeline.fail_unconfigured`) instead of pretending to analyse anything.
"""

from rm_core.settings import get_settings

from rm_worker.audit_pipeline import AuditServices
from rm_worker.audit_wiring import build_audit_services

_services: AuditServices | None = None


class NotConfiguredError(RuntimeError):
    """No `AuditServices` registered in this process."""


def configure(services: AuditServices | None) -> None:
    global _services  # noqa: PLW0603
    _services = services


def get() -> AuditServices:
    """The registered services; otherwise built once from settings when `AUDIT_PROVIDERS=real`."""
    global _services  # noqa: PLW0603
    if _services is None:
        _services = build_audit_services(get_settings())
    if _services is None:
        msg = "audit services are not configured (set AUDIT_PROVIDERS=real)"
        raise NotConfiguredError(msg)
    return _services
