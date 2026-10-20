"""Coverage manifest on real Postgres: every state, counted independently of the implementation (RM-411).

Setup uses the production importer with the verified-contract fake, so the stored rows are real; the expected
numbers below are written by hand from what each scenario must produce.

LEGAL[third-party-data]: aggregates about hand-built asking-rent offers (RM-411).
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from otodom_search_fake import FakeCorpusSearch, tile
from rm_contracts.market import LocationCatalogue, LocationEntry
from rm_core.market_corpus import PgCorpus
from rm_core.market_manifest import STATES, coverage_manifest
from rm_worker.importers.otodom_corpus import CorpusImporter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_offer, app.market_import_run, app.market_import_checkpoint,"
    " app.market_location, app.market_catalogue"
)
D0 = datetime(2026, 9, 1, 1, 10, tzinfo=UTC)
LOCS = {
    name: LocationEntry(location_id=f"loc-{name}", name=name.title(), otodom_path=f"testowe/{name}")
    for name in ("full", "empty", "blocked", "broken", "partial", "never")
}
OFF = LocationEntry(location_id="loc-off", name="Off", otodom_path="testowe/off", launch_enabled=False)
CATALOGUE = LocationCatalogue.build(1, "hand-built", [*LOCS.values(), OFF])


@pytest_asyncio.fixture(loop_scope="session")
async def corpus(engine: AsyncEngine) -> PgCorpus:  # type: ignore[misc]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    repo = PgCorpus(async_sessionmaker(engine, expire_on_commit=False))
    await repo.ensure_catalogue(CATALOGUE)
    yield repo  # type: ignore[misc]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def run(corpus: PgCorpus, entry: LocationEntry, source: FakeCorpusSearch, **kw: object) -> None:
    source.now = D0
    await CorpusImporter(corpus, source, page_cap=3, **kw).sync_location(entry, now=D0)  # type: ignore[arg-type]


async def test_every_state_is_reported_and_only_proven_locations_count_as_covered(
    corpus: PgCorpus, engine: AsyncEngine
) -> None:
    three = [tile(100 + i, D0 - timedelta(days=1, hours=i)) for i in range(3)]
    await run(corpus, LOCS["full"], FakeCorpusSearch(three, page_size=100))
    await run(corpus, LOCS["empty"], FakeCorpusSearch([], page_size=100))
    await run(corpus, LOCS["blocked"], FakeCorpusSearch(three, fail_on_call=1, retryable=False))
    await run(corpus, LOCS["broken"], FakeCorpusSearch(raw_override={"items": "x", "pagination": {}}))
    tied = [tile(200 + i, D0 - timedelta(days=2)) for i in range(30)]  # over the cap on one instant
    await run(corpus, LOCS["partial"], FakeCorpusSearch(tied))

    manifest = await coverage_manifest(async_sessionmaker(engine, expire_on_commit=False), 1, now=D0)

    assert manifest["catalogue"] == {
        "version": 1,
        "source_ref": "hand-built",
        "checksum": CATALOGUE.checksum,
        "locations": 7,
        "enabled": 6,
    }
    assert manifest["states"] == dict.fromkeys(STATES, 0) | {
        "complete_nonempty": 1,
        "complete_empty": 1,
        "blocked": 1,
        "failed": 1,
        "partial": 1,
        "pending": 1,
        "disabled": 1,
    }
    assert manifest["covered_locations"] == 2  # a blocked, broken, partial or pending place is not covered
    by_id = {row["location_id"]: row for row in manifest["locations"]}
    assert by_id["loc-full"]["offers_stored"] == 3
    assert by_id["loc-empty"]["offers_stored"] == 0
    assert by_id["loc-empty"]["bootstrap_completed_at"] is not None  # proven empty, not merely unvisited
    assert by_id["loc-never"]["last_run"] is None
    assert by_id["loc-partial"]["last_run"]["truncated"] is True
    assert by_id["loc-blocked"]["last_run"]["error_category"] == "upstream_blocked"
    assert manifest["offers_stored"] >= 3 + 12  # the partial location keeps what it read, unpublished
    published = [r for r in manifest["runs"] if r["state"] == "published"]
    assert sum(r["runs"] for r in published) == 2
    assert all(r["pages_fetched"] == r["pages_expected"] for r in published)
    assert manifest["daily_summaries"]["rows"] == 0  # nothing was published to the summary table
