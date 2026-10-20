"""Otodom rental corpus contracts: catalogue, immutable offers, run state, coverage (RM-377, OTO-01).

LEGAL[scraping]: models the results of fetching Otodom search pages; no fetching happens here (RM-377).
LEGAL[third-party-data]: offers hold original Otodom asking rents; nothing here re-publishes them (RM-377).
GDPR[personal-data]: offers hold only whitelisted analytical fields (id, location, rent, area, rooms,
timestamps). Seller names, phones, descriptions and raw payloads are never part of these models (RM-377);
there is no personal-data column, so retention is the 90-day cohort policy and erasure is not per person.

Invariant 2: every offer here is an *asking* rent (`PriceBasis.asking`); there is no deed variant, so a
deed price cannot be stored through these types.

Pure logic only (validation, dates, state transitions, the repository interface). Persistence is
`rm_core` (a later slice, with the migration); tests use the in-memory fake in `tests/market_corpus_fake.py`.
"""

import hashlib
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Protocol, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

ARCHIVE_DAYS = 90  # elapsed days, not calendar months (docs/OTODOM-NIGHTLY-IMPORT.md section 1)
EXPECTED_CATALOGUE_SIZE = (
    727  # owner-verified catalogue (B-023); a manifest is ready only when all are covered
)
LOCATION_PATH_RE = re.compile(r"[a-z0-9-]+(/[a-z0-9-]+){0,3}")  # same shape the Otodom client accepts
DISTRICT_ID_RE = re.compile(r"[a-z0-9-]+(/[a-z0-9-]+){1,7}")  # a place path plus the district segment
SOURCE_ID_RE = re.compile(r"[0-9]{1,20}")  # Otodom search ids are numeric (not the audit short id)
MAX_PAGES = 10_000  # sanity bound on a run's page counters, not a completeness cap


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_aware)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PriceBasis(StrEnum):
    asking = "asking"  # the only basis of this corpus (invariant 2)


class AgeBasis(StrEnum):
    publication = "publication"  # expires_at counted from a validated original publication time
    first_seen = "first_seen"  # fallback, recorded explicitly


class RunMode(StrEnum):
    bootstrap = "bootstrap"
    incremental = "incremental"
    recovery = "recovery"


class RunState(StrEnum):
    planned = "planned"
    running = "running"
    published = "published"  # complete, offers inserted, checkpoint advanced
    incomplete = "incomplete"  # ended without proven full coverage; prior checkpoint kept; resumable
    failed = "failed"  # terminal error; a new run is created


class SightingOutcome(StrEnum):
    inserted = "inserted"
    duplicate = "duplicate"  # same source id, same location: nothing changes
    location_conflict = "location_conflict"  # same source id, other location: first assignment kept, flagged


class DataStatus(StrEnum):
    unavailable = "unavailable"  # bootstrap pending
    fresh = "fresh"
    delayed = "delayed"
    stale = "stale"  # over the stale age or an unresolved coverage gap


FRESH_HOURS = 36
STALE_HOURS = 72


class LocationEntry(_Model):
    location_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")  # stable internal id
    name: str = Field(min_length=1, max_length=120)
    otodom_path: str = Field(min_length=1, max_length=160)  # verified domain path, unique in a catalogue
    launch_enabled: bool = True

    @model_validator(mode="after")
    def _path(self) -> Self:
        if not LOCATION_PATH_RE.fullmatch(self.otodom_path):
            raise ValueError("otodom_path is not a valid location path")
        return self


def catalogue_checksum(locations: Sequence[LocationEntry]) -> str:
    """SHA-256 over the sorted (id, path) pairs: the same catalogue always has the same checksum."""
    lines = sorted(f"{e.location_id}\t{e.otodom_path}\t{int(e.launch_enabled)}" for e in locations)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


