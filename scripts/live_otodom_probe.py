"""One live Otodom listing fetch, owner-authorised, to settle L-005 (listing shape) and L-002 (datacenter IP).

Usage: uv run python scripts/live_otodom_probe.py <listing URL or ID...>

Makes exactly one GET per argument through the production transport (no retries, no throttle, no storage).
Prints status, challenge markers and the *shape* of `props.pageProps.ad` (key names and value types only).
No listing values are printed, so seller names and phones never reach the terminal, logs or the repo.

LEGAL[scraping]: one authorised live fetch of an Otodom page with browser TLS impersonation (RM-42).
GDPR[personal-data]: the response may hold seller data; this script discards it and prints names only (RM-42).
"""

import asyncio
import json
import sys
from typing import Any

from rm_core.listing_ref import parse_listing_ref
from rm_worker.clients.otodom import _CHALLENGE_MARKERS, _NEXT_DATA, HOST, classify
from rm_worker.clients.otodom_transport import CurlCffiTransport

TOTAL_S = 30.0
MAX_DEPTH = 2
HEADERS = {"accept": "text/html,application/xhtml+xml", "accept-language": "pl-PL,pl;q=0.9,en;q=0.5"}


def shape(value: Any, depth: int = 0) -> Any:
    if isinstance(value, dict) and depth < MAX_DEPTH:
        return {key: shape(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return f"list[{len(value)}]"
    return type(value).__name__


async def probe(ref: str) -> None:
    short_id = parse_listing_ref(ref)
    url = f"https://{HOST}/pl/oferta/{short_id}"
    raw = await CurlCffiTransport().get(url, headers=HEADERS, total_s=TOTAL_S)
    text = raw.body.decode("utf-8", errors="replace")
    print(f"status={raw.status} bytes={len(raw.body)} final_path_has_oferta={'/oferta/' in raw.final_url}")
    print(f"has_next_data={bool(_NEXT_DATA.search(text))}")
    print(f"challenge_markers={[m for m in _CHALLENGE_MARKERS if m in text[:200_000].lower()]}")
    try:
        ad = classify(raw)
    except Exception as exc:  # a probe reports every failure class
        print(f"classify=FAIL {type(exc).__name__}: {exc}")
        return
    print("classify=OK")
    print(json.dumps(shape(ad), indent=2, sort_keys=True))


async def main(refs: list[str]) -> None:
    for ref in refs:
        await probe(ref)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    asyncio.run(main(sys.argv[1:]))
