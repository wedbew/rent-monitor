"""Media manifest contract: identity, cardinality, explicit failure states, closed schema (RM-376)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from rm_contracts.media import MAX_PHOTOS, MAX_PLANS, MediaItem, MediaKind, MediaManifest, MediaState

DIGEST = "a" * 64


def item(ordinal: int, kind: MediaKind = MediaKind.photo, **kw: object) -> MediaItem:
    return MediaItem.model_validate({"ordinal": ordinal, "kind": kind.value, "source_type": "url", **kw})


def stored(ordinal: int, kind: MediaKind = MediaKind.photo) -> MediaItem:
    return item(
        ordinal, kind, state="stored", content_digest=DIGEST, mime="image/jpeg", width=800, height=600
    )


def manifest(photos: int, plans: int) -> MediaManifest:
    items = [stored(i) for i in range(photos)] + [stored(photos + j, MediaKind.plan) for j in range(plans)]
    return MediaManifest(audit_id=uuid4(), items=items)


def test_25_photos_and_2_plans_are_accepted() -> None:
    assert len(manifest(MAX_PHOTOS, MAX_PLANS).items) == 27


def test_26_photos_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 25 photos"):
        manifest(MAX_PHOTOS + 1, 0)


def test_3_plans_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 2 floor plans"):
        manifest(1, MAX_PLANS + 1)


def test_duplicate_ordinal_and_media_id_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate ordinal"):
        MediaManifest(audit_id=uuid4(), items=[item(0), item(0)])
    same = item(0)
    with pytest.raises(ValidationError, match="duplicate media_id"):
        MediaManifest(audit_id=uuid4(), items=[same, same.model_copy(update={"ordinal": 1})])


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        MediaItem.model_validate({"ordinal": 0, "kind": "photo", "source_type": "url", "url": "http://x"})
    with pytest.raises(ValidationError):
        MediaManifest.model_validate({"audit_id": str(uuid4()), "items": [], "extra": 1})


def test_failure_must_be_explained_and_stored_must_be_complete() -> None:
    with pytest.raises(ValidationError, match="failure_code"):
        item(0, state="failed")
    with pytest.raises(ValidationError, match="content_digest"):
        item(0, state="stored")
    assert item(0, state="failed", failure_code="DOWNLOAD_TIMEOUT").state is MediaState.failed


def test_bad_digest_dimensions_and_naive_expiry_are_rejected() -> None:
    with pytest.raises(ValidationError):
        item(0, content_digest="XYZ")
    with pytest.raises(ValidationError, match="go together"):
        item(0, width=10)
    with pytest.raises(ValidationError, match="timezone-aware"):
        item(0, expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1))


def test_round_trip_through_json_is_lossless() -> None:
    m = manifest(3, 1)
    assert MediaManifest.model_validate_json(m.model_dump_json()) == m
