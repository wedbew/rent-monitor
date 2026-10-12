"""Google ID tokens signed with a throwaway key: no network, no real Google. Shared by unit and integration
tests."""

import time
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt as google_crypt
from google.auth import jwt as google_jwt

GOOGLE_AUDIENCE = "test-client-id.apps.googleusercontent.com"
GOOGLE_KID = "test-key-1"


@dataclass(frozen=True)
class GoogleKeys:
    public_pem: str
    signer: google_crypt.RSASigner
    other_signer: google_crypt.RSASigner  # same kid, a key Google never published

    @property
    def certs(self) -> dict[str, str]:
        return {GOOGLE_KID: self.public_pem}


def _signer(kid: str) -> tuple[google_crypt.RSASigner, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return google_crypt.RSASigner.from_string(private, kid), public.decode()


def build_keys() -> GoogleKeys:
    signer, public = _signer(GOOGLE_KID)
    other, _ = _signer(GOOGLE_KID)
    return GoogleKeys(public, signer, other)


def sign_token(
    keys: GoogleKeys,
    *,
    sub: str = "google-sub-1",
    email: str | None = "investor@example.test",
    email_verified: object = True,
    aud: str = GOOGLE_AUDIENCE,
    iss: str = "https://accounts.google.com",
    exp_in: int = 300,
    name: str | None = "Test Investor",
    picture: str | None = "https://lh3.example.test/a/photo",
    signer: google_crypt.RSASigner | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {"iss": iss, "aud": aud, "iat": now - 5, "exp": now + exp_in, "sub": sub}
    if email is not None:
        payload["email"] = email
    payload["email_verified"] = email_verified
    if name is not None:
        payload["name"] = name
    if picture is not None:
        payload["picture"] = picture
    payload.update(extra or {})
    return google_jwt.encode(signer or keys.signer, payload).decode()
