"""Typed vision/OCR outputs and the +/-15 % clamp on LLM adjustments (docs/ENGINE-SPEC.md row 12,
invariant 4).

The model output is untrusted text. It is parsed into a bounded, typed `VisionOutput` (anything else is
rejected),
it can only *propose* percentage adjustments, and every proposal is clamped to +/-15 % of a
deterministic base before it
touches a number. The record of what was proposed and what was applied (plus model and prompt version)
makes every audit
reproducible without calling the model again.
LEGAL[images]: this module only consumes the already-produced assessment; fetching and sending images
is in the worker.
"""

import json
import re
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, field_validator

from deal_analyzer.money import ONE, ZERO, engine_math

MAX_ADJUSTMENT = Decimal("0.15")  # the clamp: +/- 15 % of the deterministic base, never more
MAX_PHOTOS = 25
MAX_PLANS = 2
MAX_IMAGES = MAX_PHOTOS + MAX_PLANS  # one assessment per image sent: 25 photos then 2 floor plans (G-02)
MAX_EQUIPMENT = 40
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class VisionOutputError(ValueError):
    """The model answer is not a usable `VisionOutput`; the audit continues as `succeeded_degraded`."""


class PhotoKind(StrEnum):
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    FLOOR_PLAN = "floor_plan"
    RENDER = "render"  # computer-generated: never evidence of condition
    STAGING = "staging"  # virtual staging: never evidence of condition
    OTHER = "other"


class Condition(StrEnum):
    GOOD = "good"
    REFRESH = "refresh"
    RENOVATION = "renovation"
    SHELL = "shell"
    UNKNOWN = "unknown"


EXCLUDED_KINDS = frozenset({PhotoKind.RENDER, PhotoKind.STAGING})


class SaleStatus(StrEnum):
    """Whether an item seen in the listing media is part of the sale. Unknown is the honest default."""

    INCLUDED = "included"  # the listing text or plan says it stays
    VISIBLE_ONLY = "visible_only"  # seen in a photo, nothing says it is sold with the flat
    UNKNOWN = "unknown"


class EvidenceSource(StrEnum):
    PHOTO = "photo"
    FLOOR_PLAN = "floor_plan"
    UNATTRIBUTED = "unattributed"  # the model named no usable image


class EquipmentObservation(BaseModel):
    """One piece of equipment or fit-out the model saw, linked to the image it came from (G-02).

    Factual evidence only: it never feeds a number (invariant 4). `media_ordinal` is the position in the
    selected media list (photos in listing order, then floor plans), the `ordinal` of the media manifest.
    LEGAL[images]: derived from listing photos and plans sent to a third party (RM-387)
    LEGAL[republication]: shown back to users, so bounded and stripped of control characters (RM-387)
    GDPR[processor]: produced by the vision model behind OpenRouter (RM-387)
    """

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    item: str = Field(min_length=1, max_length=80)
    # the model answers with `image_index` (0-based, order sent); the worker rewrites it to the ordinal
    media_ordinal: int | None = Field(
        default=None, ge=0, lt=MAX_IMAGES, validation_alias=AliasChoices("image_index", "media_ordinal")
    )
    confidence: Decimal = Field(ge=ZERO, le=ONE)
    provenance: EvidenceSource = EvidenceSource.UNATTRIBUTED
    sale_status: SaleStatus = SaleStatus.UNKNOWN

    @field_validator("item")
    @classmethod
    def _clean_item(cls, value: str) -> str:
        cleaned = " ".join(_CONTROL.sub("", value).split())
        if not cleaned:
            raise ValueError("empty item")
        return cleaned


class PhotoAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: PhotoKind


