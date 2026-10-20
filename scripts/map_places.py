"""Map every catalogue place to its GUS BDL gmina, powiat and voivodeship and store the result (RM-282).

Usage: `uv run python scripts/map_places.py` (reads DATABASE_URL and the catalogue and reference
versions from the settings). Recomputable and idempotent: it replaces the stored mapping of the
catalogue version. Prints how many places are `mapped`, `ambiguous` and `unmatched`; the last two are
listed in the context API with their candidates.

LEGAL[third-party-data]: relates public Otodom place paths to public GUS administrative units (RM-282).
"""

import asyncio

from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.location_places import PgPlaceMapping
from rm_core.settings import get_settings


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings, pool_size=1, max_overflow=0)
    try:
        counts = await PgPlaceMapping(make_sessionmaker(engine)).map_catalogue(
            settings.otodom_market_catalogue_version, settings.location_reference_version
        )
    finally:
        await engine.dispose()
    print(dict(counts))


if __name__ == "__main__":
    asyncio.run(main())
