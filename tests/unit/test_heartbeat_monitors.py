"""Heartbeat pings and the monitor thresholds (docs/OBSERVABILITY-SPEC.md sections 4 and 5)."""

from pathlib import Path

import httpx
import pytest
from rm_worker.clients.heartbeat import Heartbeat
from rm_worker.monitors import (
    CONNECTIONS_WARN,
    MEMORY_PEAK_WARN,
    QUEUE_AGE_WARN_S,
    Reading,
    evaluate,
    memory_peak_ratio,
)

SECRET_URL = "https://uptime.example.test/api/v1/heartbeat/SECRETTOKEN123"


def heartbeat(handler: object, url: str = SECRET_URL) -> tuple[Heartbeat, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator, no-any-return]

    return Heartbeat(httpx.AsyncClient(transport=httpx.MockTransport(wrapped)), url, "test"), seen


async def test_success_pings_the_url_and_failure_pings_slash_fail() -> None:
    hb, seen = heartbeat(lambda r: httpx.Response(200))
    assert await hb.ping(ok=True) is True
    assert await hb.ping(ok=False) is True
    assert [str(r.url) for r in seen] == [SECRET_URL, SECRET_URL + "/fail"]


async def test_a_trailing_slash_does_not_double_up() -> None:
    hb, seen = heartbeat(lambda r: httpx.Response(200), SECRET_URL + "/")
    await hb.ping(ok=False)
    assert str(seen[0].url) == SECRET_URL + "/fail"


async def test_an_empty_url_means_monitoring_is_off() -> None:
    hb, seen = heartbeat(lambda r: httpx.Response(200), "")
    assert await hb.ping() is False
    assert seen == []


@pytest.mark.parametrize("status", [404, 500, 503])
async def test_a_bad_answer_is_reported_but_never_raises(status: int) -> None:
    hb, _ = heartbeat(lambda r: httpx.Response(status))
    assert await hb.ping() is False


async def test_a_network_error_never_raises_and_never_logs_the_url(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    hb, _ = heartbeat(boom)
    assert await hb.ping() is False
    captured = capsys.readouterr()
    assert "SECRETTOKEN123" not in captured.out + captured.err


def reading(**kw: object) -> Reading:
    base: dict[str, object] = {"queue_age_s": {}, "connections": 5, "memory_peak_ratio": None}
    return Reading(**{**base, **kw})  # type: ignore[arg-type]


def test_a_healthy_reading_raises_no_alert() -> None:
    assert evaluate(reading(queue_age_s={"audit": 3.0}, connections=20, memory_peak_ratio=0.3)) == []


def test_queue_lag_is_reported_per_queue_beyond_ten_minutes() -> None:
    alerts = evaluate(
        reading(queue_age_s={"audit": QUEUE_AGE_WARN_S + 1, "ops": QUEUE_AGE_WARN_S, "batch": 900})
    )
    assert [a.key for a in alerts] == ["queue_lag:audit", "queue_lag:batch"]  # exactly at the limit is fine


def test_connections_above_the_budget_alert_but_at_the_budget_do_not() -> None:
    assert evaluate(reading(connections=CONNECTIONS_WARN)) == []
    assert [a.key for a in evaluate(reading(connections=CONNECTIONS_WARN + 1))] == ["connections"]


def test_memory_above_sixty_percent_alerts() -> None:
    assert evaluate(reading(memory_peak_ratio=MEMORY_PEAK_WARN)) == []
    alerts = evaluate(reading(memory_peak_ratio=0.75))
    assert [a.key for a in alerts] == ["memory"]
    assert "75%" in alerts[0].message


def write_cgroup(root: Path, peak: str, limit: str) -> None:
    (root / "memory.peak").write_text(peak)
    (root / "memory.max").write_text(limit)


def test_cgroup_ratio_is_peak_over_limit(tmp_path: Path) -> None:
    write_cgroup(tmp_path, "600\n", "1000\n")
    assert memory_peak_ratio(tmp_path) == 0.6


@pytest.mark.parametrize(("peak", "limit"), [("5", "max"), ("x", "100"), ("5", "y"), ("5", "0")])
def test_an_unlimited_or_unreadable_cgroup_gives_none(tmp_path: Path, peak: str, limit: str) -> None:
    write_cgroup(tmp_path, peak, limit)
    assert memory_peak_ratio(tmp_path) is None


def test_a_missing_cgroup_gives_none(tmp_path: Path) -> None:
    assert memory_peak_ratio(tmp_path / "nope") is None
