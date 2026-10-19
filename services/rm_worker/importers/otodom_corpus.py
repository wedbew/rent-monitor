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
- coverage is claimed only when the sweep provably reached both ends of its window (an advert older than the
  window start, or every page of a list that fits the cap) and was not truncated; a window deeper than the
  page cap is read newest-first and oldest-first and the middle is walked with `daysSinceCreated`, and a
  stretch that still cannot be read makes the run `incomplete`, never silently shorter;
- a valid empty search is a complete, published run; a malformed, cut-off or blocked one is `incomplete`;
- bounds are frozen and hour-aligned, so a retry in the same hour asks the same question; the next window
  starts at `covered_until - OVERLAP`, so a missed night is caught by a wider window, not by a gap;
- "active stock" and "achieved rent" are never claimed: the corpus is what was advertised when first seen.
Progress is durable per page (offers and counters), but a restarted window re-reads its pages from the start
(RM-392-L02). The search contract was verified against the live site on 2026-10-20 (RM-411, L-050):
`daysSinceCreated=N` is a rolling N x 24 h window without an upper bound, `by=LATEST&direction=ASC|DESC`
sorts by `createdAtFirst`, and a page past the end repeats the last page (so `currentPage` is checked).
"""

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from math import ceil
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
    MAX_DAYS_SINCE_CREATED,
    MAX_SEARCH_PAGE,
    FetchError,
    Priority,
    SearchOptions,
    UpstreamBlocked,
    UpstreamSchemaDrift,
)
from rm_worker.importers.otodom_rental import AREA_RANGE, MAX_ITEMS_PER_PAGE, RENT_RANGE

log = structlog.get_logger(__name__)

EPOCH = datetime(2010, 1, 1, tzinfo=UTC)  # lower bound of a bootstrap window (nothing older is claimed)
PROMOTED_HREF_PREFIX = "hpr/"  # a sponsored tile repeated on every page with a synthetic id and a 1999 date
PAGE_CAP = MAX_SEARCH_PAGE  # the client refuses deeper pages; a bigger result is partitioned, not cut
DAY = timedelta(days=1)
MAX_GAP_STEPS = 400  # oldest-first steps over the middle of one huge location before it is called truncated
OVERLAP = timedelta(minutes=60)  # default recovery margin; OTODOM_MARKET_OVERLAP_MINUTES in production
DUE_AFTER = timedelta(hours=23)  # a bootstrapped location is due when the watermark is this old
RUN_PAGE_BUDGET = 3000  # default pages per run; OTODOM_MARKET_REQUEST_BUDGET in production
RUN_DEADLINE_S = 3600.0  # one run's total deadline; each request has its own cap in the client
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
    total_pages: int  # 0 is a valid empty search
    rejected: int  # tiles that are not flat-for-rent offers with a numeric id (recommendations, sponsored)
    created_min: datetime | None = None  # oldest and newest `createdAtFirst` of the accepted tiles
    created_max: datetime | None = None


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


def parse_search_page(
    search_ads: dict[str, Any], *, location_id: str, observed_at: datetime, page: int = 1
) -> ParsedPage:
    raw_items: object = search_ads.get("items")
    pagination = _obj(search_ads.get("pagination")) or {}
    total: object = pagination.get("totalPages")
    current: object = pagination.get("currentPage")
    if not isinstance(raw_items, list) or isinstance(total, bool) or not isinstance(total, int):
        raise PageShapeError("results page has no items list or pagination.totalPages")
    if not 0 <= total <= 10_000:
        raise PageShapeError("pagination.totalPages is out of range")
    if isinstance(current, int) and not isinstance(current, bool) and total > 0 and current != page:
        raise PageShapeError("the site answered another page than requested")  # past-the-end repeats the last
    found: list[OfferObservation] = []
    rejected = 0
    for raw in cast("list[object]", raw_items)[:MAX_ITEMS_PER_PAGE]:
        item = _obj(raw)
        offer_id = item.get("id") if item else None
        href = item.get("href") if item else None
        if (
            item is None
            or isinstance(offer_id, bool)
            or not isinstance(offer_id, int)
            or offer_id <= 0
            or item.get("estate") != "FLAT"
            or item.get("transaction") != "RENT"
            or (isinstance(href, str) and href.startswith(PROMOTED_HREF_PREFIX))
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
    dated = [o.published_at for o in found if o.published_at is not None]
    return ParsedPage(tuple(found), total, rejected, min(dated, default=None), max(dated, default=None))


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
        """One run per call: the bootstrap, or one window from just before the watermark to the target.
        The site filters only by "created in the last N days", so a long gap is one wider window (read
        newest-first until an advert older than its start), never a chain of bounded chunks."""
        end = self.target(now)
        cp = await self.corpus.get_checkpoint(entry.location_id)
        if cp is None or cp.bootstrap_completed_at is None or cp.covered_until is None:
            return [await self._run(entry, RunMode.bootstrap, EPOCH, end, now)]
        if end - cp.covered_until < DUE_AFTER:
            return [RunOutcome(entry.location_id, RunMode.incremental, None, "not_due")]
        if end <= cp.covered_until:
            return []
        start = cp.covered_until - self.overlap
        mode = RunMode.incremental if end - start <= self.normal_window else RunMode.recovery
        return [await self._run(entry, mode, start, end, now)]

    async def _run(
        self, entry: LocationEntry, mode: RunMode, start: datetime, end: datetime, now: datetime | None
    ) -> RunOutcome:
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
            await self._cover(_Ctx(entry, run.run_id, sweep, deadline), window_from, end, now or self.clock())
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

    # -- covering a window ----------------------------------------------------------------------------

    async def _cover(self, ctx: _Ctx, lo: datetime | None, hi: datetime, now: datetime) -> None:
        """Read every advert created in [lo, hi] (lo None: everything). The site offers no absolute date
        filter, so the window is proven from the adverts' own `createdAtFirst`:

        1. newest-first, limited to the last N days when `lo` is given; done when every page was read or an
           advert older than `lo` appeared (all newer ones were passed);
        2. if the cap stopped it, oldest-first the same way, done when it met the newest-first range;
        3. otherwise walk the middle oldest-first, each step restarting at the oldest uncovered age;
           a step that cannot advance (more than a cap of adverts in one day) is truncated coverage.
        The two ranges meet only when the oldest-first edge is strictly newer than the newest-first edge:
        equal timestamps could hide unread adverts at the cut of a page.
        Boundary adverts may be read twice: inserts are idempotent. `hi` is not an upper filter: a few adverts
        newer than it are stored too, which is harmless. `now` is the run's start."""
        days = None if lo is None else self._days_back(now, lo)
        newest = await self._pass(ctx, SearchOptions(days, "newest"), stop_older_than=lo)
        if newest.done:
            return
        gap_end = newest.edge  # oldest created time read newest-first: everything newer is covered
        if gap_end is None:  # the cap stopped a list whose adverts carry no usable creation time
            ctx.sweep.truncated = True
            return
        oldest = await self._pass(ctx, SearchOptions(days, "oldest"), stop_newer_than=gap_end)
        steps = 0
        while not oldest.done:
            edge = oldest.edge
            if edge is None or steps >= MAX_GAP_STEPS:
                ctx.sweep.truncated = True
                return
            steps += 1
            step = await self._pass(
                ctx, SearchOptions(self._days_back(now, edge), "oldest"), stop_newer_than=gap_end
            )
            if not step.done and (step.edge is None or step.edge <= edge):
                ctx.sweep.truncated = True  # cannot advance (over a cap of adverts in a day)
                return
            oldest = step

    @staticmethod
    def _days_back(reference: datetime, since: datetime) -> int:
        """`daysSinceCreated` that reaches `since`, measured from the run's start time with one day of margin:
        the site counts from its own clock, which is at most the run's duration ahead of it."""
        return max(1, min(MAX_DAYS_SINCE_CREATED, ceil((reference - since) / DAY) + 1))

    async def _pass(
        self,
        ctx: _Ctx,
        options: SearchOptions,
        *,
        stop_older_than: datetime | None = None,
        stop_newer_than: datetime | None = None,
    ) -> "_Pass":
        """Read one ordered list from page 1. `edge` is the last created time it reached (the oldest when
        newest-first, the newest when oldest-first). `done` means the list ended or reached its stop bound."""
        sweep = ctx.sweep
        newest_first = options.order == "newest"
        edge: datetime | None = None
        page, planned, listed = 1, 1, 0
        while page <= planned:
            parsed = await self._page(ctx, options, page)
            if page == 1:
                listed = parsed.total_pages
                planned = min(parsed.total_pages, self.page_cap)
                sweep.expected += max(planned, 1)
                if parsed.total_pages == 0:
                    return _Pass(done=True, edge=None)  # a valid empty search is complete
            reached = parsed.created_min if newest_first else parsed.created_max
            if reached is not None:
                edge = (
                    reached if edge is None else (min(edge, reached) if newest_first else max(edge, reached))
                )
            if stop_older_than is not None and newest_first and edge is not None and edge < stop_older_than:
                sweep.expected -= planned - page
                return _Pass(done=True, edge=edge)
            if (
                stop_newer_than is not None
                and not newest_first
                and edge is not None
                and edge > stop_newer_than
            ):
                sweep.expected -= planned - page
                return _Pass(done=True, edge=edge)
            page += 1
        return _Pass(done=listed <= self.page_cap, edge=edge)

    async def _page(self, ctx: _Ctx, options: SearchOptions, page: int) -> ParsedPage:
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
        parsed = parse_search_page(ads, location_id=entry.location_id, observed_at=now, page=page)
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
        return parsed


@dataclass(frozen=True)
class _Pass:
    done: bool
    edge: datetime | None


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
