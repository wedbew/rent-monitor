"""Typed corpus search options and the client's refusal to send an unverified date filter (RM-392).

LEGAL[scraping]: asserts the request shape of an Otodom search against a fake transport; no network.
"""

from datetime import UTC, datetime, timedelta

import pytest
from rm_core.deadline import Deadline
from rm_worker.app import app
from rm_worker.clients.otodom import FilterContractUnverified, OtodomClient, SearchOptions
from rm_worker.tasks import batch
from test_rental_search import LOC, Breaker, Slots, Transport, offer, page

T = datetime(2026, 9, 1, 1, 0, tzinfo=UTC)


def client(*, verified: bool) -> tuple[OtodomClient, Transport]:
    transport = Transport(page([offer()]))
    return OtodomClient(
        transport=transport, slots=Slots(), breaker=Breaker(), filters_verified=verified
    ), transport


def test_options_require_aware_ordered_bounds() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SearchOptions(datetime(2026, 9, 1), T)  # noqa: DTZ001
    with pytest.raises(ValueError, match="precede"):
        SearchOptions(T, T)
    assert SearchOptions().query() == {}
    assert SearchOptions(T - timedelta(days=1), T).query() == {
        "createdAtFrom": "2026-08-31T01:00:00Z",
        "createdAtTo": "2026-09-01T01:00:00Z",
    }


async def test_date_filter_is_refused_until_verified_and_sends_nothing() -> None:
    c, transport = client(verified=False)
    with pytest.raises(FilterContractUnverified):
        await c.fetch_corpus_search(LOC, 1, options=SearchOptions(None, T), deadline=Deadline.after(30))
    assert transport.urls == []


async def test_unfiltered_search_needs_no_verification_and_filtered_goes_out_when_verified() -> None:
    c, transport = client(verified=False)
    await c.fetch_corpus_search(LOC, 2, options=SearchOptions(), deadline=Deadline.after(30))
    assert transport.urls == [f"https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/{LOC}?page=2"]
    v, vt = client(verified=True)
    await v.fetch_corpus_search(LOC, 1, options=SearchOptions(None, T), deadline=Deadline.after(30))
    assert vt.urls == [
        f"https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/{LOC}?page=1&createdAtTo=2026-09-01T01%3A00%3A00Z"
    ]


@pytest.mark.parametrize(("location", "page_no"), [("../x", 1), ("a?b=1", 1), (LOC, 0), (LOC, 51)])
async def test_corpus_search_validates_location_and_page_before_any_request(
    location: str, page_no: int
) -> None:
    c, transport = client(verified=True)
    with pytest.raises(ValueError, match="invalid"):
        await c.fetch_corpus_search(location, page_no, options=SearchOptions(), deadline=Deadline.after(30))
    assert transport.urls == []


def test_batch_tasks_are_registered_on_the_expected_queues() -> None:
    names = {t.name: t.queue for t in app.tasks.values()}
    assert names[batch.CORPUS_LOCATION_TASK] == "batch"
    assert names[batch.CORPUS_DISPATCH_TASK] == "ops"
