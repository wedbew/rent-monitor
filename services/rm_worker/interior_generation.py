"""Run one interior generation: claim, gather inputs, reserve, call the model once, store, settle (RM-450).

Money rules (owner decision 2026-10-19: USD 5 shared, USD 0.50 per attempt, no bypass):
- the estimate is reserved atomically from the shared AI budget before any paid call; none left means
  the operation fails `BUDGET_EXHAUSTED` and nothing is sent;
- `request_sent_at` is committed before the call. A definite refusal or a request that never left
  releases the reservation; a sent request without a usable answer is `AMBIGUOUS`: the estimate is
  settled (kept charged) and the operation is never retried by itself, so a lost answer cannot become
  a second paid call;
- a success settles the provider-reported cost (or the estimate, flagged `cost_estimated`);
- every transition is a conditional UPDATE, so duplicate delivery, cancel and recovery settle exactly once.

The room photo is the digest-bound `source` of the revision, read back from the store and verified; it
is never modified. Reference images are only sent when the source grants `generation_reference`
(catalogue photos) or the person supplied them (own items); otherwise the item is described by name only
and counted as skipped.

LEGAL[images]: sends the room photo and permitted reference images to an image model (RM-450)
GDPR[processor]: OpenRouter and its model provider (RM-450)
"""

import asyncio
import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import structlog
from rm_contracts.catalogue import SelectionSnapshot
from rm_contracts.generation import GenerationError, GenerationState
from rm_contracts.interior import Brief, ItemSnapshot
from rm_core import interior_generation as ops
from rm_core.ai_budget import CallUsage
from rm_core.catalogue import demo_image_png
from rm_core.db.models import InteriorGeneration, InteriorMedia, InteriorRevision
from rm_core.deadline import Deadline
from rm_core.interior import store_render
from rm_core.interior_images import ImageRejectedError, normalize_image
from rm_core.interior_prompt import MAX_REFERENCES, PromptItem, build_prompt
from rm_core.legal import LegalTag, tag_names
from rm_core.object_store import ObjectStore, ObjectStoreError
from rm_core.settings import Settings
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.image_gen import (
    GeneratedImage,
    ImageGenerator,
    ImageRequest,
    OutcomeUnknown,
    ProviderNotReached,
    ProviderRejected,
)

log = structlog.get_logger(__name__)
LEGAL_TAGS = tag_names(LegalTag.images, LegalTag.processor)
DEMO_IMAGE_PREFIX = "/api/interior/catalogue/demo-image/"


class Ticket(Protocol):
    @property
    def reservation_id(self) -> UUID: ...

    async def settle(self, actual_usd: Decimal, usage: CallUsage | None = None) -> None: ...

    async def release(self) -> None: ...


class Gate(Protocol):
    async def reserve(self, estimate_usd: Decimal) -> Ticket | None: ...


@dataclass
class Deps:
    sm: async_sessionmaker[AsyncSession]
    store: ObjectStore
    generator: ImageGenerator
    gate: Gate
    settings: Settings


@dataclass(frozen=True)
class Inputs:
    source: bytes
    references: list[bytes]
    prompt: str
    skipped: int


class _Fail(Exception):
    def __init__(self, error: GenerationError):
        super().__init__(error.value)
        self.error = error


async def _media_bytes(deps: Deps, project_id: UUID, digest: str, purpose: str) -> bytes | None:
    async with deps.sm() as db:
        row = await db.scalar(
            select(InteriorMedia).where(
                InteriorMedia.project_id == project_id,
                InteriorMedia.content_digest == digest,
                InteriorMedia.purpose == purpose,
                InteriorMedia.state == "stored",
            )
        )
        key = row.object_key if row is not None else None
    if key is None:
        return None
    try:
        data = await deps.store.get(key)
    except ObjectStoreError:
        return None
    return data if hashlib.sha256(data).hexdigest() == digest else None  # a corrupted object is never sent


def _offer_reference(selection: SelectionSnapshot) -> bytes | None:
    """Bytes of a picked product's photo, only if its source grants generation use. Today only the demo
    source's own placeholder pictures can be produced locally; fetching a real merchant photo needs an
    approved host allow-list and the owner's written permission (B-026, L-099): it is skipped and counted."""
    offer = selection.offer
    if not offer.image_rights.generation_reference or offer.image_url is None:
        return None
    if offer.provider == "demo" and offer.image_url.startswith(DEMO_IMAGE_PREFIX):
        return demo_image_png(offer.product_id, offer.variant_id)
    return None


