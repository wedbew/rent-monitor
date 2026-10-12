"""The principal cache bound, token hashing and cookie attributes (blueprint §2 Auth decision, rules 1-4)."""

from fastapi import Response
from rm_api.auth.sessions import (
    PRINCIPAL_CACHE_TTL_S,
    PrincipalCache,
    clear_session_cookie,
    hash_token,
    new_token,
    set_session_cookie,
)
from rm_core.principal import Principal
from rm_core.settings import Settings


def principal(user: str = "u1", tag: str = "t1") -> Principal:
    return Principal(
        user_id=user,
        email=f"{user}@example.test",
        role="user",
        email_verified=True,
        session_id=1,
        token_hash=tag,
    )


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_a_cached_principal_expires_after_the_stated_ttl() -> None:
    clock = Clock()
    cache = PrincipalCache(clock=clock)
    cache.put(principal())
    clock.now += PRINCIPAL_CACHE_TTL_S - 0.1
    assert cache.get("t1") is not None
    clock.now += 0.2
    assert cache.get("t1") is None


def test_the_ttl_is_the_documented_thirty_seconds() -> None:
    assert PRINCIPAL_CACHE_TTL_S == 30.0


def test_notify_evicts_every_session_of_a_user_but_nobody_else() -> None:
    cache = PrincipalCache()
    for token, user in (("a", "u1"), ("b", "u1"), ("c", "u2")):
        cache.put(principal(user, token))
    cache.on_notify("user:u1")
    assert cache.get("a") is None
    assert cache.get("b") is None
    assert cache.get("c") is not None


def test_notify_can_evict_one_token() -> None:
    cache = PrincipalCache()
    cache.put(principal("u1", "a"))
    cache.put(principal("u1", "b"))
    cache.on_notify("token:a")
    assert cache.get("a") is None
    assert cache.get("b") is not None


def test_unknown_or_malformed_notify_payloads_are_ignored() -> None:
    cache = PrincipalCache()
    cache.put(principal())
    for payload in ("", "garbage", "user", "other:u1", ":::"):
        cache.on_notify(payload)
    assert cache.get("t1") is not None


def test_the_cache_is_bounded() -> None:
    cache = PrincipalCache(maxsize=3)
    for i in range(10):
        cache.put(principal(f"u{i}", f"t{i}"))
    assert len(cache) == 3
    assert cache.get("t9") is not None


def test_clear_drops_everything() -> None:
    cache = PrincipalCache()
    cache.put(principal())
    cache.clear()
    assert len(cache) == 0


def test_tokens_are_long_random_and_hashed_with_sha256() -> None:
    tokens = {new_token() for _ in range(200)}
    assert len(tokens) == 200
    assert all(len(t) >= 43 for t in tokens)  # 32 random bytes, urlsafe base64
    digest = hash_token("abc")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert len(digest) == 64


def test_the_production_cookie_uses_the_host_prefix_and_strict_attributes() -> None:
    settings = Settings(app_env="production")
    assert settings.cookie_name == "__Host-rm_session"
    response = Response()
    set_session_cookie(response, "tok", settings)
    header = response.headers["set-cookie"].lower()
    assert header.startswith("__host-rm_session=tok")
    for attribute in ("httponly", "secure", "samesite=lax", "path=/"):
        assert attribute in header
    assert "domain" not in header  # required by the __Host- prefix
    assert "max-age=2592000" in header


def test_development_cookies_work_over_plain_http() -> None:
    settings = Settings(app_env="development")
    assert settings.cookie_name == "rm_session"
    response = Response()
    set_session_cookie(response, "tok", settings)
    assert "secure" not in response.headers["set-cookie"].lower()


def test_clearing_the_cookie_expires_it() -> None:
    response = Response()
    clear_session_cookie(response, Settings(app_env="production"))
    header = response.headers["set-cookie"].lower()
    assert "__host-rm_session=" in header
    assert "max-age=0" in header
