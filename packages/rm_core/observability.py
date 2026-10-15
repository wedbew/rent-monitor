"""Error tracking via the Sentry SDK, sent to Better Stack (ADR 0009).

Off without a DSN; sends no personal data. GDPR[processor]: Better Stack receives only what survives
`scrub_event`
(RM-149): no request data, no stack-frame variables, no breadcrumb data, and no emails, tokens or
credentials inside
free text. If the scrubber itself fails the event is dropped, never sent unscrubbed.
"""

import re
from decimal import Decimal
from typing import Any, cast

import sentry_sdk
import structlog
from sentry_sdk.types import Event, Hint

from rm_core.logging import SENSITIVE_KEYS
from rm_core.settings import Settings

log = structlog.get_logger(__name__)
_DROP_HEADERS = frozenset({"authorization", "cookie", "set-cookie", "x-api-key", "stripe-signature"})
REDACTED = "[redacted]"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
# `#t=<magic-link token>`, `token=...`, `credential=...`, `code=...`, `session=...` in URLs or messages,
# also at the very start of a text or a line (RM-280 found `token=...` at the start escaping)
_PARAM = re.compile(
    r"(?im)((?:^|[#?&;\s])(?:t|token|id_token|credential|code|session|key|secret|password)=)[^&\s\"'#]+"
)


def redact_text(text: str) -> str:
    """Remove addresses, JWTs, bearer tokens and token-like URL parameters from free text."""
    text = _JWT.sub(REDACTED, text)
    text = _BEARER.sub("Bearer " + REDACTED, text)
    text = _PARAM.sub(r"\1" + REDACTED, text)
    return _EMAIL.sub("[email]", text)


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            k: (REDACTED if str(k).lower() in SENSITIVE_KEYS else _scrub_value(v))
            for k, v in cast("dict[Any, Any]", value).items()
        }
    if isinstance(value, list):
        return [_scrub_value(v) for v in cast("list[Any]", value)]
    return value


def _scrub_exception(event: dict[str, Any]) -> None:
    exception = event.get("exception")
    values = cast("dict[str, Any]", exception).get("values") if isinstance(exception, dict) else None
    if not isinstance(values, list):
        return
    for item in cast("list[Any]", values):
        if not isinstance(item, dict):
            continue
        exc = cast("dict[str, Any]", item)
        if isinstance(exc.get("value"), str):
            exc["value"] = redact_text(exc["value"])
        stacktrace = exc.get("stacktrace")
        frames = cast("dict[str, Any]", stacktrace).get("frames") if isinstance(stacktrace, dict) else None
        for frame in cast("list[Any]", frames) if isinstance(frames, list) else []:
            if isinstance(frame, dict):
                cast("dict[str, Any]", frame).pop("vars", None)  # local variables can hold anything


def _scrub_request(event: dict[str, Any]) -> None:
    request = event.get("request")
    if not isinstance(request, dict):
        return
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
    if isinstance(req.get("url"), str):
        req["url"] = redact_text(req["url"])


def _scrub_breadcrumbs(event: dict[str, Any]) -> None:
    breadcrumbs = event.get("breadcrumbs")
    crumbs = cast("dict[str, Any]", breadcrumbs).get("values") if isinstance(breadcrumbs, dict) else None
    for crumb in cast("list[Any]", crumbs) if isinstance(crumbs, list) else []:
        if isinstance(crumb, dict):
            c = cast("dict[str, Any]", crumb)
            c.pop("data", None)
            if isinstance(c.get("message"), str):
                c["message"] = redact_text(c["message"])


def _scrub_messages(event: dict[str, Any]) -> None:
    if isinstance(event.get("message"), str):
        event["message"] = redact_text(event["message"])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        entry = cast("dict[str, Any]", logentry)
        for key in ("message", "formatted"):
            if isinstance(entry.get(key), str):
                entry[key] = redact_text(entry[key])
        entry.pop("params", None)


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    """Remove cookies, auth headers, request bodies, frame variables, breadcrumb data and personal data in
    text."""
    _scrub_request(event)
    user = event.get("user")
    if isinstance(user, dict):
        usr = cast("dict[str, Any]", user)
        event["user"] = {"id": usr["id"]} if "id" in usr else {}
    _scrub_exception(event)
    _scrub_breadcrumbs(event)
    if isinstance(event.get("extra"), dict):
        event["extra"] = _scrub_value(event["extra"])
    _scrub_messages(event)
    return event


def _probability(value: Decimal) -> float:
    """A sampling probability, not money: the Sentry SDK API requires a float."""
    return float(value)


def _before_send(event: Event, _hint: Hint) -> Event | None:
    try:
        return cast("Event", scrub_event(cast("dict[str, Any]", event)))
    except Exception:  # fail closed: an event we could not scrub is not sent
        log.error("sentry_scrub_failed_event_dropped")
        return None


# GDPR[processor]: scrubbed error events and traces go to Better Stack via the Sentry SDK (ADR 0009)
def init_sentry(settings: Settings) -> bool:
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.release or None,
        traces_sample_rate=_probability(settings.sentry_traces_sample_rate),
        send_default_pii=False,
        include_local_variables=False,  # stack-frame variables can hold emails, tokens, credentials (L-013)
        before_send=_before_send,
    )
    return True