class LocationCatalogue(_Model):
    """A versioned, immutable catalogue. A new version is a new object; an existing one never changes."""

    version: int = Field(ge=1)
    source_ref: str = Field(min_length=1, max_length=300)  # reference to the owner-verified artifact
    locations: tuple[LocationEntry, ...] = Field(min_length=1)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def build(cls, version: int, source_ref: str, locations: Sequence[LocationEntry]) -> Self:
        return cls(
            version=version,
            source_ref=source_ref,
            locations=tuple(locations),
            checksum=catalogue_checksum(locations),
        )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [e.location_id for e in self.locations]
        paths = [e.otodom_path for e in self.locations]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate location_id in catalogue")
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate otodom_path in catalogue")
        if self.checksum != catalogue_checksum(self.locations):
            raise ValueError("catalogue checksum does not match its locations")
        return self

    @property
    def complete(self) -> bool:
        return len(self.locations) == EXPECTED_CATALOGUE_SIZE


class OfferObservation(_Model):
    """One tile from a validated search page, reduced to whitelisted fields. Input of `record_offers`."""

    source_offer_id: str = Field(pattern=SOURCE_ID_RE.pattern)
    location_id: str = Field(min_length=1, max_length=64)
    asking_rent_pln: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )  # None: hidden
    area_m2: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    rooms: int | None = Field(default=None, ge=1, le=50)
    published_at: UtcDatetime | None = None  # validated original publication time, never `pushedUpAt`
    observed_at: UtcDatetime
    # The advert's district as the site names it (`locationLevel == "district"`), kept only when its id is a
    # child path of the searched place. Stored beside the offer, never in it (offers are immutable).
    district_id: str | None = Field(default=None, max_length=200, pattern=DISTRICT_ID_RE.pattern)
    district_name: str | None = Field(
        default=None, min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$"
    )

    @model_validator(mode="after")
    def _district_pair(self) -> Self:
        if (self.district_id is None) != (self.district_name is None):
            raise ValueError("a district needs both its id and its name")
        return self


class RentalOffer(_Model):
    """Immutable stored offer. Content never changes after insert; archival is derived from `expires_at`."""

    source: str = "otodom"
    price_basis: PriceBasis = PriceBasis.asking
    source_offer_id: str = Field(pattern=SOURCE_ID_RE.pattern)
    location_id: str = Field(min_length=1, max_length=64)
    asking_rent_pln: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    area_m2: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    rooms: int | None = Field(default=None, ge=1, le=50)
    published_at: UtcDatetime | None = None
    first_seen_at: UtcDatetime
    age_basis: AgeBasis
    expires_at: UtcDatetime
    source_date_issue: bool = False  # publication time was missing-or-rejected (future); fallback used
    run_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _age(self) -> Self:
        if self.price_basis is not PriceBasis.asking:
            raise ValueError("the rental corpus holds asking rents only")
        anchor = self.published_at if self.age_basis is AgeBasis.publication else self.first_seen_at
        if anchor is None or self.expires_at != anchor + timedelta(days=ARCHIVE_DAYS):
            raise ValueError("expires_at must be the age anchor plus 90 days")
        return self

    @property
    def priced(self) -> bool:
        return self.asking_rent_pln is not None and self.area_m2 is not None

    def archived(self, now: datetime) -> bool:
        """Derived at read time, so reads stay right if a job fails. Exactly at expiry: archived."""
        return _aware(now) >= self.expires_at


def offer_from_observation(obs: OfferObservation, run_id: str, now: datetime) -> RentalOffer:
    """Apply the age rules: a usable publication time anchors expiry; a missing or future one falls back to
    `first_seen_at` with `age_basis=first_seen`. A naive or arbitrary time is never substituted silently."""
    first_seen = _aware(now)
    pub = obs.published_at
    issue = False
    if pub is not None and pub > first_seen:
        pub, issue = None, True
    if pub is not None:
        basis, anchor = AgeBasis.publication, pub
    else:
        basis, anchor = AgeBasis.first_seen, first_seen
    return RentalOffer(
        source_offer_id=obs.source_offer_id,
        location_id=obs.location_id,
        asking_rent_pln=obs.asking_rent_pln,
        area_m2=obs.area_m2,
        rooms=obs.rooms,
        published_at=pub,
        first_seen_at=first_seen,
        age_basis=basis,
        expires_at=anchor + timedelta(days=ARCHIVE_DAYS),
        source_date_issue=issue,
        run_id=run_id,
    )


