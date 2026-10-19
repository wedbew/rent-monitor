"""Acquire and seed the Otodom location catalogue (RM-411). Two steps, both repeatable.

  uv run python scripts/seed_catalogue.py discover --out docs/market/otodom-catalogue-v1.json [--cache FILE]
      Fetches Otodom's location sitemap, applies the settlement rule (`otodom_catalogue.py`), reads page 1 of
      every settlement's flat-rent search for its display name and offer count (1 request/second, resumable
      through --cache) and writes the provenance artifact: source date, sitemap SHA-256, rule, reconciliation
      against the owner's 727, the catalogue checksum and one probe record per location.
  uv run python scripts/seed_catalogue.py apply --file docs/market/otodom-catalogue-v1.json [--version 1]
      Verifies the artifact's checksum and seeds `market_catalogue` / `market_location` (idempotent: the same
      content is a no-op, different content for an existing version is refused). Needs DATABASE_URL.

Nothing from the POC is read. Only location paths, names and offer counts are stored; no listing data.

LEGAL[scraping]: one sitemap request and one search-page request per location, browser TLS impersonation,
1 req/s, stops at the first refusal (RM-411).
LEGAL[third-party-data]: location paths, names and counts only (RM-411).
"""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rm_contracts.market import LocationCatalogue, LocationEntry
from rm_core.deadline import Deadline
from rm_worker.clients.otodom import OtodomClient, SearchOptions, UpstreamBlocked
from rm_worker.clients.otodom_transport import CurlCffiTransport
from rm_worker.importers.otodom_catalogue import (
    ARTIFACT_SCHEMA,
    SITEMAP_URL,
    ArtifactError,
    build_catalogue,
    build_entries,
    catalogue_from_artifact,
    display_name,
    flat_paths,
    parse_sitemap,
    reconcile,
    settlement_units,
)

SCHEMA = ARTIFACT_SCHEMA
SITEMAP_MAX_BYTES = 32 * 1024 * 1024
RULE = (
    "gmina-level place = every depth-3 path (voivodeship/county/gmina) plus every depth-4 path whose depth-3 "
    "gmina is not listed, among Otodom's flat landing pages for rent or sale; nested places excluded"
)


class OneSecondSlots:
    """In-memory 1 req/s for a one-off run (the worker uses the shared Postgres slot)."""

    def __init__(self) -> None:
        self._next = 0.0

    async def reserve(self, host: str) -> float:
        loop = asyncio.get_running_loop()
        wait = max(0.0, self._next - loop.time())
        self._next = loop.time() + wait + 1.0
        return wait

    async def audit_queue_busy(self) -> bool:
        return False


class StopAtFirstRefusal:
    def __init__(self) -> None:
        self.tripped: str | None = None

    async def is_open(self, host: str) -> int | None:
        return 3600 if self.tripped else None

    async def trip(self, host: str, reason: str) -> None:
        self.tripped = reason


