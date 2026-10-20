"""Print or write the Otodom corpus coverage manifest as JSON (RM-411).

Usage: `uv run python scripts/market_manifest.py [--version 1] [--out FILE] [--summary]`
Reads DATABASE_URL like every service. Counts and states only, no offer content. `--summary` prints the
headline numbers without the per-location list.

LEGAL[third-party-data]: aggregates about stored asking-rent offers; nothing is fetched (RM-411).
"""

import argparse
import asyncio
import json
from pathlib import Path

from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.market_manifest import coverage_manifest
from rm_core.settings import get_settings


async def main(version: int | None, out: Path | None, summary: bool) -> None:
    settings = get_settings()
    engine = make_engine(settings, pool_size=1, max_overflow=0)
    try:
        manifest = await coverage_manifest(
            make_sessionmaker(engine), version or settings.otodom_market_catalogue_version
        )
    finally:
        await engine.dispose()
    if summary:
        manifest = {k: v for k, v in manifest.items() if k != "locations"}
    text = json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"
    if out is None:
        print(text, end="")
    else:
        await asyncio.to_thread(out.write_text, text)
        print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.version, args.out, args.summary))
