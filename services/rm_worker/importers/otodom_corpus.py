"""Otodom rental corpus importer: bootstrap, nightly new-offer windows and catch-up (RM-392, OTO-02/03).

LEGAL[scraping]: pages through Otodom search results with browser TLS impersonation via the shared 1 req/s
host slot and circuit breaker, at `batch` priority; `LEGAL_SCRAPING_ENABLED=false` stops it (the gated
source). ToS and EU database-right exposure are with counsel (RM-392).
LEGAL[third-party-data]: keeps whitelisted analytical fields of third-party adverts (id, asking rent, area,
rooms, creation time); no seller, title, description, phone or photo reaches the database (RM-392).
Invariant 2: every stored rent is an asking rent. Invariant 3: only `totalPrice` is read; `rentPrice` is the
admin fee (czynsz) and is never income.

What it guarantees, and what it does not:
- insert-once: an offer is recorded when first seen and never refreshed; no listing page is visited;
- coverage is claimed only when every page of every disjoint created-date partition was read
  (`pages_fetched == pages_expected`, not truncated); a window over the page cap is bisected by creation time
  and a partition that cannot be split any further makes the run `incomplete`, never silently shorter;
- a valid empty search is a complete, published run; a malformed, cut-off or blocked one is `incomplete`;
- bounds are frozen and hour-aligned, so a retry in the same hour asks the same question; the next window
  starts at `covered_until - OVERLAP`, so a missed night is caught by a wider window, not by a gap;
- "active stock" and "achieved rent" are never claimed: the corpus is what was advertised when first seen.
Progress is durable per page (offers and counters), but a restarted window re-reads its pages from the start
(RM-392-L02). The date-filter parameter names are unverified (L-050): the live client refuses them until an
owner-authorised check flips `filters_verified`.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast

import structlog
from deal_analyzer.rent import PPM2_RANGE
from rm_contracts.market import (
    CorpusRepository,
    CoverageNotProvenError,
    ImportRun,
    LocationCatalogue,
    LocationEntry,
    OfferObservation,
    RunMode,
    RunState,
)
from rm_core.deadline import Deadline
from rm_core.legal import LegalTag, tag_names
from rm_core.settings import Settings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from rm_worker.clients.otodom import (
    MAX_SEARCH_PAGE,
    FetchError,
    FilterContractUnverified,
    Priority,
    SearchOptions,
    UpstreamBlocked,
    UpstreamSchemaDrift,
)
from rm_worker.importers.otodom_rental import AREA_RANGE, MAX_ITEMS_PER_PAGE, RENT_RANGE

log = structlog.get_logger(__name__)

EPOCH = datetime(2010, 1, 1, tzinfo=UTC)  # lower bound of a bootstrap window (nothing older is claimed)
PAGE_CAP = MAX_SEARCH_PAGE  # the client refuses deeper pages; a bigger result is partitioned, not cut
MIN_PARTITION = timedelta(hours=1)  # a window this narrow that still exceeds the cap is truncated coverage
OVERLAP = timedelta(minutes=60)  # default recovery margin; OTODOM_MARKET_OVERLAP_MINUTES in production
CHUNK = timedelta(days=7)  # widest window of one catch-up run; longer gaps chain several runs
DUE_AFTER = timedelta(hours=23)  # a bootstrapped location is due when the watermark is this old
RUN_PAGE_BUDGET = 3000  # default pages per run; OTODOM_MARKET_REQUEST_BUDGET in production
RUN_DEADLINE_S = 3600.0  # one run's total deadline; each request has its own cap in the client
MAX_RUNS_PER_CALL = 8  # catch-up runs for one location in one call
NIGHT_WINDOW_END_UTC = time(5)  # default OTODOM_MARKET_NIGHT_WINDOW_END_UTC
NIGHT_WINDOW_REOPEN_UTC = time(12)  # normal fetches are closed from the window end until this time
CATALOGUE_VERSION = 1  # default OTODOM_MARKET_CATALOGUE_VERSION; the scheduled jobs read the setting
CREATED_AT_FIELD = "createdAtFirst"  # never `pushedUpAt`; semantics unverified (RM-392-L03)


def in_night_window(now: datetime, window_end: time = NIGHT_WINDOW_END_UTC) -> bool:
    """True when normal Otodom fetches must stop: from the window end until 12:00 UTC. Work left over is
    kept resumable, so a closed window delays a location and never completes or skips it (RM-209)."""
    return window_end <= now.astimezone(UTC).time() < NIGHT_WINDOW_REOPEN_UTC


_TAGS = tag_names(LegalTag.scraping, LegalTag.third_party_data)


class CorpusSearchSource(Protocol):
    async def fetch_corpus_search(
        self,
        location_id: str,
        page: int,
        *,
        options: SearchOptions,
        deadline: Deadline,
        priority: Priority = "batch",
    ) -> dict[str, Any]: ...


class LocationLock(Protocol):
    def hold(self, location_id: str) -> AbstractAsyncContextManager[bool]:
        """Yields True when this caller owns the location, False when another run holds it."""
        ...


class PageShapeError(ValueError):
    """A results page lacks a valid `items` list or `pagination.totalPages`: coverage cannot be proven."""


class PgLocationLock:
    """Session-level Postgres advisory lock per location on a dedicated autocommit connection. Released by
    Postgres if the holder dies. Holding a connection (not a transaction) is the cost; pool_size >= 2."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def hold(self, location_id: str) -> AsyncGenerator[bool]:
        key = func.hashtext(f"otodom_corpus:{location_id}")
        conn = await self._engine.connect()
        try:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            got = bool(await conn.scalar(select(func.pg_try_advisory_lock(key))))
            try:
                yield got
            finally:
                if got:
                    await conn.scalar(select(func.pg_advisory_unlock(key)))
        finally:
            await conn.close()


