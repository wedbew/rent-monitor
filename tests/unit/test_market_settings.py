"""Rental corpus settings wiring: the switch, cron, window, overlap and budget govern the importer (RM-209).

LEGAL[scraping]: a disabled import must send no request to the Otodom search fake; no network is used here.
"""

from datetime import UTC, datetime, time, timedelta, timezone

import pytest
from market_corpus_fake import InMemoryCorpus
from otodom_search_fake import FakeCorpusSearch, tile
from rm_core.settings import Settings, get_settings
from rm_worker.importers.otodom_corpus import importer_from_settings, in_night_window
from rm_worker.tasks import batch

D0 = datetime(2026, 9, 1, 1, 10, tzinfo=UTC)


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_defaults_are_the_documented_policy() -> None:
    s = settings()
    assert s.otodom_market_import_enabled is True
    assert s.otodom_market_nightly_cron == "0 1 * * *"
    assert s.otodom_market_summary_cron == "30 5 * * *"
    assert s.night_window_end_time == time(5)
    assert s.otodom_market_overlap_minutes == 60
    assert s.otodom_market_request_budget == 3000
    assert s.otodom_market_catalogue_version == 1
    assert get_settings().otodom_market_nightly_cron == batch.CORPUS_DISPATCH_CRON


@pytest.mark.parametrize(
    ("hhmm", "closed"),
    [("01:00", False), ("04:59", False), ("05:00", True), ("11:59", True), ("12:00", False)],
)
def test_night_window_is_closed_from_its_end_until_noon_utc(hhmm: str, closed: bool) -> None:
    now = datetime.fromisoformat(f"2026-09-01T{hhmm}:00+00:00")
    assert in_night_window(now, time(5)) is closed


def test_night_window_compares_instants_not_the_wall_clock_of_the_caller() -> None:
    warsaw_summer = timezone(timedelta(hours=2))
    assert in_night_window(datetime(2026, 9, 1, 7, 30, tzinfo=warsaw_summer), time(5)) is True  # 05:30 UTC
    assert in_night_window(datetime(2026, 9, 1, 6, 30, tzinfo=warsaw_summer), time(5)) is False  # 04:30 UTC


def test_window_end_must_be_hh_mm_before_noon() -> None:
    assert settings(otodom_market_night_window_end_utc="03:30").night_window_end_time == time(3, 30)
    with pytest.raises(ValueError, match="before 12:00"):
        settings(otodom_market_night_window_end_utc="12:00")
    with pytest.raises(ValueError, match="HH:MM"):
        settings(otodom_market_night_window_end_utc="5am")


def test_cron_settings_need_five_fields() -> None:
    with pytest.raises(ValueError, match="five"):
        settings(otodom_market_summary_cron="30 5 *")
    with pytest.raises(ValueError, match="five"):
        settings(otodom_market_nightly_cron="0 1 * *")


def test_factory_applies_overlap_budget_and_window_from_settings() -> None:
    s = settings(
        otodom_market_overlap_minutes=15,
        otodom_market_request_budget=7,
        otodom_market_night_window_end_utc="03:15",
    )
    imp = importer_from_settings(InMemoryCorpus(), FakeCorpusSearch(), s)
    assert imp.overlap == timedelta(minutes=15)
    assert imp.page_budget == 7
    assert imp.night_window_end == time(3, 15)
    assert imp.normal_window == timedelta(hours=24) + timedelta(minutes=15) + timedelta(hours=1)


async def test_disabled_switch_sends_no_request_and_defers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    off = settings(otodom_market_import_enabled=False)
    fake = FakeCorpusSearch([tile(1, D0 - timedelta(days=1))])
    assert await batch.sync_location_now(off, "loc-a", source=fake, now=D0) == []
    assert fake.calls == []

    deferred: list[dict[str, object]] = []

    async def record(**kwargs: object) -> None:
        deferred.append(kwargs)

    monkeypatch.setattr(batch.sync_corpus_location, "defer_async", record)
    assert await batch.dispatch_nightly_now(off, now=D0) == []
    assert deferred == []
