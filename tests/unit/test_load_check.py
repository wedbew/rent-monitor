"""The pure parts of the load check (scripts/load_check.py): percentiles, report, verdict, bounds."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SPEC = importlib.util.spec_from_file_location(
    "load_check", Path(__file__).resolve().parents[2] / "scripts" / "load_check.py"
)
assert SPEC is not None
assert SPEC.loader is not None
load_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(load_check)


def make_run(**overrides: object) -> Any:
    run = load_check.Run(audits=3, stop_connections=70)
    run.statuses = {"a": "succeeded", "b": "succeeded_degraded", "c": "succeeded"}
    run.finished_s = {"a": 4.0, "b": 8.0, "c": 12.0}
    run.connection_samples = [12, 30, 41]
    run.poll_latencies_s = [0.01, 0.02, 0.03, 0.2]
    for key, value in overrides.items():
        setattr(run, key, value)
    return run


def test_percentile_is_nearest_rank_and_empty_is_none() -> None:
    assert load_check.percentile([], 0.5) is None
    assert load_check.percentile([5.0], 0.95) == 5.0
    assert load_check.percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert load_check.percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_a_clean_run_passes_and_reports_its_numbers() -> None:
    report = load_check.summarise(make_run())
    assert report["ok"] is True
    assert report["pg_connections_peak"] == 41
    assert report["statuses"] == {"succeeded": 2, "succeeded_degraded": 1}
    assert report["time_to_finish_s"] == {"first": 4.0, "median": 8.0, "last": 12.0}
    assert report["poll_latency_s"]["max"] == 0.2
    assert report["evidence_class"].startswith("fake-provider-data")


@pytest.mark.parametrize(
    "overrides",
    [
        {"connection_samples": [12, 70]},  # reached the ceiling
        {"aborted": "deadline"},
        {"statuses": {"a": "succeeded", "b": "failed", "c": "succeeded"}},
        {"statuses": {"a": "succeeded", "b": "succeeded"}},  # one audit never reached a terminal state
        {"statuses": {"a": "succeeded", "b": "submit_402", "c": "succeeded"}},
    ],
)
def test_any_breach_or_unfinished_audit_fails_the_run(overrides: dict[str, object]) -> None:
    assert load_check.summarise(make_run(**overrides))["ok"] is False


def test_the_bounds_are_the_gates() -> None:
    assert load_check.MAX_AUDITS <= 25
    assert (
        load_check.DEFAULT_STOP_CONNECTIONS == 70
    )  # gate 5: pg_stat_activity stays under 70 of max_connections=100
    assert load_check.EMAIL_DOMAIN.endswith(".invalid")  # synthetic addresses can never be real mailboxes


def test_the_planted_listing_is_anonymised_and_has_no_photos() -> None:
    ad = load_check.hand_built_ad("Loadcheckabc")
    assert ad["adCategory"] == {"type": "SELL"}
    assert "images" not in ad  # no photos: the vision stage makes no OpenRouter call
    assert "seller" not in str(ad).lower()


def test_cleanup_names_exact_references_and_a_ref_fits_the_api_limit() -> None:
    refs = load_check.planted_refs("abcd1234")
    assert len(refs) == load_check.MAX_AUDITS
    assert refs[0] == "IDLCABCD123400"
    assert refs[-1] == "IDLCABCD123424"
    assert all(len(ref) <= 16 for ref in refs)  # the API's reference limit
