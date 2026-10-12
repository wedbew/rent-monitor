"""Start a disposable Postgres 17 for tests, retrying a known Docker Desktop race.

On Docker Desktop (macOS) the Testcontainers reaper's published port is sometimes not visible yet when it is
read, and
container start fails with `ConnectionError: Port mapping for container ... is not available`. It is a
startup timing
issue, not a test or product failure, so a short bounded retry is the right answer; anything else still
fails at once.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from testcontainers.community.postgres import PostgresContainer

ATTEMPTS = 4
BACKOFF_S = 1.5


def start_with_retry[T](
    start: Callable[[], T], *, attempts: int = ATTEMPTS, sleep: Callable[[float], None] = time.sleep
) -> T:
    """Call `start()` until it works; only `ConnectionError` (the port race) is retried."""
    for attempt in range(1, attempts + 1):
        try:
            return start()
        except ConnectionError:
            if attempt == attempts:
                raise
            sleep(BACKOFF_S * attempt)
    raise AssertionError("unreachable")  # pragma: no cover


@contextmanager
def postgres_container() -> Iterator[PostgresContainer]:
    container = start_with_retry(lambda: PostgresContainer("postgres:17", driver="psycopg").start())
    try:
        yield container
    finally:
        container.stop()
