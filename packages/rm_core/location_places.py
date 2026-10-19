"""Stored mapping of catalogue places to BDL territories (RM-282).

LEGAL[third-party-data]: relates public Otodom place paths to public GUS administrative units (RM-282).
GDPR[personal-data]: none; territorial identifiers only (RM-282).
"""

from collections import Counter
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import MarketLocation, MarketLocationTerritory
from rm_core.location_mapping import MappingStatus, PlaceMapping, Relation, map_places
from rm_core.location_repo import PgLocationRepo


class PgPlaceMapping:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def map_catalogue(self, catalogue_version: int, reference_version: int) -> Counter[str]:
        """Recompute and store the mapping of every place of the catalogue; replaces the previous rows."""
        reference = await PgLocationRepo(self._sessions).get_reference(reference_version)
        if reference is None:
            raise LookupError(f"territorial reference {reference_version} is not stored")
        async with self._sessions() as s:
            places = [
                (r.location_id, r.otodom_path)
                for r in (
                    await s.execute(
                        select(MarketLocation.location_id, MarketLocation.otodom_path)
                        .where(MarketLocation.catalogue_version == catalogue_version)
                        .order_by(MarketLocation.position)
                    )
                ).all()
            ]
        mappings = map_places(places, reference)
        await self.save(catalogue_version, reference_version, mappings)
        return Counter(m.status.value for m in mappings)

    async def save(
        self, catalogue_version: int, reference_version: int, mappings: Sequence[PlaceMapping]
    ) -> None:
        async with self._sessions() as s, s.begin():
            await s.execute(
                delete(MarketLocationTerritory).where(
                    MarketLocationTerritory.catalogue_version == catalogue_version
                )
            )
            if mappings:
                await s.execute(
                    insert(MarketLocationTerritory),
                    [
                        {
                            "catalogue_version": catalogue_version,
                            "location_id": m.location_id,
                            "reference_version": reference_version,
                            "status": m.status.value,
                            "method": m.method,
                            "relation": m.relation.value if m.relation else None,
                            "gmina_id": m.gmina_id,
                            "powiat_id": m.powiat_id,
                            "wojewodztwo_id": m.wojewodztwo_id,
                            "candidates": list(m.candidates),
                        }
                        for m in mappings
                    ],
                )

    async def get(self, catalogue_version: int, location_id: str) -> PlaceMapping | None:
        async with self._sessions() as s:
            row = await s.get(MarketLocationTerritory, (catalogue_version, location_id))
        if row is None:
            return None
        return PlaceMapping(
            location_id=row.location_id,
            status=MappingStatus(row.status),
            method=row.method,
            relation=Relation(row.relation) if row.relation else None,
            gmina_id=row.gmina_id,
            powiat_id=row.powiat_id,
            wojewodztwo_id=row.wojewodztwo_id,
            candidates=tuple(row.candidates),
        )