def _jpeg(data: bytes) -> bytes | None:
    try:
        return normalize_image(data).data
    except ImageRejectedError:
        return None


async def gather_inputs(deps: Deps, generation: InteriorGeneration) -> Inputs:
    async with deps.sm() as db:
        revision = await db.get(InteriorRevision, generation.revision_id)
        if revision is None or revision.source_digest is None:
            raise _Fail(GenerationError.NO_SOURCE_PHOTO)
        snapshot = revision.snapshot
        source_digest = revision.source_digest
    source = await _media_bytes(deps, generation.project_id, source_digest, "source")
    if source is None:
        raise _Fail(GenerationError.NO_SOURCE_PHOTO)
    brief = Brief.model_validate(snapshot["brief"])
    references: list[bytes] = []
    items: list[PromptItem] = []
    skipped = 0

    def add(label: str, detail: str, quantity: int, image: bytes | None) -> None:
        nonlocal skipped
        number: int | None = None
        if image is not None and len(references) < MAX_REFERENCES:
            prepared = _jpeg(image)
            if prepared is not None:
                references.append(prepared)
                number = len(references)
        if number is None:
            skipped += 1
        items.append(PromptItem(label, detail, quantity, number))

    for raw in snapshot.get("selections", []):
        selection = SelectionSnapshot.model_validate(raw)
        detail = ", ".join(f"{k}: {v}" for k, v in selection.offer.attributes.items())
        add(selection.offer.title, detail, selection.quantity, _offer_reference(selection))
    for raw in snapshot["items"]:
        item = ItemSnapshot.model_validate(raw)
        photo = (
            await _media_bytes(deps, generation.project_id, item.photo_digest, "custom_item")
            if item.photo_digest
            else None
        )
        add(item.name, "", item.quantity, photo)
    return Inputs(source, references, build_prompt(brief, items), skipped)


async def run_generation(deps: Deps, generation_id: UUID) -> None:
    generation = await ops.claim(deps.sm, generation_id)
    if generation is None:
        return  # duplicate delivery, or cancelled while queued
    tags = {"generation_id": str(generation_id), "legal_tags": LEGAL_TAGS}
    ticket: Ticket | None = None
    sent = False
    try:
        inputs = await gather_inputs(deps, generation)
        await ops.set_references(deps.sm, generation_id, len(inputs.references), inputs.skipped)
        ticket = await deps.gate.reserve(generation.estimate_usd)
        if ticket is None:
            log.warning("interior_generation_budget_exhausted", **tags)
            raise _Fail(GenerationError.BUDGET_EXHAUSTED)
        await ops.record_reservation(deps.sm, generation_id, ticket.reservation_id)
        await ops.mark_sent(deps.sm, generation_id)
        sent = True
        deadline = Deadline.after(deps.settings.interior_generation_deadline_s)
        request = ImageRequest(generation.model, inputs.prompt, [inputs.source, *inputs.references])
        result = await deps.generator.generate(request, deadline=deadline)
    except _Fail as exc:
        await ops.finish(deps.sm, generation_id, GenerationState.failed, error=exc.error)
    except (ProviderNotReached, ProviderRejected) as exc:
        await _fail_not_billed(deps, generation_id, ticket, exc)
    except (OutcomeUnknown, TimeoutError, asyncio.CancelledError) as exc:
        await _fail_unknown(deps, generation, ticket, exc)
        if isinstance(exc, asyncio.CancelledError):
            raise
    except Exception:
        log.exception("interior_generation_crashed", sent=sent, **tags)
        await _fail_unknown(deps, generation, ticket, None, sent=sent)
    else:
        assert ticket is not None  # noqa: S101  (a result implies the reservation was taken)
        await _succeed(deps, generation, ticket, result)


