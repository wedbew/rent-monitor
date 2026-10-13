"""Password policy and hashing for email/password sign-in (ADR 0013, docs/PASSWORD-AUTH-SPEC.md).

GDPR[personal-data]: handles a plaintext password only in memory, for the length of one request; it is never
logged, stored or returned. Storage is the Argon2id PHC string.

Hashing is deliberately expensive, so it runs off the event loop and under a small concurrency cap: a burst of
sign-ups queues instead of exhausting memory next to the audit worker (blueprint §6).
"""

import asyncio
import unicodedata

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from rm_contracts.auth import PASSWORD_MAX_BYTES, PASSWORD_MAX_CHARS, PASSWORD_MIN_CHARS
from rm_core.settings import Settings

# Reasons reported with 422 WEAK_PASSWORD (a closed vocabulary).
TOO_SHORT, TOO_LONG, COMMON, CONTAINS_EMAIL = "too_short", "too_long", "common", "contains_email"
MIN_LOCAL_PART = 4  # a shorter local part would reject innocent passwords

# Passwords of at least the minimum length that appear in every public breach corpus. This is a floor, not the
# full list: the source and size of the production blocklist are an open item (L-019, #203).
_COMMON_TEXT = """
1234567890 0123456789 12345678910 123456789012 1q2w3e4r5t 1qaz2wsx3edc 1qazxsw2 qwertyuiop
qwertyuiop1 asdfghjkl1 asdfghjklz zxcvbnm123 qwerty1234 qwerty12345 qwertyuiop123 qwerty123456
password12 password123 password1234 password12345 password123456 passw0rd123 p@ssw0rd123 p@ssword12
pa55word12 letmein1234 letmein12345 welcome123 welcome1234 welcome12345 iloveyou12 iloveyou123
iloveyou1234 admin12345 admin123456 administrator trustno1234 changeme123 changeme1234 abc1234567
abcd123456 abcdefghij abcdefg123 monkey1234 dragon1234 master1234 sunshine12 princess12 football12
baseball12 superman12 batman1234 starwars12 shadow1234 michael123 jennifer12 charlie123 computer12
internet12 whatever12 freedom123 mustang123 hello12345 hello123456 haslo12345 haslo123456 haslo1234
haslo12345 haslohaslo zaq12wsx34 zaq1zaq1zaq1 polska12345 polska1234 kocham1234 kocham12345
mojehaslo1 mojehaslo12 mojehaslo123 qazwsxedc1 qazwsxedcrfv 1111111111 0000000000 1212121212
1231231231 9876543210 987654321012 aaaaaaaaaa
"""
_COMMON = frozenset(_COMMON_TEXT.split())


def normalise(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def check_policy(password: str, email: str) -> str | None:
    """None if acceptable, else one reason from the closed vocabulary. NFKC first, no composition rules."""
    pw = normalise(password)
    if len(pw) < PASSWORD_MIN_CHARS:
        return TOO_SHORT
    if len(pw) > PASSWORD_MAX_CHARS or len(pw.encode()) > PASSWORD_MAX_BYTES:
        return TOO_LONG
    folded = pw.casefold()
    if folded in _COMMON or len(set(folded)) == 1:
        return COMMON
    local = email.split("@", 1)[0].casefold()
    if len(local) >= MIN_LOCAL_PART and local in folded:
        return CONTAINS_EMAIL
    return None


class PasswordHasher:
    """One per API process (built from settings). `hash` and `verify` never block the event loop."""

    def __init__(self, settings: Settings) -> None:
        self._hash = PasswordHash(
            (
                Argon2Hasher(
                    time_cost=settings.password_argon2_time_cost,
                    memory_cost=settings.password_argon2_memory_kib,
                    parallelism=settings.password_argon2_parallelism,
                ),
            )
        )
        self._slots = asyncio.Semaphore(settings.password_hash_concurrency)
        self._dummy = self._hash.hash("dummy-password-for-timing")

    async def hash(self, password: str) -> str:
        async with self._slots:
            return await asyncio.to_thread(self._hash.hash, normalise(password))

    async def verify(self, password: str, stored: str) -> tuple[bool, str | None]:
        """(matches, replacement hash if the parameters changed and it should be re-stored)."""
        async with self._slots:
            return await asyncio.to_thread(self._hash.verify_and_update, normalise(password), stored)

    async def verify_dummy(self, password: str) -> None:
        """Same work as a real check, for an address that has no credential (no timing oracle)."""
        async with self._slots:
            await asyncio.to_thread(self._hash.verify, normalise(password), self._dummy)
