"""Place mapping stored on real Postgres (RM-282): recompute, replace, read back, constraints.

LEGAL[third-party-data]: relates hand-built place paths to hand-built territories (RM-282).
"""

import pytest
import pytest_asyncio
from mapping_fixtures import REF
from rm_contracts.market import LocationCatalogue, LocationEntry
from rm_core.location_mapping import MappingStatus
from rm_core.location_places import PgPlaceMapping
from rm_core.location_repo import PgLocationRepo
from rm_core.market_corpus import PgCorpus
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_location_territory, app.market_location, app.market_catalogue,"
    " app.location_territory, app.location_reference"
)
ENTRIES = [
    LocationEntry(location_id="a", name="A", otodom_path="malopolskie/bochenski/nowy-wisnicz"),
    LocationEntry(location_id="b", name="B", otodom_path="malopolskie/bochenski/bochnia"),
    LocationEntry(location_id="c", name="C", otodom_path="malopolskie/krakow/krakow/krakow"),
    LocationEntry(location_id="d", name="D", otodom_path="mazowieckie/bochenski/nowy-wisnicz"),
]


@pytest_asyncio.fixture(loop_scope="session")
async def stores(engine: AsyncEngine):  # type: ignore[no-untyped-def]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    await PgLocationRepo(sessions).ensure_reference(1, "hand-built", REF)
    await PgCorpus(sessions).ensure_catalogue(LocationCatalogue.build(1, "hand-built", ENTRIES))
    yield PgPlaceMapping(sessions), engine
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES} CASCADE"))


async def test_every_place_gets_exactly_one_honest_row_and_a_rerun_replaces_it(stores) -> None:  # type: ignore[no-untyped-def]
    mapping, _ = stores
    counts = await mapping.map_catalogue(1, 1)
    assert dict(counts) == {"mapped": 2, "ambiguous": 1, "unmatched": 1}
    a, b, c, d = [await mapping.get(1, x) for x in "abcd"]
    assert (a.status, a.gmina_id) == (MappingStatus.mapped, "G3")
    assert (b.status, b.gmina_id, set(b.candidates)) == (MappingStatus.ambiguous, None, {"G1", "G2"})
    assert (c.status, c.gmina_id, c.powiat_id) == (MappingStatus.mapped, "G4", "P1261")
    assert (d.status, d.method) == (MappingStatus.unmatched, "powiat_unknown")
    again = await mapping.map_catalogue(1, 1)
    assert dict(again) == dict(counts)  # replace, not append
    assert await mapping.get(1, "zzz") is None


async def test_a_mapped_row_without_a_gmina_is_refused_by_the_database(stores) -> None:  # type: ignore[no-untyped-def]
    _, engine = stores
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO app.market_location_territory"
                    " (catalogue_version, location_id, reference_version, status, method)"
                    " VALUES (1, 'a', 1, 'mapped', 'x')"
                )
            )
