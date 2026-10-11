"""Sentry initialisation. Off without a DSN; sends no personal data (scrubbed)."""

from decimal import Decimal
from typing import Any, cast

import sentry_sdk
from sentry_sdk.types import Event, Hint

from rm_core.settings import Settings

_DROP_HEADERS = frozenset({"authorization", "cookie", "set-cookie", "x-api-key", "stripe-signature"})


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    """Remove cookies, auth headers, request bodies and user identifiers from an event."""
    request = event.get("request")
    if isinstance(request, dict):
        req = cast("dict[str, Any]", request)
        for key in ("cookies", "data", "query_string"):
            req.pop(key, None)
        headers = req.get("headers")
        if isinstance(headers, dict):
            req["headers"] = {
                str(k): v
                for k, v in cast("dict[Any, Any]", headers).items()
                if str(k).lower() not in _DROP_HEADERS
            }
    user = event.get("user")
    if isinstance(user, dict):
        usr = cast("dict[str, Any]", user)
        event["user"] = {"id": usr["id"]} if "id" in usr else {}
    return event


def _probability(value: Decimal) -> float:
    """A sampling probability, not money: the Sentry SDK API requires a float."""
    return float(value)


def _before_send(event: Event, _hint: Hint) -> Event | None:
    return cast("Event", scrub_event(cast("dict[str, Any]", event)))


def init_sentry(settings: Settings) -> bool:
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.release or None,
        traces_sample_rate=_probability(settings.sentry_traces_sample_rate),
        send_default_pii=False,
        before_send=_before_send,
    )
    return True