# --- parsing -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedPage:
    observations: tuple[OfferObservation, ...]
    total_pages: int
    rejected: int  # tiles that are not flat-for-rent offers with a numeric id (recommendations, malformed)


def _obj(value: object) -> dict[str, Any] | None:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _stored_decimal(number: Decimal | None, low_high: tuple[Decimal, Decimal]) -> Decimal | None:
    """In range and storable as NUMERIC with 2 places; otherwise absent (an offer is insert-once, so a
    doubtful value is left out rather than stored wrongly)."""
    if number is None or not low_high[0] <= number <= low_high[1]:
        return None
    exponent = number.as_tuple().exponent
    return number if isinstance(exponent, int) and exponent >= -2 else None


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None  # a naive time is not guessed


def parse_search_page(search_ads: dict[str, Any], *, location_id: str, observed_at: datetime) -> ParsedPage:
    raw_items: object = search_ads.get("items")
    total: object = (_obj(search_ads.get("pagination")) or {}).get("totalPages")
    if not isinstance(raw_items, list) or isinstance(total, bool) or not isinstance(total, int):
        raise PageShapeError("results page has no items list or pagination.totalPages")
    if not 1 <= total <= 10_000:
        raise PageShapeError("pagination.totalPages is out of range")
    found: list[OfferObservation] = []
    rejected = 0
    for raw in cast("list[object]", raw_items)[:MAX_ITEMS_PER_PAGE]:
        item = _obj(raw)
        offer_id = item.get("id") if item else None
        if (
            item is None
            or isinstance(offer_id, bool)
            or not isinstance(offer_id, int)
            or offer_id <= 0
            or item.get("estate") != "FLAT"
            or item.get("transaction") != "RENT"
        ):
            rejected += 1
            continue
        price = _obj(item.get("totalPrice"))  # NOT rentPrice: that is the admin fee (invariant 3)
        rent: Decimal | None = None
        if price is not None and price.get("currency") == "PLN" and not item.get("hidePrice"):
            rent = _stored_decimal(_decimal(price.get("value")), RENT_RANGE)
        area = _stored_decimal(_decimal(item.get("areaInSquareMeters")), AREA_RANGE)
        if rent is not None and area is not None and not PPM2_RANGE[0] <= rent / area <= PPM2_RANGE[1]:
            rent = area = None
        rooms = item.get("roomsNumber")
        found.append(
            OfferObservation(
                source_offer_id=str(offer_id),
                location_id=location_id,
                asking_rent_pln=rent,
                area_m2=area,
                rooms=rooms
                if isinstance(rooms, int) and not isinstance(rooms, bool) and 1 <= rooms <= 50
                else None,
                published_at=_published_at(item.get(CREATED_AT_FIELD)),
                observed_at=observed_at,
            )
        )
    return ParsedPage(tuple(found), total, rejected)