async def fetch_sitemap() -> tuple[bytes, dict[str, Any]]:
    raw = await CurlCffiTransport(max_bytes=SITEMAP_MAX_BYTES).get(
        SITEMAP_URL, headers={"accept": "application/xml,*/*", "accept-language": "pl-PL"}, total_s=120
    )
    if raw.status != 200:
        raise SystemExit(f"sitemap answered HTTP {raw.status}; nothing written")
    return raw.body, {
        "url": SITEMAP_URL,
        "sha256": hashlib.sha256(raw.body).hexdigest(),
        "bytes": len(raw.body),
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


async def probe(
    client: OtodomClient, entries: list[LocationEntry], cache: dict[str, Any], cache_path: Path | None
):
    names: dict[str, str] = {}
    done = 0
    for entry in entries:
        path = entry.otodom_path
        if path in cache and cache[path].get("status") == "ok":
            if cache[path].get("name"):
                names[path] = cache[path]["name"]
            continue
        try:
            ads = await client.fetch_corpus_search(
                path, 1, options=SearchOptions(), deadline=Deadline.after(60), priority="batch"
            )
        except UpstreamBlocked as exc:
            print(f"stopped at {path}: {exc}", file=sys.stderr)
            break
        raw_pagination = ads.get("pagination")
        pagination: dict[str, Any] = raw_pagination if isinstance(raw_pagination, dict) else {}
        name = display_name(ads, path)
        cache[path] = {
            "status": "ok",
            "name": name,
            "total_items": pagination.get("totalItems"),
            "total_pages": pagination.get("totalPages"),
            "probed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        if name:
            names[path] = name
        done += 1
        if cache_path and done % 20 == 0:
            await asyncio.to_thread(cache_path.write_text, json.dumps(cache))
            print(f"probed {len(cache)}/{len(entries)}", file=sys.stderr)
    if cache_path:
        await asyncio.to_thread(cache_path.write_text, json.dumps(cache))
    return names


async def discover(out: Path, cache_path: Path | None) -> None:
    xml, sitemap = await fetch_sitemap()
    by_tx = flat_paths(parse_sitemap(xml))
    units = settlement_units(by_tx["wynajem"] | by_tx["sprzedaz"])
    rec = reconcile(by_tx, units)
    cache: dict[str, Any] = {}
    if cache_path and await asyncio.to_thread(cache_path.exists):
        cache = json.loads(await asyncio.to_thread(cache_path.read_text))
    client = OtodomClient(transport=CurlCffiTransport(), slots=OneSecondSlots(), breaker=StopAtFirstRefusal())
    names = await probe(client, build_entries(units), cache, cache_path)
    entries = build_entries(units, names)
    unprobed = [e.otodom_path for e in entries if cache.get(e.otodom_path, {}).get("status") != "ok"]
    if unprobed:
        raise SystemExit(
            f"{len(unprobed)} locations were not probed (rerun with the same --cache); nothing written"
        )
    catalogue = build_catalogue(1, f"otodom-sitemap:{sitemap['sha256'][:16]}", entries)
    artifact = {
        "schema": SCHEMA,
        "version": catalogue.version,
        "source_ref": catalogue.source_ref,
        "checksum": catalogue.checksum,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sitemap": sitemap,
        "rule": RULE,
        "reconciliation": rec.as_dict(),
        "locations": [
            {
                "location_id": e.location_id,
                "name": e.name,
                "otodom_path": e.otodom_path,
                "probe": {k: v for k, v in cache[e.otodom_path].items() if k != "name"},
            }
            for e in catalogue.locations
        ],
    }
    await asyncio.to_thread(out.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(out.write_text, json.dumps(artifact, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {out}: {len(entries)} settlements, checksum {catalogue.checksum[:12]}")


def load_catalogue(path: Path, version: int | None) -> LocationCatalogue:
    try:
        return catalogue_from_artifact(json.loads(path.read_text()), version)
    except ArtifactError as exc:
        raise SystemExit(f"{exc}; refusing to seed") from exc


async def apply(path: Path, version: int | None) -> None:
    from rm_core.db.session import make_engine, make_sessionmaker  # noqa: PLC0415
    from rm_core.market_corpus import PgCorpus  # noqa: PLC0415
    from rm_core.settings import get_settings  # noqa: PLC0415

    catalogue = load_catalogue(path, version)
    engine = make_engine(get_settings())
    try:
        stored = await PgCorpus(make_sessionmaker(engine)).ensure_catalogue(catalogue)
    finally:
        await engine.dispose()
    print(f"catalogue v{stored.version}: {len(stored.locations)} locations, checksum {stored.checksum[:12]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--out", type=Path, required=True)
    d.add_argument("--cache", type=Path, default=None)
    a = sub.add_parser("apply")
    a.add_argument("--file", type=Path, required=True)
    a.add_argument("--version", type=int, default=None)
    args = parser.parse_args()
    if args.cmd == "discover":
        asyncio.run(discover(args.out, args.cache))
    else:
        asyncio.run(apply(args.file, args.version))


if __name__ == "__main__":
    main()
