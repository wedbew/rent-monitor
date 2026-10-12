"""Google ID-token verification (blueprint §2 Auth decision, "Google first").

GDPR[processor]: Google authenticates the person; we receive email, name and picture claims (RM-12).
No OAuth redirect and no client secret: the SPA posts the signed `credential` from Google Identity Services.

The blueprint sketch used `google.oauth2.id_token` over `requests`; `requests` is banned in `services/` and
its
transport blocks, so we fetch Google's public certificates ourselves over the shared `httpx` client (explicit
timeouts, cached by `Cache-Control`) and use `google.auth.jwt.decode` for signature, audience and expiry.
"""

import asyncio
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

import httpx
import structlog
from google.auth import jwt as google_jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = structlog.get_logger(__name__)
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
CLOCK_SKEW_S = 10
CERTS_MIN_TTL_S = 60
CERTS_MAX_TTL_S = 86_400
CERTS_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
MAX_CERTS_BYTES = 64 * 1024

# google-auth ships without complete type information; these adapters pin the shapes we rely on.
_decode_header = cast(Callable[[str], Mapping[str, Any]], google_jwt.decode_header)  # pyright: ignore[reportUnknownMemberType]
_decode = cast(Callable[..., Mapping[str, Any]], google_jwt.decode)  # pyright: ignore[reportUnknownMemberType]


class InvalidGoogleToken(Exception):
    """Bad signature, wrong audience or issuer, expired, malformed, or missing claims."""


class GoogleEmailUnverified(Exception):
    """A valid token whose email Google has not verified: no account may be created from it."""


class GoogleUnavailable(Exception):
    """Google's certificates cannot be fetched and none are cached; not the caller's fault (503)."""


class GoogleClaims(BaseModel):
    """GDPR[personal-data]: email, name, picture. Only validated, bounded values leave this module."""

    model_config = ConfigDict(extra="ignore")
    sub: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=254)
    email_verified: bool
    name: str | None = Field(default=None, max_length=200)
    picture: str | None = Field(default=None, max_length=500)
    hd: str | None = Field(default=None, max_length=255)  # hosted domain: set for Google Workspace accounts

    @property
    def authoritative(self) -> bool:
        """Whether Google can vouch for ownership of this address (docs/adr/0010, owner decision D-13).

        Google says it is authoritative only for `@gmail.com` addresses and for Workspace accounts (`hd`
        claim). For any other
        address `email_verified` does not prove the holder controls the mailbox's domain, so it must not
        link to or create an
        account. An `hd` that differs from the address's own domain is not trusted.
        """
        address = self.email.strip().lower()
        domain = address.rpartition("@")[2]
        if domain == "gmail.com":
            return True
        return self.hd is not None and self.hd.strip().lower() == domain


class CertSource(Protocol):
    async def get(self, *, refresh: bool = False) -> Mapping[str, str]: ...


class GoogleCerts:
    """Google's current signing certificates, fetched at most once per `max-age` (and once on an unknown key
    id)."""

    def __init__(self, http: httpx.AsyncClient, clock: Callable[[], float] = time.monotonic) -> None:
        self._http = http
        self._clock = clock
        self._certs: dict[str, str] = {}
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def get(self, *, refresh: bool = False) -> Mapping[str, str]:
        if self._certs and not refresh and self._clock() < self._expires:
            return self._certs
        async with self._lock:
            if (
                self._certs and not refresh and self._clock() < self._expires
            ):  # another task refreshed meanwhile
                return self._certs
            try:
                response = await self._http.get(GOOGLE_CERTS_URL, timeout=CERTS_TIMEOUT)
                response.raise_for_status()
                if len(response.content) > MAX_CERTS_BYTES:
                    raise ValueError("certificate document too large")
                body: Any = response.json()
                if not isinstance(body, dict) or not body:
                    raise ValueError("certificate document is not an object")
                items = cast(dict[str, Any], body)
                certs = {k: v for k, v in items.items() if isinstance(v, str)}
                if not certs:
                    raise ValueError("no certificates in document")
            except (httpx.HTTPError, ValueError) as exc:
                if (
                    self._certs
                ):  # keep serving the last good set for a short while rather than lock everyone out
                    log.warning("google_certs_refresh_failed", error=type(exc).__name__)
                    self._expires = self._clock() + CERTS_MIN_TTL_S
                    return self._certs
                raise GoogleUnavailable(type(exc).__name__) from exc
            self._certs = certs
            self._expires = self._clock() + _ttl(response.headers.get("cache-control", ""))
            return self._certs


def _ttl(cache_control: str) -> float:
    match = re.search(r"max-age=(\d+)", cache_control)
    seconds = int(match.group(1)) if match else CERTS_MIN_TTL_S
    return float(min(max(seconds, CERTS_MIN_TTL_S), CERTS_MAX_TTL_S))


class GoogleVerifier:
    def __init__(self, client_id: str, certs: CertSource) -> None:
        self._client_id = client_id
        self._certs = certs

    @property
    def configured(self) -> bool:
        return bool(self._client_id)

    async def verify(self, credential: str) -> GoogleClaims:
        """Return the validated claims of a Google ID token, or raise one of the three exceptions above."""
        if not self.configured:
            raise GoogleUnavailable("GOOGLE_CLIENT_ID is not set")
        try:
            header = _decode_header(credential)
        except (ValueError, TypeError) as exc:
            raise InvalidGoogleToken("malformed token") from exc
        certs = await self._certs.get()
        kid = header.get("kid")
        if isinstance(kid, str) and kid not in certs:  # Google rotated keys: refresh once, then decide
            certs = await self._certs.get(refresh=True)
        try:
            payload: Mapping[str, Any] = await asyncio.to_thread(
                _decode,
                credential,
                certs=dict(certs),
                audience=self._client_id,
                clock_skew_in_seconds=CLOCK_SKEW_S,
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise InvalidGoogleToken(type(exc).__name__) from exc
        if payload.get("iss") not in ISSUERS:
            raise InvalidGoogleToken("wrong issuer")
        raw_verified = payload.get("email_verified")
        verified = raw_verified is True or (isinstance(raw_verified, str) and raw_verified.lower() == "true")
        try:
            claims = GoogleClaims.model_validate({**payload, "email_verified": verified})
        except ValidationError as exc:
            raise InvalidGoogleToken("missing or invalid claims") from exc
        if not claims.email_verified:
            raise GoogleEmailUnverified
        return claims.model_copy(update={"email": claims.email.strip().lower()})