async def _fail_not_billed(
    deps: Deps, generation_id: UUID, ticket: Ticket | None, exc: ProviderNotReached | ProviderRejected
) -> None:
    if ticket is not None:
        await ticket.release()  # the request never left, or was refused: nothing was billed
    error = (
        GenerationError.PROVIDER_UNAVAILABLE
        if isinstance(exc, ProviderNotReached)
        else GenerationError.PROVIDER_REJECTED
    )
    log.warning("interior_generation_not_billed", error=error.value, generation_id=str(generation_id))
    await ops.finish(deps.sm, generation_id, GenerationState.failed, error=error)


async def _fail_unknown(
    deps: Deps,
    generation: InteriorGeneration,
    ticket: Ticket | None,
    exc: BaseException | None,
    *,
    sent: bool = True,
) -> None:
    """Sent without a usable answer (or crashed after sending): keep the estimate charged, never retry alone.
    A crash before anything was sent releases the reservation instead."""
    if ticket is not None:
        if sent:
            await ticket.settle(generation.estimate_usd, CallUsage(model=generation.model, estimated=True))
        else:
            await ticket.release()
    if exc is None:
        error = GenerationError.INTERNAL
    else:
        error = GenerationError.TIMEOUT if isinstance(exc, TimeoutError) else GenerationError.AMBIGUOUS
    log.error("interior_generation_outcome_unknown", error=error.value, generation_id=str(generation.id))
    await ops.finish(
        deps.sm,
        generation.id,
        GenerationState.failed,
        error=error,
        cost_usd=generation.estimate_usd if sent and ticket is not None else None,
        cost_estimated=sent and ticket is not None,
    )


async def _succeed(
    deps: Deps, generation: InteriorGeneration, ticket: Ticket, result: GeneratedImage
) -> None:
    cost = result.cost_usd if result.cost_usd is not None else generation.estimate_usd
    estimated = result.cost_usd is None
    await ticket.settle(cost, CallUsage(model=generation.model, estimated=estimated))
    error: GenerationError | None = None
    media_id: UUID | None = None
    try:
        media_id = await store_render(
            deps.sm, deps.store, generation.user_id, generation.project_id, result.data
        )
    except ImageRejectedError:
        error = GenerationError.OUTPUT_REJECTED
    except Exception:
        log.exception("interior_generation_store_failed", generation_id=str(generation.id))
        error = GenerationError.STORAGE_FAILED
    await ops.finish(
        deps.sm,
        generation.id,
        GenerationState.failed if error else GenerationState.succeeded,
        error=error,
        cost_usd=cost,
        cost_estimated=estimated,
        output_media_id=media_id,
    )
    log.info("interior_generation_done", ok=error is None, cost_usd=str(cost), legal_tags=LEGAL_TAGS)


async def reconcile(sm: async_sessionmaker[AsyncSession], recovery: "Recovery") -> int:
    """Close operations a dead worker left behind. Returns how many were closed."""
    closed = 0
    async with sm() as db:
        stuck = (
            await db.scalars(
                select(InteriorGeneration).where(
                    InteriorGeneration.state.in_(("queued", "running")),
                    InteriorGeneration.deadline_at < func.clock_timestamp(),
                )
            )
        ).all()
        rows = [
            (g.id, g.state, g.reservation_id, g.request_sent_at is not None, g.estimate_usd, g.model)
            for g in stuck
        ]
    for gid, state, reservation, sent, estimate, model in rows:
        if reservation is not None:
            if sent:
                await recovery.settle(reservation, estimate, model)  # spend unknown: stay charged
            else:
                await recovery.release(reservation)
        async with sm() as db, db.begin():
            done = await db.scalar(
                update(InteriorGeneration)
                .where(InteriorGeneration.id == gid, InteriorGeneration.state.in_(("queued", "running")))
                .values(
                    state="failed",
                    error_code=GenerationError.TIMEOUT.value,
                    finished_at=func.clock_timestamp(),
                    cost_usd=estimate if sent else None,
                    cost_estimated=sent,
                )
                .returning(InteriorGeneration.id)
            )
        closed += 1 if done is not None else 0
        log.error("interior_generation_recovered", generation_id=str(gid), was=state, sent=sent)
    return closed


class Recovery(Protocol):
    async def settle(self, reservation_id: UUID, estimate: Decimal, model: str) -> None: ...

    async def release(self, reservation_id: UUID) -> None: ...
