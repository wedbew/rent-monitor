"""Paddle webhook signature verification (docs/PADDLE-INTEGRATION.md section 5).

`Paddle-Signature: ts=<unix>;h1=<hex>[;h1=<hex>...]`. The signed payload is `ts + ":" + raw body`,
HMAC-SHA256 with the notification destination's secret, compared in constant time. Several `h1` values
appear during secret rotation; any one that matches is enough. The timestamp must be within the tolerance
of the server clock in both directions. The check works on the raw bytes and runs before any JSON is
parsed or stored.
"""

import hashlib
import hmac
import time

MAX_HEADER_LEN = 1024
MAX_SIGNATURES = 4


class InvalidSignatureError(Exception):
    """The request was not signed by the configured secret, or is too old or too new."""


def sign(secret: str, body: bytes, *, timestamp: int) -> str:
    """The header value Paddle would send (tests and local tools)."""
    digest = hmac.new(secret.encode(), f"{timestamp}:".encode() + body, hashlib.sha256).hexdigest()
    return f"ts={timestamp};h1={digest}"


def verify(
    header: str | None, body: bytes, secrets: list[str], *, tolerance_s: int, now: float | None = None
) -> None:
    """Raise `InvalidSignatureError` unless the header proves `body` was signed by one of `secrets`."""
    if not header or len(header) > MAX_HEADER_LEN or not any(secrets):
        raise InvalidSignatureError
    timestamp: str | None = None
    signatures: list[str] = []
    for part in header.split(";"):
        key, sep, value = part.strip().partition("=")
        if not sep:
            raise InvalidSignatureError
        if key == "ts" and timestamp is None:
            timestamp = value
        elif key == "h1":
            signatures.append(value)
    if timestamp is None or not timestamp.isdecimal() or not signatures or len(signatures) > MAX_SIGNATURES:
        raise InvalidSignatureError
    if abs((now if now is not None else time.time()) - int(timestamp)) > tolerance_s:
        raise InvalidSignatureError
    payload = f"{timestamp}:".encode() + body
    for secret in secrets:
        if not secret:
            continue
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if any(hmac.compare_digest(expected, candidate) for candidate in signatures):
            return
    raise InvalidSignatureError
