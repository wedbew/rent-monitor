"""Google ID-token verification with a throwaway key: signature, audience, issuer, expiry, claims, key
rotation."""

import asyncio
import base64
import json
from collections.abc import Callable, Mapping

import httpx
import pytest
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from rm_api.auth.google import (
    GoogleCerts,
    GoogleEmailUnverified,
    GoogleUnavailable,
    GoogleVerifier,
    InvalidGoogleToken,
)

MakeToken = Callable[..., str]


class FakeCerts:
    def __init__(self, certs: Mapping[str, str], rotated: Mapping[str, str] | None = None) -> None:
        self.certs, self.rotated = dict(certs), dict(rotated or {})
        self.calls: list[bool] = []

    async def get(self, *, refresh: bool = False) -> Mapping[str, str]:
        self.calls.append(refresh)
        if refresh and self.rotated:
            self.certs = self.rotated
        return self.certs


def verifier(keys: GoogleKeys, certs: FakeCerts | None = None) -> GoogleVerifier:
    return GoogleVerifier(GOOGLE_AUDIENCE, certs or FakeCerts(keys.certs))


async def test_a_valid_token_yields_normalised_claims(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    claims = await verifier(google_keys).verify(make_google_token(email="  Investor@Example.TEST "))
    assert claims.sub == "google-sub-1"
    assert claims.email == "investor@example.test"
    assert claims.email_verified is True


@pytest.mark.parametrize("verified", ["true", "TRUE"])
async def test_google_sometimes_sends_email_verified_as_a_string(
    google_keys: GoogleKeys, make_google_token: MakeToken, verified: str
) -> None:
    claims = await verifier(google_keys).verify(make_google_token(email_verified=verified))
    assert claims.email_verified is True


async def test_wrong_audience_is_rejected(google_keys: GoogleKeys, make_google_token: MakeToken) -> None:
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(make_google_token(aud="someone-elses-client"))


async def test_an_expired_token_is_rejected(google_keys: GoogleKeys, make_google_token: MakeToken) -> None:
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(make_google_token(exp_in=-3600))


async def test_a_token_signed_by_another_key_is_rejected(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(make_google_token(signer=google_keys.other_signer))


async def test_a_tampered_payload_is_rejected(google_keys: GoogleKeys, make_google_token: MakeToken) -> None:
    header, payload, signature = make_google_token().split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["email"] = "victim@example.test"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(f"{header}.{forged}.{signature}")


async def test_alg_none_is_rejected(google_keys: GoogleKeys, make_google_token: MakeToken) -> None:
    _, payload, _ = make_google_token().split(".")
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT", "kid": "test-key-1"}).encode())
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(f"{header.rstrip(b'=').decode()}.{payload}.")


@pytest.mark.parametrize("junk", ["", "not-a-jwt", "a.b.c", "....", "x" * 5000])
async def test_garbage_is_rejected_not_crashed(google_keys: GoogleKeys, junk: str) -> None:
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(junk)


async def test_a_wrong_issuer_is_rejected(google_keys: GoogleKeys, make_google_token: MakeToken) -> None:
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(make_google_token(iss="https://evil.example.test"))


async def test_the_bare_google_issuer_is_accepted(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    claims = await verifier(google_keys).verify(make_google_token(iss="accounts.google.com"))
    assert claims.sub


@pytest.mark.parametrize("verified", [False, "false", None, 1, "yes"])
async def test_unverified_email_is_a_distinct_error(
    google_keys: GoogleKeys, make_google_token: MakeToken, verified: object
) -> None:
    with pytest.raises(GoogleEmailUnverified):
        await verifier(google_keys).verify(make_google_token(email_verified=verified))


async def test_a_token_without_an_email_or_sub_is_rejected(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(make_google_token(email=None))
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys).verify(make_google_token(sub=""))


async def test_an_unknown_key_id_refreshes_certificates_once(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    certs = FakeCerts({"old-key": google_keys.public_pem}, rotated=google_keys.certs)
    claims = await verifier(google_keys, certs).verify(make_google_token())
    assert claims.sub
    assert certs.calls == [False, True]


async def test_an_unknown_key_id_after_refresh_is_just_invalid(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    certs = FakeCerts({"old-key": google_keys.public_pem})
    with pytest.raises(InvalidGoogleToken):
        await verifier(google_keys, certs).verify(make_google_token())
    assert certs.calls == [False, True]  # one refresh, not a loop


async def test_without_a_client_id_google_sign_in_is_unavailable(
    google_keys: GoogleKeys, make_google_token: MakeToken
) -> None:
    with pytest.raises(GoogleUnavailable):
        await GoogleVerifier("", FakeCerts(google_keys.certs)).verify(make_google_token())


# ---------- the certificate cache ----------
def cert_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_certificates_are_cached_for_their_max_age() -> None:
    now = [0.0]
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"k": "PEM"}, headers={"cache-control": "public, max-age=600"})

    certs = GoogleCerts(cert_client(handler), clock=lambda: now[0])
    assert await certs.get() == {"k": "PEM"}
    now[0] = 599
    await certs.get()
    assert len(calls) == 1
    now[0] = 601
    await certs.get()
    assert len(calls) == 2


async def test_many_concurrent_callers_cause_one_fetch() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"k": "PEM"})

    certs = GoogleCerts(cert_client(handler))
    await asyncio.gather(*(certs.get() for _ in range(25)))
    assert len(calls) == 1


async def test_a_fetch_failure_without_a_cache_is_unavailable() -> None:
    certs = GoogleCerts(cert_client(lambda r: httpx.Response(503)))
    with pytest.raises(GoogleUnavailable):
        await certs.get()


@pytest.mark.parametrize("body", [[], {}, {"k": 1}, "text"])
async def test_a_malformed_certificate_document_is_unavailable(body: object) -> None:
    certs = GoogleCerts(cert_client(lambda r: httpx.Response(200, json=body)))
    with pytest.raises(GoogleUnavailable):
        await certs.get()


async def test_stale_certificates_are_served_when_a_refresh_fails() -> None:
    now = [0.0]
    ok = [True]

    def handler(request: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(200, json={"k": "PEM"}, headers={"cache-control": "max-age=60"})
            if ok[0]
            else httpx.Response(500)
        )

    certs = GoogleCerts(cert_client(handler), clock=lambda: now[0])
    await certs.get()
    ok[0], now[0] = False, 120
    assert await certs.get() == {"k": "PEM"}  # last good set, not an outage


# ---------- D-13: is Google authoritative for the address? ----------
@pytest.mark.parametrize(
    ("email", "hd", "expected"),
    [
        ("a@gmail.com", None, True),
        ("a@GMAIL.com", None, True),
        ("a@gmail.com", "other.example", True),  # a gmail address is gmail whatever hd says
        ("a@company.example", "company.example", True),
        ("a@company.example", "COMPANY.example ", True),
        ("a@company.example", None, False),
        ("a@company.example", "", False),
        ("a@company.example", "evil.example", False),
        ("a@sub.company.example", "company.example", False),
        ("a@googlemail.com", None, False),
        ("a@gmail.com.evil.test", None, False),
    ],
)
async def test_google_is_authoritative_only_for_gmail_or_a_matching_workspace_domain(
    google_keys: GoogleKeys, make_google_token: MakeToken, email: str, hd: str | None, expected: bool
) -> None:
    extra = {"hd": hd} if hd is not None else None
    claims = await verifier(google_keys).verify(make_google_token(email=email, extra=extra))
    assert claims.authoritative is expected