# --- one run -----------------------------------------------------------------------------------------


@dataclass
class _Sweep:
    """Counters of one run; `expected` grows as partitions reveal their page counts."""

    fetched: int = 0
    expected: int = 0
    truncated: bool = False
    inserted: int = 0
    duplicates: int = 0
    conflicts: int = 0
    rejected: int = 0


@dataclass(frozen=True)
class _Ctx:
    entry: LocationEntry
    run_id: str
    sweep: _Sweep
    deadline: Deadline


@dataclass(frozen=True)
class RunOutcome:
    location_id: str
    mode: RunMode
    run_id: str | None
    state: str  # published | incomplete | failed | busy | not_due | already_published | unknown
    error_category: str | None = None
    inserted: int = 0
    pages: int = 0
    window_end: datetime | None = None
    blocked: bool = False  # upstream refused: the caller stops hammering the host


@dataclass
class CorpusImporter:
    corpus: CorpusRepository
    source: CorpusSearchSource
    lock: LocationLock | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    page_cap: int = PAGE_CAP
    page_budget: int = RUN_PAGE_BUDGET
    run_deadline_s: float = RUN_DEADLINE_S
    overlap: timedelta = OVERLAP
    night_window_end: time = NIGHT_WINDOW_END_UTC
    # Checked before every page request; False ends the run `incomplete` (category `night_window`) and keeps
    # its checkpoint. The production factory checks the real time; tests inject their own.
    may_fetch: Callable[[], bool] = field(default=lambda: True)

    @property
    def normal_window(self) -> timedelta:
        """Wider than this is mode `recovery` (one daily window plus overlap and one hour of slack)."""
        return timedelta(hours=24) + self.overlap + timedelta(hours=1)

    def night_window_closed(self, now: datetime | None = None) -> bool:
        return in_night_window(now or self.clock(), self.night_window_end)

    # -- planning -----------------------------------------------------------------------------------

    def target(self, now: datetime | None = None) -> datetime:
        """Frozen, hour-aligned upper bound, so a retry in the same hour asks the same question."""
        return (now or self.clock()).astimezone(UTC).replace(minute=0, second=0, microsecond=0)

    async def is_due(self, location_id: str, now: datetime | None = None) -> bool:
        cp = await self.corpus.get_checkpoint(location_id)
        if cp is None or cp.bootstrap_completed_at is None or cp.covered_until is None:
            return True  # needs its bootstrap
        return self.target(now) - cp.covered_until >= DUE_AFTER

    async def due_locations(self, catalogue: LocationCatalogue, now: datetime | None = None) -> list[str]:
        return [
            e.location_id
            for e in catalogue.locations
            if e.launch_enabled and await self.is_due(e.location_id, now)
        ]

    # -- one location -------------------------------------------------------------------------------

    async def sync_location(self, entry: LocationEntry, *, now: datetime | None = None) -> list[RunOutcome]:
        """Bootstrap the location if it never was, otherwise catch up to the target in bounded runs."""
        if self.lock is None:
            return await self._sync(entry, now)
        async with self.lock.hold(entry.location_id) as owned:
            if not owned:
                return [RunOutcome(entry.location_id, RunMode.incremental, None, "busy")]
            return await self._sync(entry, now)

    async def _sync(self, entry: LocationEntry, now: datetime | None) -> list[RunOutcome]:
        end = self.target(now)
        cp = await self.corpus.get_checkpoint(entry.location_id)
        if cp is None or cp.bootstrap_completed_at is None or cp.covered_until is None:
            return [await self._run(entry, RunMode.bootstrap, EPOCH, end)]
        outcomes: list[RunOutcome] = []
        for _ in range(MAX_RUNS_PER_CALL):
            if cp.covered_until is None:
                break
            if not outcomes and end - cp.covered_until < DUE_AFTER:
                return [RunOutcome(entry.location_id, RunMode.incremental, None, "not_due")]
            if end <= cp.covered_until:
                break
            start = cp.covered_until - self.overlap
            window_end = min(end, start + CHUNK)
            mode = RunMode.incremental if window_end - start <= self.normal_window else RunMode.recovery
            outcome = await self._run(entry, mode, start, window_end)
            outcomes.append(outcome)
            if outcome.state not in ("published", "already_published"):
                break
            fresh = await self.corpus.get_checkpoint(entry.location_id)
            if fresh is None or fresh.covered_until is None or fresh.covered_until <= cp.covered_until:
                break
            cp = fresh
        return outcomes

    async def _run(self, entry: LocationEntry, mode: RunMode, start: datetime, end: datetime) -> RunOutcome:
        loc = entry.location_id
        base = f"{mode.value}-{loc}-{end:%Y%m%dT%H%M%SZ}"
        attempt = 1
        while (existing := await self.corpus.get_run(f"{base}-a{attempt}")) is not None:
            if existing.state is RunState.published:
                return RunOutcome(loc, mode, existing.run_id, "already_published", window_end=end)
            if existing.state is RunState.planned:  # dead before its first page: close it
                await self.corpus.finish_run(
                    existing.run_id, state=RunState.failed, now=self.clock(), error_category="abandoned"
                )
            attempt += (
                1  # a running/incomplete/failed attempt is superseded by a fresh one on the same window
            )
        run = await self.corpus.start_run(
            ImportRun(
                run_id=f"{base}-a{attempt}", location_id=loc, mode=mode, window_start=start, window_end=end
            )
        )
        bound = log.bind(location_id=loc, run_id=run.run_id, mode=mode.value, legal_tags=_TAGS)
        sweep = _Sweep()
        deadline = Deadline.after(self.run_deadline_s)
        await self.corpus.save_progress(
            run.run_id, pages_fetched=0, pages_expected=None
        )  # planned -> running
        try:
            window_from = None if mode is RunMode.bootstrap else start
            await self._partition(_Ctx(entry, run.run_id, sweep, deadline), window_from, end)
            await self.corpus.save_progress(
                run.run_id,
                pages_fetched=sweep.fetched,
                pages_expected=sweep.expected,
                truncated=sweep.truncated,
            )
            try:
                done = await self.corpus.finish_run(run.run_id, state=RunState.published, now=self.clock())
            except CoverageNotProvenError:
                done = await self.corpus.finish_run(
                    run.run_id,
                    state=RunState.incomplete,
                    now=self.clock(),
                    error_category="coverage_not_proven",
                )
            bound.info(
                "corpus_run_finished", state=done.state.value, pages=sweep.fetched, inserted=sweep.inserted
            )
            return RunOutcome(
                loc,
                mode,
                run.run_id,
                done.state.value,
                done.error_category,
                sweep.inserted,
                sweep.fetched,
                end,
            )
        except asyncio.CancelledError:
            await asyncio.shield(self._close(run.run_id, "cancelled"))
            raise
        except (FetchError, PageShapeError, TimeoutError, _RunStopped) as exc:
            category = _category(exc)
            blocked = isinstance(exc, UpstreamBlocked) and not exc.retryable
            await self._close(run.run_id, category)
            bound.warning("corpus_run_incomplete", category=category, pages=sweep.fetched)
            return RunOutcome(
                loc, mode, run.run_id, "incomplete", category, sweep.inserted, sweep.fetched, end, blocked
            )

    async def _close(self, run_id: str, category: str) -> None:
        await self.corpus.finish_run(
            run_id, state=RunState.incomplete, now=self.clock(), error_category=category
        )

    # -- partitioned paging -------------------------------------------------------------------------

    async def _partition(self, ctx: _Ctx, lo: datetime | None, hi: datetime) -> None:
        """Read every page of [lo, hi]; if the result is deeper than the cap, split the window by creation
        time and read the halves. Boundary instants may be seen twice: inserts are idempotent."""
        sweep, options = ctx.sweep, SearchOptions(lo, hi)
        total = await self._page(ctx, options, 1)
        if total > self.page_cap:
            floor = lo or EPOCH
            if hi - floor <= MIN_PARTITION:
                sweep.truncated = True  # cannot split further: read what the cap allows, claim nothing more
                total = self.page_cap
            else:
                sweep.expected += 1
                mid = (floor + (hi - floor) / 2).replace(microsecond=0)
                await self._partition(ctx, lo, mid)
                await self._partition(ctx, mid, hi)
                return
        sweep.expected += total
        planned = total
        page = 2
        while page <= planned:
            seen_total = await self._page(ctx, options, page)
            if seen_total > planned:
                sweep.truncated = True  # the result grew under a frozen bound: do not claim full coverage
            if seen_total < planned:
                sweep.expected -= planned - seen_total  # offers vanished meanwhile: fewer pages exist now
                planned = seen_total
            page += 1

    async def _page(self, ctx: _Ctx, options: SearchOptions, page: int) -> int:
        sweep, entry = ctx.sweep, ctx.entry
        if sweep.fetched >= self.page_budget:
            raise _BudgetExceededError
        if ctx.deadline.expired:
            raise TimeoutError("run deadline reached")
        if not self.may_fetch():
            raise _NightWindowClosedError
        now = self.clock()
        ads = await self.source.fetch_corpus_search(
            entry.otodom_path, page, options=options, deadline=ctx.deadline, priority="batch"
        )
        parsed = parse_search_page(ads, location_id=entry.location_id, observed_at=now)
        report = await self.corpus.record_offers(ctx.run_id, parsed.observations, now)
        sweep.fetched += 1
        sweep.inserted += report.inserted
        sweep.duplicates += report.duplicates
        sweep.conflicts += len(report.location_conflicts)
        sweep.rejected += parsed.rejected
        await self.corpus.save_progress(
            ctx.run_id,
            pages_fetched=sweep.fetched,
            pages_expected=max(sweep.expected, sweep.fetched),
            truncated=sweep.truncated,
        )
        return parsed.total_pages


