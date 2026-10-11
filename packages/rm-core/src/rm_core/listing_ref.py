"""Parse a user-supplied listing reference into an Otodom short id, and nothing else.

LEGAL[url-analysis]: accepts and resolves user-supplied listing URLs / ids (RM-22).
Security: the result is only ever an id matching a strict pattern. The fetcher builds its own URL from it, so
a user cannot make the server request an arbitrary host (SSRF); hostile input is rejected before any I/O.
"""

import re
from urllib.parse import urlsplit

MAX_REF_LENGTH = 300
ALLOWED_HOSTS = frozenset({"otodom.pl", "www.otodom.pl"})
_SHORT_ID = re.compile(r"ID[0-9A-Za-z]{4,10}")
_URL_TAIL = re.compile(r"-(?P<short_id>ID[0-9A-Za-z]{4,10})/?$")


class InvalidListingRefError(ValueError):
    """The reference is not an Otodom listing URL or id."""


def parse_listing_ref(ref: str) -> str:
    value = ref.strip()
    if not value or len(value) > MAX_REF_LENGTH or not value.isprintable():
        raise InvalidListingRefError("not an Otodom listing URL or ID")
    if _SHORT_ID.fullmatch(value):
        return value
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise InvalidListingRefError("not an Otodom listing URL or ID") from exc
    if (
        parts.scheme not in {"http", "https"}
        or host not in ALLOWED_HOSTS
        or port not in {None, 80, 443}
        or parts.username is not None
        or parts.password is not None
        or "/oferta/" not in parts.path
    ):
        raise InvalidListingRefError("not an Otodom listing URL or ID")
    match = _URL_TAIL.search(parts.path)
    if not match:
        raise InvalidListingRefError("not an Otodom listing URL or ID")
    return match.group("short_id")
