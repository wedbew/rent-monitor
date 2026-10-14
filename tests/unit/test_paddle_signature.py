"""Paddle webhook signature verification (PADDLE-INTEGRATION.md §5): `test_paddle_raw_signature`."""

import pytest
from rm_core.paddle_webhook import InvalidSignatureError, sign, verify

SECRET = "pdl_ntfset_test_secret"
BODY = b'{"event_id":"evt_1","event_type":"transaction.completed"}'
NOW = 1_800_000_000


def ok(header: str | None, body: bytes = BODY, secrets: list[str] | None = None, now: float = NOW) -> None:
    verify(header, body, [SECRET] if secrets is None else secrets, tolerance_s=5, now=now)


def test_a_correctly_signed_body_inside_the_window_is_accepted() -> None:
    ok(sign(SECRET, BODY, timestamp=NOW))
    ok(sign(SECRET, BODY, timestamp=NOW - 5))  # the edge of the tolerance, both sides
    ok(sign(SECRET, BODY, timestamp=NOW + 5))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b + b" ",  # one added byte
        lambda b: b.replace(b"evt_1", b"evt_2"),  # one changed byte
        lambda b: b"",  # emptied
    ],
)
def test_any_change_to_the_raw_bytes_is_rejected(mutate) -> None:
    header = sign(SECRET, BODY, timestamp=NOW)
    with pytest.raises(InvalidSignatureError):
        ok(header, mutate(BODY))


def test_the_wrong_or_missing_secret_is_rejected() -> None:
    header = sign("another-secret", BODY, timestamp=NOW)
    with pytest.raises(InvalidSignatureError):
        ok(header)
    with pytest.raises(InvalidSignatureError):
        ok(sign(SECRET, BODY, timestamp=NOW), secrets=[""])
    with pytest.raises(InvalidSignatureError):
        ok(sign(SECRET, BODY, timestamp=NOW), secrets=[])


@pytest.mark.parametrize("skew", [6, 60, -6, -3600])
def test_old_and_future_timestamps_are_rejected(skew: int) -> None:
    with pytest.raises(InvalidSignatureError):
        ok(sign(SECRET, BODY, timestamp=NOW - skew))


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "garbage",
        "ts=abc;h1=00",
        f"ts={NOW}",
        f"h1={'0' * 64}",
        f"ts={NOW};h1=",
        f"ts=-1;h1={'0' * 64}",
        "ts" * 600,
    ],
)
def test_malformed_headers_are_rejected(header: str | None) -> None:
    with pytest.raises(InvalidSignatureError):
        ok(header)


def test_a_rotation_accepts_either_secret_and_any_of_several_signatures() -> None:
    old, new = "old-secret", "new-secret"
    signed_with_old = sign(old, BODY, timestamp=NOW)
    ok(signed_with_old, secrets=[new, old])  # the previous secret still works while both are configured
    with pytest.raises(InvalidSignatureError):
        ok(signed_with_old, secrets=[new])
    digest_new = sign(new, BODY, timestamp=NOW).split("h1=")[1]
    ok(f"ts={NOW};h1={'0' * 64};h1={digest_new}", secrets=[new])  # Paddle sends several during rotation
    with pytest.raises(InvalidSignatureError):
        ok(f"ts={NOW}" + "".join(f";h1={'0' * 64}" for _ in range(9)))  # bounded


def test_the_timestamp_is_part_of_what_is_signed() -> None:
    digest = sign(SECRET, BODY, timestamp=NOW).split("h1=")[1]
    with pytest.raises(InvalidSignatureError):
        ok(f"ts={NOW + 1};h1={digest}")  # a replay with a refreshed timestamp does not verify
