"""The Postgres start helper retries the Docker Desktop port race, and only that."""

from collections.abc import Callable

import pytest
from pg_container import ATTEMPTS, start_with_retry


def flaky(failures: int) -> tuple[list[int], Callable[[], str]]:
    calls: list[int] = []

    def start() -> str:
        calls.append(1)
        if len(calls) <= failures:
            raise ConnectionError("Port mapping for container abc and port 8080 is not available")
        return "started"

    return calls, start


def test_a_transient_port_error_is_retried_until_it_works() -> None:
    calls, start = flaky(2)
    waits: list[float] = []
    assert start_with_retry(start, sleep=waits.append) == "started"
    assert len(calls) == 3
    assert waits == [1.5, 3.0]  # a growing, bounded back-off


def test_the_half_created_reaper_is_cleaned_up_before_each_retry() -> None:
    calls, start = flaky(2)
    events: list[str] = []
    start_with_retry(
        start,
        sleep=lambda _s: events.append("sleep"),
        before_retry=lambda: events.append("cleanup"),
    )
    assert events == ["cleanup", "sleep", "cleanup", "sleep"]
    assert len(calls) == 3


def test_it_gives_up_after_the_last_attempt_and_raises_the_original_error() -> None:
    calls, start = flaky(99)
    with pytest.raises(ConnectionError, match="Port mapping"):
        start_with_retry(start, sleep=lambda _s: None)
    assert len(calls) == ATTEMPTS


def test_other_errors_are_not_retried() -> None:
    calls: list[int] = []

    def start() -> str:
        calls.append(1)
        raise RuntimeError("image not found")

    with pytest.raises(RuntimeError):
        start_with_retry(start, sleep=lambda _s: None)
    assert calls == [1]