class VisionOutput(BaseModel):
    """What the vision model may tell us. Unknown keys are ignored, but nothing outside these fields
    is ever used."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    condition: Condition = Condition.UNKNOWN
    photos: tuple[PhotoAssessment, ...] = Field(default=(), max_length=MAX_IMAGES)
    capex_adjustment: Decimal = Field(
        default=ZERO, ge=Decimal(-10), le=Decimal(10)
    )  # proposed fraction of the base
    rent_adjustment: Decimal = Field(default=ZERO, ge=Decimal(-10), le=Decimal(10))
    floor_plan_text: str | None = Field(default=None, max_length=4_000)
    notes: str | None = Field(default=None, max_length=1_000)

    equipment: tuple[EquipmentObservation, ...] = Field(default=(), max_length=MAX_EQUIPMENT)

    @field_validator("equipment", mode="before")
    @classmethod
    def _keep_valid_equipment(cls, value: Any) -> Any:
        """One malformed observation must not void the whole answer (and with it the finance adjustments):
        unusable entries are dropped, the rest kept up to the cap."""
        if not isinstance(value, (list, tuple)):
            return ()
        items: list[Any] = list(value)  # type: ignore[arg-type]
        kept: list[EquipmentObservation] = []
        for raw in items:
            if isinstance(raw, EquipmentObservation):
                kept.append(raw)
                continue
            try:
                kept.append(EquipmentObservation.model_validate(raw))
            except ValidationError:
                continue
        return tuple(kept[:MAX_EQUIPMENT])

    @field_validator("floor_plan_text", "notes")
    @classmethod
    def _printable(cls, value: str | None) -> str | None:
        return _CONTROL.sub("", value) if value else value


def _reject_constant(name: str) -> Any:
    raise VisionOutputError(f"JSON constant {name} is not allowed")


def parse_vision_output(raw: str | dict[str, Any]) -> VisionOutput:
    """Parse the model's JSON answer (optionally fenced). Raises `VisionOutputError` for anything unusable."""
    try:
        if isinstance(raw, str):
            if len(raw) > 100_000:
                raise VisionOutputError("answer is too long")
            match = _FENCE.match(raw)
            data: Any = json.loads(
                match.group(1) if match else raw, parse_float=Decimal, parse_constant=_reject_constant
            )
        else:
            data = raw
        if not isinstance(data, dict):
            raise VisionOutputError("answer is not a JSON object")
        return VisionOutput.model_validate(data)
    except (ValueError, ValidationError) as exc:
        if isinstance(exc, VisionOutputError):
            raise
        raise VisionOutputError("answer does not match the expected shape") from exc


class Applied(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    base: Decimal
    proposed: Decimal  # as proposed by the model (a fraction: 0.20 = +20 %)
    applied: Decimal  # after the clamp
    clamped: bool
    value: Decimal  # base * (1 + applied)


def clamp_adjustment(base: Decimal, proposed: Decimal) -> Applied:
    """Apply a proposed percentage to a deterministic base, limited to +/- 15 % (invariant 4)."""
    with engine_math():
        applied = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, proposed))
        return Applied(
            base=base,
            proposed=proposed,
            applied=applied,
            clamped=applied != proposed,
            value=base * (ONE + applied),
        )


class VisionRecord(BaseModel):
    """Everything needed to reproduce an audit without the model: provenance plus proposed and applied
    adjustments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model: str = Field(max_length=120)
    prompt_version: str = Field(max_length=40)
    condition: Condition
    photos_total: int
    photos_excluded: int
    capex: Applied | None
    rent: Applied | None
    # G-02: evidence kept for the report so a reload needs no second model call. Additive within schema
    # version 1 (`ADDITIVE_FIELDS` in scripts/gen_report_schema.py); old stored reports lack them.
    # LEGAL[images]: text transcribed from listing floor plans and notes about photos (RM-387)
    # LEGAL[republication]: echoed to the audit's owner in the report (RM-387)
    # GDPR[processor]: OCR text may contain names printed on a plan; produced via OpenRouter (RM-387)
    floor_plan_text: str | None = Field(default=None, max_length=4_000)
    notes: str | None = Field(default=None, max_length=1_000)
    equipment: tuple[EquipmentObservation, ...] = Field(default=(), max_length=MAX_EQUIPMENT)


def usable_photo_count(output: VisionOutput) -> tuple[int, int]:
    """(usable, excluded): renders and virtual staging never count as evidence of the flat's condition."""
    excluded = sum(1 for p in output.photos if p.kind in EXCLUDED_KINDS)
    return len(output.photos) - excluded, excluded


def progress_message(output: VisionOutput) -> str:
    usable, excluded = usable_photo_count(output)
    return f"{usable + excluded} photos, {excluded} renders excluded"


def apply_vision(
    output: VisionOutput,
    *,
    model: str,
    prompt_version: str,
    capex_base: Decimal | None,
    rent_base: Decimal | None,
) -> VisionRecord:
    """Clamp the model's proposals against the deterministic bases. A missing base means no adjustment
    is applied."""
    usable, excluded = usable_photo_count(output)
    return VisionRecord(
        model=model,
        prompt_version=prompt_version,
        condition=output.condition,
        photos_total=usable + excluded,
        photos_excluded=excluded,
        capex=clamp_adjustment(capex_base, output.capex_adjustment) if capex_base is not None else None,
        rent=clamp_adjustment(rent_base, output.rent_adjustment) if rent_base is not None else None,
        floor_plan_text=output.floor_plan_text,
        notes=output.notes,
        equipment=output.equipment,
    )