class SightingReport(_Model):
    """Counts for one `record_offers` call; kept in run metadata. Conflicts are listed for review."""

    inserted: int = 0
    duplicates: int = 0
    location_conflicts: tuple[str, ...] = ()  # source ids first assigned to another location
    unpriced: int = 0  # inserted offers without a usable price/area (identity only)


class ImportRun(_Model):
    run_id: str = Field(min_length=1, max_length=64)
    location_id: str
    mode: RunMode
    window_start: UtcDatetime  # frozen intended bounds of the covered source window
    window_end: UtcDatetime
    state: RunState = RunState.planned
    pages_expected: int | None = Field(default=None, ge=0, le=MAX_PAGES)
    pages_fetched: int = Field(default=0, ge=0, le=MAX_PAGES)  # checkpoint: resume from this page + 1
    truncated: bool = False  # a cap or short page: coverage not proven
    observed: int = Field(default=0, ge=0)  # distinct source ids seen, including duplicates and unpriced
    inserted: int = Field(default=0, ge=0)
    duplicates: int = Field(default=0, ge=0)
    location_conflicts: int = Field(default=0, ge=0)
    error_category: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.window_end < self.window_start:
            raise ValueError("window_end precedes window_start")
        return self

    @property
    def coverage_complete(self) -> bool:
        """Completion evidence. A valid empty search (one page, zero offers) is complete, not failed."""
        return (
            not self.truncated
            and self.pages_expected is not None
            and self.pages_fetched == self.pages_expected
        )


_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.planned: frozenset({RunState.running, RunState.failed}),
    RunState.running: frozenset({RunState.running, RunState.published, RunState.incomplete, RunState.failed}),
    RunState.incomplete: frozenset({RunState.running, RunState.failed}),
    RunState.published: frozenset(),
    RunState.failed: frozenset(),
}


class InvalidRunTransitionError(ValueError):
    """The requested run state change is not allowed (published and failed are terminal)."""


class CoverageNotProvenError(ValueError):
    """A run cannot be published without complete page coverage."""


def check_transition(current: RunState, new: RunState) -> None:
    if new not in _TRANSITIONS[current]:
        raise InvalidRunTransitionError(f"{current.value} -> {new.value}")


class LocationCheckpoint(_Model):
    """One per location and dataset: what is covered, when it last refreshed successfully."""

    location_id: str
    bootstrap_completed_at: UtcDatetime | None = None
    covered_until: UtcDatetime | None = None  # watermark of the proven-covered source window
    unresolved_gap_since: UtcDatetime | None = None  # set when a published window did not reach the watermark
    last_successful_refresh_at: UtcDatetime | None = None  # advances even when no offer was inserted
    last_published_run_id: str | None = None

    def data_status(self, now: datetime) -> DataStatus:
        if self.bootstrap_completed_at is None or self.last_successful_refresh_at is None:
            return DataStatus.unavailable
        age = _aware(now) - self.last_successful_refresh_at
        if self.unresolved_gap_since is not None or age > timedelta(hours=STALE_HOURS):
            return DataStatus.stale
        return DataStatus.delayed if age > timedelta(hours=FRESH_HOURS) else DataStatus.fresh


