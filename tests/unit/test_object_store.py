"""Object store seam: key discipline, fake contract, S3 client error mapping, EU-only settings (RM-447)."""

import hashlib
import io
from uuid import uuid4

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from pydantic import ValidationError
from rm_core.object_store import (
    MAX_OBJECT_BYTES,
    MediaPurpose,
    MemoryObjectStore,
    ObjectStoreError,
    S3ObjectStore,
    media_key,
    user_prefix,
)
from rm_core.settings import Settings

EU = "https://0123456789abcdef0123456789abcdef.eu.r2.cloudflarestorage.com"


def _s3() -> tuple[S3ObjectStore, Stubber]:
    client = boto3.client(
        "s3", endpoint_url=EU, region_name="auto", aws_access_key_id="k", aws_secret_access_key="s"
    )
    return S3ObjectStore(client, "media"), Stubber(client)


def test_media_key_is_tenant_scoped_and_validated() -> None:
    oid = uuid4()
    assert media_key("usr_1", MediaPurpose.source, oid) == f"u/usr_1/source/{oid}"
    assert user_prefix("usr_1") == "u/usr_1/"
    for bad in ("", "../x", "a/b", "a" * 65, "u 1"):
        with pytest.raises(ValueError, match="invalid"):
            media_key(bad, MediaPurpose.render, oid)
        with pytest.raises(ValueError, match="invalid"):
            user_prefix(bad)


async def test_memory_store_contract() -> None:
    store = MemoryObjectStore()
    key = media_key("u1", MediaPurpose.source, uuid4())
    info = await store.put(key, b"abc", "image/jpeg")
    assert info.size == 3
    assert info.sha256
    assert await store.get(key) == b"abc"
    assert (await store.head(key)) == info
    assert await store.list_keys("u/u1/", 10) == [key]
    assert await store.list_keys("u/u2/", 10) == []
    await store.delete(key)
    await store.delete(key)  # absent delete succeeds
    assert await store.head(key) is None
    with pytest.raises(ObjectStoreError) as err:
        await store.get(key)
    assert err.value.code == "not_found"
    with pytest.raises(ObjectStoreError):
        await store.put(key, b"x" * (MAX_OBJECT_BYTES + 1), "image/jpeg")
    store.fail_next = "unavailable"
    with pytest.raises(ObjectStoreError):
        await store.head(key)
    assert await store.head(key) is None  # one-shot failure


async def test_s3_put_head_get_delete_round_trip() -> None:
    store, stub = _s3()
    key = "u/u1/source/x"
    stub.add_response(
        "put_object",
        {},
        {
            "Bucket": "media",
            "Key": key,
            "Body": b"abc",
            "ContentType": "image/jpeg",
            "Metadata": {"sha256": _sha(b"abc")},
        },
    )
    stub.add_response(
        "head_object",
        {"ContentLength": 3, "ContentType": "image/jpeg", "Metadata": {"sha256": _sha(b"abc")}},
        {"Bucket": "media", "Key": key},
    )
    stub.add_response("get_object", {"Body": _body(b"abc")}, {"Bucket": "media", "Key": key})
    stub.add_response("delete_object", {}, {"Bucket": "media", "Key": key})
    with stub:
        put = await store.put(key, b"abc", "image/jpeg")
        head = await store.head(key)
        assert head is not None
        assert head.sha256 == put.sha256
        assert head.size == 3
        assert await store.get(key) == b"abc"
        await store.delete(key)
    stub.assert_no_pending_responses()


async def test_s3_missing_object_and_provider_errors_are_mapped_without_provider_text() -> None:
    store, stub = _s3()
    stub.add_client_error("head_object", http_status_code=404, service_error_code="404")
    stub.add_client_error("get_object", http_status_code=404, service_error_code="NoSuchKey")
    stub.add_client_error(
        "put_object",
        http_status_code=403,
        service_error_code="AccessDenied",
        service_message="secret-bearing provider text",
    )
    with stub:
        assert await store.head("u/u1/source/x") is None
        with pytest.raises(ObjectStoreError) as missing:
            await store.get("u/u1/source/x")
        assert missing.value.code == "not_found"
        with pytest.raises(ObjectStoreError) as denied:
            await store.put("u/u1/source/x", b"a", "image/png")
        assert denied.value.code == "rejected"
        assert "secret" not in str(denied.value)


async def test_s3_get_rejects_an_oversized_body() -> None:
    store, stub = _s3()
    stub.add_response(
        "get_object", {"Body": _body(b"x" * (MAX_OBJECT_BYTES + 1))}, {"Bucket": "media", "Key": "k"}
    )
    with stub, pytest.raises(ObjectStoreError) as err:
        await store.get("k")
    assert err.value.code == "too_large"


def test_from_settings_refuses_when_unconfigured() -> None:
    with pytest.raises(ObjectStoreError) as err:
        S3ObjectStore.from_settings(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    assert err.value.code == "not_configured"


def test_settings_accept_only_the_eu_endpoint() -> None:
    ok = Settings(_env_file=None, media_s3_endpoint=EU + "/")  # pyright: ignore[reportCallIssue]
    assert ok.media_s3_endpoint == EU
    for bad in (
        "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com",  # default jurisdiction
        "http://x.eu.r2.cloudflarestorage.com",
        "https://example.com",
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, media_s3_endpoint=bad)  # pyright: ignore[reportCallIssue]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _body(data: bytes) -> object:
    return StreamingBody(io.BytesIO(data), len(data))