class _RunStopped(RuntimeError):
    """A policy stop, not a provider failure: the run ends `incomplete` with its category and keeps its
    checkpoint, so the next attempt starts the same window again."""

    category: str = "stopped"


class _BudgetExceededError(_RunStopped):
    """The run reached its page budget."""

    category = "budget"


class _NightWindowClosedError(_RunStopped):
    """The night window closed mid-run; the run resumes from the same window later."""

    category = "night_window"


def _category(exc: BaseException) -> str:
    if isinstance(exc, _RunStopped):
        return exc.category
    if isinstance(exc, FilterContractUnverified):
        return "filter_unverified"
    if isinstance(exc, UpstreamBlocked):
        return "upstream_blocked"
    if isinstance(exc, UpstreamSchemaDrift | PageShapeError):
        return "schema_drift"
    if isinstance(exc, TimeoutError):
        return "deadline"
    return "fetch_error"


# --- the whole catalogue -----------------------------------------------------------------------------


@dataclass(frozen=True)
class NightlyResult:
    outcomes: tuple[RunOutcome, ...]
    stopped: str | None  # None | "blocked" | "night_window"


async def run_nightly(
    importer: CorpusImporter, catalogue: LocationCatalogue, *, now: datetime | None = None
) -> NightlyResult:
    """Sequentially sync every enabled, due location. Stops at the first upstream refusal (never hammers a
    blocked host) and at the end of the night window; the remaining locations stay overdue and resumable."""
    outcomes: list[RunOutcome] = []
    for entry in catalogue.locations:
        if outcomes and importer.night_window_closed(now):
            return NightlyResult(tuple(outcomes), "night_window")
        if not entry.launch_enabled or not await importer.is_due(entry.location_id, now):
            continue
        done = await importer.sync_location(entry, now=now)
        outcomes.extend(done)
        if any(o.blocked for o in done):
            return NightlyResult(tuple(outcomes), "blocked")
    return NightlyResult(tuple(outcomes), None)


def importer_from_settings(
    corpus: CorpusRepository,
    source: CorpusSearchSource,
    settings: Settings,
    *,
    lock: LocationLock | None = None,
    may_fetch: Callable[[], bool] | None = None,
) -> CorpusImporter:
    """The only way production builds the importer: the configured overlap, request budget and night window
    (`OTODOM_MARKET_*`) apply, and the window is checked against the real time before each page request."""
    window_end = settings.night_window_end_time
    return CorpusImporter(
        corpus,
        source,
        lock=lock,
        page_budget=settings.otodom_market_request_budget,
        overlap=timedelta(minutes=settings.otodom_market_overlap_minutes),
        night_window_end=window_end,
        may_fetch=may_fetch or (lambda: not in_night_window(datetime.now(UTC), window_end)),
    )