def advance_checkpoint(cp: LocationCheckpoint, run: ImportRun, now: datetime) -> LocationCheckpoint:
    """The checkpoint after `run` was published at `now` (pure; both repositories use it)."""
    update: dict[str, object] = {
        "last_successful_refresh_at": _aware(now),
        "last_published_run_id": run.run_id,
    }
    if run.mode is RunMode.bootstrap:
        update["bootstrap_completed_at"] = _aware(now)
        update["covered_until"] = run.window_end
        update["unresolved_gap_since"] = None
    elif cp.covered_until is not None and run.window_start > cp.covered_until:
        # The window does not reach the watermark: keep it, make the gap visible.
        update["unresolved_gap_since"] = cp.unresolved_gap_since or cp.covered_until
    else:
        update["covered_until"] = max(cp.covered_until or run.window_end, run.window_end)
        update["unresolved_gap_since"] = None
    return LocationCheckpoint.model_validate(cp.model_copy(update=update).model_dump())


class BootstrapManifest(_Model):
    """Readiness: every catalogue location counts, enabled or not; disabled ones are uncovered."""

    catalogue_version: int
    total: int
    bootstrapped: int
    pending: tuple[str, ...]  # location ids without a completed bootstrap
    gaps: tuple[str, ...]  # location ids with an unresolved coverage gap
    zero_offer_locations: tuple[str, ...]  # bootstrapped with no offers: visible, not failed
    catalogue_complete: bool  # the catalogue itself has all 727 entries

    @property
    def ready(self) -> bool:
        return self.catalogue_complete and not self.pending and not self.gaps


class UnknownLocationError(LookupError):
    """The location is not in the catalogue (404 at the API level)."""


class CatalogueConflictError(ValueError):
    """A catalogue version already exists with different content; versions are immutable."""


class CorpusRepository(Protocol):
    """Interface of the corpus store. Every method is idempotent on its key and race-safe: the Postgres
    implementation uses INSERT ... ON CONFLICT DO NOTHING and row locks, no transaction held across I/O."""

    async def ensure_catalogue(self, catalogue: LocationCatalogue) -> LocationCatalogue:
        """Insert the version, or return the stored one when identical; differing content raises
        `CatalogueConflictError`."""
        ...

    async def get_catalogue(self, version: int) -> LocationCatalogue | None: ...

    async def start_run(self, run: ImportRun) -> ImportRun:
        """Create the run (state planned); an existing `run_id` returns the stored run unchanged."""
        ...

    async def save_progress(
        self, run_id: str, *, pages_fetched: int, pages_expected: int | None, truncated: bool = False
    ) -> ImportRun:
        """Persist the page checkpoint and move the run to running. Never moves backwards."""
        ...

    async def record_offers(
        self, run_id: str, observations: Sequence[OfferObservation], now: datetime
    ) -> SightingReport:
        """Insert unknown offers; never update an existing one. Retry-safe."""
        ...

    async def record_districts(
        self, location_id: str, observations: Sequence[OfferObservation], now: datetime
    ) -> int:
        """Attach each observation's district to the offer already stored for this place; nothing else is
        written and an offer never changes. Offers the corpus does not hold, or holds for another place,
        are skipped. Returns the number of new attachments. Retry-safe."""
        ...

    async def district_counts(self, location_id: str) -> dict[str, tuple[str, int]]:
        """`district_id -> (name, offers carrying it)` for the place."""
        ...

    async def finish_run(
        self, run_id: str, *, state: RunState, now: datetime, error_category: str | None = None
    ) -> ImportRun:
        """`published` requires proven coverage (`CoverageNotProvenError` otherwise) and, in one step,
        advances the location checkpoint. `incomplete` and `failed` leave the checkpoint untouched."""
        ...

    async def get_run(self, run_id: str) -> ImportRun | None: ...

    async def get_checkpoint(self, location_id: str) -> LocationCheckpoint | None: ...

    async def list_offers(
        self, location_id: str, *, after_source_id: str | None = None, limit: int = 1000
    ) -> list[RentalOffer]:
        """Keyset page ordered by numeric source id."""
        ...

    async def manifest(self, catalogue_version: int) -> BootstrapManifest: ...
