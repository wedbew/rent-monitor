"""The corpus search wire contract verified against the live site on 2026-10-20 (RM-411, L-050).

LEGAL[scraping]: asserts the request shape of an Otodom search against a fake transport; no network.
Live probes (Bydgoszcz flat rentals, one request each, no content kept): `daysSinceCreated=N` limits the
list to the last N x 24 hours for any integer N, and `by=LATEST&direction=ASC|DESC` sorts by creation time.
"""

import pytest
from rm_core.deadline import Deadline
from rm_worker.app import app
from rm_worker.clients.otodom import OtodomClient, SearchOptions
from rm_worker.tasks import batch
from test_rental_search import LOC, Breaker, Slots, Transport, offer, page

BASE = f"https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/{LOC}"


def client() -> tuple[OtodomClient, Transport]:
    transport = Transport(page([offer()]))
    return OtodomClient(transport=transport, slots=Slots(), breaker=Breaker()), transport


@pytest.mark.parametrize("days", [0, -1, 3651])
def test_days_since_created_is_bounded(days: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        SearchOptions(days)


@pytest.mark.parametrize("size", [0, 35, 100])
def test_page_size_is_one_the_site_honours(size: int) -> None:
    """Live: limit=100 silently fell back to 36 pages, which would break page arithmetic."""
    with pytest.raises(ValueError, match="page_size"):
        SearchOptions(page_size=size)


def test_options_always_carry_an_explicit_creation_order() -> None:
    assert SearchOptions().query() == {"limit": "72", "by": "LATEST", "direction": "DESC"}
    assert SearchOptions(7, "oldest").query() == {
        "limit": "72",
        "by": "LATEST",
        "direction": "ASC",
        "daysSinceCreated": "7",
    }


async def test_the_request_uses_the_verified_parameters_and_no_invented_ones() -> None:
    c, transport = client()
    await c.fetch_corpus_search(LOC, 2, options=SearchOptions(), deadline=Deadline.after(30))
    await c.fetch_corpus_search(LOC, 1, options=SearchOptions(45, "oldest"), deadline=Deadline.after(30))
    assert transport.urls == [
        f"{BASE}?page=2&limit=72&by=LATEST&direction=DESC",
        f"{BASE}?page=1&limit=72&by=LATEST&direction=ASC&daysSinceCreated=45",
    ]
    assert not any("createdAt" in u for u in transport.urls)  # the unverified bound names are gone


@pytest.mark.parametrize(("location", "page_no"), [("../x", 1), ("a?b=1", 1), (LOC, 0), (LOC, 401)])
async def test_corpus_search_validates_location_and_page_before_any_request(
    location: str, page_no: int
) -> None:
    c, transport = client()
    with pytest.raises(ValueError, match="invalid"):
        await c.fetch_corpus_search(location, page_no, options=SearchOptions(), deadline=Deadline.after(30))
    assert transport.urls == []


def test_batch_tasks_are_registered_on_the_expected_queues() -> None:
    names = {t.name: t.queue for t in app.tasks.values()}
    assert names[batch.CORPUS_LOCATION_TASK] == "batch"
    assert names[batch.CORPUS_DISPATCH_TASK] == "ops"
