"""Live probe of the product media bucket: PUT, HEAD, GET (hash equal), anonymous denial, DELETE, absence.

Run: uv run python scripts/probe_media_store.py
Reads MEDIA_* settings from the environment or the private root .env; prints only sanitised results, never
keys, endpoints or provider error text. Touches one unique `probe/` object and deletes only that one (RM-447).
"""

import asyncio
import hashlib
import sys
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from rm_core.object_store import ObjectStoreError, S3ObjectStore
from rm_core.settings import Settings


async def main() -> int:
    settings = Settings()
    if not settings.media_store_configured:
        print("FAIL not_configured: set the four MEDIA_* settings (.env.example)")
        return 2
    store = S3ObjectStore.from_settings(settings)
    key = f"probe/{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}"
    body = f"media store probe {uuid4().hex}".encode()
    digest = hashlib.sha256(body).hexdigest()
    steps: list[tuple[str, bool]] = []
    try:
        put = await store.put(key, body, "text/plain")
        steps.append(("put", put.sha256 == digest))
        head = await store.head(key)
        steps.append(("head", head is not None and head.size == len(body)))
        steps.append(("get_hash_equal", hashlib.sha256(await store.get(key)).hexdigest() == digest))
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            anon = await http.get(f"{settings.media_s3_endpoint}/{settings.media_bucket}/{key}")
        # The S3 endpoint answers an unsigned request with 400 (auth required); 401/403 are equally a denial.
        denied = anon.status_code in (400, 401, 403) and body not in anon.content
        steps.append(("anonymous_denied", denied))
    except ObjectStoreError as exc:
        steps.append((f"error_{exc.code}", False))
    finally:
        try:
            await store.delete(key)
            steps.append(("delete_absent", await store.head(key) is None))
        except ObjectStoreError as exc:
            steps.append((f"cleanup_error_{exc.code}", False))
    for name, ok in steps:
        print(("PASS " if ok else "FAIL ") + name)
    print("endpoint_jurisdiction", "eu" if ".eu.r2." in settings.media_s3_endpoint else "default")
    return 0 if all(ok for _, ok in steps) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
