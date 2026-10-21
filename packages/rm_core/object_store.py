"""Private object store for product media: an injectable seam, an R2/S3 client and an in-memory fake (RM-447).

Bytes live here; ownership, state and retention live in Postgres (ADR 0014). The two cannot share a
transaction, so callers write the row first, then the object, and a reconciler removes either half that
outlives the other.

Keys are built only by `media_key` from a validated user id, purpose and object id: callers never pass a
free-form key, and the store never signs or returns a URL (delivery is an authenticated API route).

LEGAL[images]: stores normalised room photos and generated images for tenants (RM-447)
GDPR[processor]: Cloudflare R2 holds users' images; EU endpoint enforced by settings (RM-447)
GDPR[retention]: objects are deleted by the retention job and with the account (RM-447)
"""

import asyncio
import hashlib
import importlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

import structlog
from botocore.config import Config  # pyright: ignore[reportMissingTypeStubs]
from botocore.exceptions import BotoCoreError, ClientError  # pyright: ignore[reportMissingTypeStubs]

from rm_core.settings import Settings

log = structlog.get_logger()

MAX_OBJECT_BYTES = 12 * 1024 * 1024  # a normalised image is far smaller; caps a hostile or broken read
_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class MediaPurpose(StrEnum):
    source = "source"  # normalised room photo, never overwritten
    reference = "reference"  # a permitted product reference image
    item = "item"  # a photo of the person's own item
    render = "render"  # generated output


class ObjectStoreError(Exception):
    """A store failure. `code` is stable and carries no provider text, credentials or URLs."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str | None
    sha256: str | None


def media_key(user_id: str, purpose: MediaPurpose, object_id: UUID) -> str:
    """The only way to name an object: `u/<user>/<purpose>/<uuid>`; the user id is validated."""
    if not _USER_ID.fullmatch(user_id):
        raise ValueError("invalid user id for an object key")
    return f"u/{user_id}/{purpose.value}/{object_id}"


def user_prefix(user_id: str) -> str:
    if not _USER_ID.fullmatch(user_id):
        raise ValueError("invalid user id for an object prefix")
    return f"u/{user_id}/"


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> ObjectInfo: ...
    async def get(self, key: str) -> bytes: ...
    async def head(self, key: str) -> ObjectInfo | None: ...
    async def delete(self, key: str) -> None: ...
    async def list_keys(self, prefix: str, limit: int) -> list[str]: ...


class MemoryObjectStore:
    """Offline fake with the same contract. `fail_next` injects a store error for the next call."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_next: str | None = None

    def _maybe_fail(self) -> None:
        if self.fail_next is not None:
            code, self.fail_next = self.fail_next, None
            raise ObjectStoreError(code)

    async def put(self, key: str, data: bytes, content_type: str) -> ObjectInfo:
        self._maybe_fail()
        if len(data) > MAX_OBJECT_BYTES:
            raise ObjectStoreError("too_large")
        self.objects[key] = (data, content_type)
        return ObjectInfo(len(data), content_type, hashlib.sha256(data).hexdigest())

    async def get(self, key: str) -> bytes:
        self._maybe_fail()
        if key not in self.objects:
            raise ObjectStoreError("not_found")
        return self.objects[key][0]

    async def head(self, key: str) -> ObjectInfo | None:
        self._maybe_fail()
        found = self.objects.get(key)
        if found is None:
            return None
        return ObjectInfo(len(found[0]), found[1], hashlib.sha256(found[0]).hexdigest())

    async def delete(self, key: str) -> None:
        self._maybe_fail()
        self.objects.pop(key, None)  # deleting an absent object succeeds, like S3

    async def list_keys(self, prefix: str, limit: int) -> list[str]:
        self._maybe_fail()
        return sorted(k for k in self.objects if k.startswith(prefix))[:limit]


class S3ObjectStore:
    """boto3 against the EU-jurisdiction R2 endpoint. Blocking calls run in a thread; every call has a
    timeout and at most two retries inside botocore. Provider error text is never surfaced."""

    def __init__(self, client: Any, bucket: str):
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3ObjectStore":
        if not settings.media_store_configured:
            raise ObjectStoreError("not_configured")
        boto3: Any = importlib.import_module("boto3")  # lazy: only media processes pay for the import

        timeout = settings.media_s3_timeout_s
        client: Any = boto3.client(
            "s3",
            endpoint_url=settings.media_s3_endpoint,
            aws_access_key_id=settings.media_access_key_id,
            aws_secret_access_key=settings.media_secret_access_key.get_secret_value(),
            region_name="auto",
            config=Config(
                connect_timeout=5,
                read_timeout=timeout,
                retries={"max_attempts": 3, "mode": "standard"},
                signature_version="s3v4",
            ),
        )
        return cls(client, settings.media_bucket)

    async def _call(self, fn: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(fn, **kwargs)
        except ClientError as exc:
            response: dict[str, Any] = exc.response
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            raw = response.get("Error", {}).get("Code")
            if status == 404 or raw in {"NoSuchKey", "NotFound"}:
                raise ObjectStoreError("not_found") from None
            log.warning("object_store_rejected", status=status, provider_code=raw)
            raise ObjectStoreError("rejected") from None
        except BotoCoreError as exc:
            log.warning("object_store_unavailable", error=type(exc).__name__)
            raise ObjectStoreError("unavailable") from None

    async def put(self, key: str, data: bytes, content_type: str) -> ObjectInfo:
        if len(data) > MAX_OBJECT_BYTES:
            raise ObjectStoreError("too_large")
        digest = hashlib.sha256(data).hexdigest()
        await self._call(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return ObjectInfo(len(data), content_type, digest)

    async def get(self, key: str) -> bytes:
        def read(**kwargs: Any) -> bytes:
            body = self._client.get_object(**kwargs)["Body"]
            try:
                data: bytes = body.read(MAX_OBJECT_BYTES + 1)
            finally:
                body.close()
            if len(data) > MAX_OBJECT_BYTES:
                raise ObjectStoreError("too_large")
            return data

        data: bytes = await self._call(read, Bucket=self._bucket, Key=key)
        return data

    async def head(self, key: str) -> ObjectInfo | None:
        try:
            r = await self._call(self._client.head_object, Bucket=self._bucket, Key=key)
        except ObjectStoreError as exc:
            if exc.code == "not_found":
                return None
            raise
        meta: dict[str, str] = r.get("Metadata") or {}
        return ObjectInfo(int(r["ContentLength"]), r.get("ContentType"), meta.get("sha256"))

    async def delete(self, key: str) -> None:
        await self._call(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def list_keys(self, prefix: str, limit: int) -> list[str]:
        r = await self._call(
            self._client.list_objects_v2, Bucket=self._bucket, Prefix=prefix, MaxKeys=min(limit, 1000)
        )
        return [o["Key"] for o in r.get("Contents", [])][:limit]
