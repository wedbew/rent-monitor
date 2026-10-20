"""Daily asking-rent summaries for the Otodom rental corpus, and a read adapter over them (RM-395, OTO-04).

LEGAL[third-party-data]: aggregates original Otodom asking rents; terms unreviewed (B-012) (RM-395).
LEGAL[republication]: the reader returns aggregates only, never offers or listing content (RM-395).
GDPR[personal-data]: counts and quantiles; no personal data is read or written here (RM-395).

Two series that are never mixed (docs/OTODOM-NIGHTLY-IMPORT.md section 8):
- `additions`: offers whose *source date* is the summary day (original publication date, else the day first
  seen), with the number of IDs first observed that day shown separately, so a late recovery run is not
  presented as a day's publication;
- `cohort`: the rolling collection of original asking rents whose `expires_at` is after `as_of` (90 elapsed
  days). It is not a set of active offers and not a set of achieved rents.

Invariant 2: every figure is an *asking* observation. No deed price can enter (the table CHECKs `asking`).
Invariant 4: quantiles come from the injected `Summariser` (`deal_analyzer.market_stats.summarise_asking`);
this module counts, groups and persists, it does not compute statistics. A summary day is published
atomically (one transaction under an advisory lock), immutably, once per calculation version.
"""

import hashlib
from collections import defaultdict
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict
from rm_contracts.market import FRESH_HOURS, STALE_HOURS, DataStatus
from sqlalchemy import func, literal, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import (
    MarketDailySummary,
    MarketDistrict,
    MarketImportCheckpoint,
    MarketImportRun,
    MarketLocation,
    MarketOffer,
    MarketOfferDistrict,
    MarketOfferRooms,
)

DATASET = "otodom_rental"
# Bump when the cohort rules or the statistics change; old rows stay as published, readers take the newest.
# 2: offers left on a dead run count once a later published run covers them; no first-seen count on a
# bootstrap day.
# 3: the room count of an offer stored without one is read from its sidecar (RM-439), so rooms cohorts exist.
CALC_VERSION = 3
MIN_PRICED = 10  # below this a published row says "insufficient evidence" (matches the CHECK)
MAX_HISTORY_DAYS = 400
ALL = "all"
CAVEATS = ("asking_not_achieved_rent", "not_active_stock", "not_deed_price")

Series = Literal["additions", "cohort"]
PublishStatus = Literal["published", "already_published", "bootstrap_pending", "before_bootstrap"]


class QuantileSummary(Protocol):
    @property
    def count(self) -> int: ...
    @property
    def median(self) -> Decimal: ...
    @property
    def p25(self) -> Decimal: ...
    @property
    def p75(self) -> Decimal: ...


Summariser = Callable[[Sequence[Decimal]], QuantileSummary | None]


@dataclass(frozen=True)
class OfferFacts:
    """The whitelisted fields of a stored offer that a summary needs."""

    source_id: int
    rent: Decimal | None
    area: Decimal | None
    rooms: int | None
    published_at: datetime | None
    first_seen_at: datetime
    age_basis: str
    expires_at: datetime
    initial_load: bool = False  # read by a bootstrap run: the place's backlog, not a day's arrivals
    district_id: str | None = None  # the source's district of the advert, beside the offer (RM-439)

    @property
    def priced(self) -> bool:
        return self.rent is not None and self.area is not None

    @property
    def source_date(self) -> date:
        anchor = (
            self.published_at if self.age_basis == "publication" and self.published_at else self.first_seen_at
        )
        return anchor.astimezone(UTC).date()

    @property
    def first_seen_date(self) -> date:
        return self.first_seen_at.astimezone(UTC).date()


def cohort_keys(o: OfferFacts) -> list[str]:
    """`all` plus the bedroom (rooms) cohort and the size cohort the offer belongs to, where known."""
    keys = [ALL]
    if o.rooms is not None:
        keys.append(f"rooms_{o.rooms}" if o.rooms < 4 else "rooms_4plus")
    if o.area is not None:
        for limit, key in (
            (Decimal(30), "size_lt30"),
            (Decimal(45), "size_30_45"),
            (Decimal(60), "size_45_60"),
            (Decimal(80), "size_60_80"),
        ):
            if o.area < limit:
                keys.append(key)
                break
        else:
            keys.append("size_80plus")
    return keys


class SummaryRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    location_id: str
    summary_date: date
    series: Series
    cohort_key: str
    calc_version: int
    as_of: datetime
    observed_count: int
    priced_count: int
    first_observed_count: int | None
    median_rent_pln: Decimal | None
    median_ppm2: Decimal | None
    p25_ppm2: Decimal | None
    p75_ppm2: Decimal | None
    sufficient: bool
    input_digest: str
    backfilled: bool
    refresh_at: datetime | None
    gap_since: datetime | None


def _digest(series: str, members: Sequence[OfferFacts]) -> str:
    lines = sorted(f"{o.source_id}|{o.rent}|{o.area}|{o.rooms}|{o.age_basis}" for o in members)
    return hashlib.sha256((f"{series}\n{CALC_VERSION}\n" + "\n".join(lines)).encode()).hexdigest()


def _row(
    *,
    location_id: str,
    day: date,
    series: Series,
    key: str,
    members: Sequence[OfferFacts],
    first_observed: int | None,
    as_of: datetime,
    summarise: Summariser,
    backfilled: bool,
    refresh_at: datetime | None,
    gap_since: datetime | None,
) -> SummaryRow:
    priced = [o for o in members if o.priced]
    rents = [o.rent for o in priced if o.rent is not None]
    ppm2 = [o.rent / o.area for o in priced if o.rent is not None and o.area is not None]
    rent_stats = summarise(rents)
    ppm2_stats = summarise(ppm2)
    return SummaryRow(
        location_id=location_id,
        summary_date=day,
        series=series,
        cohort_key=key,
        calc_version=CALC_VERSION,
        as_of=as_of,
        observed_count=len(members),
        priced_count=len(priced),
        first_observed_count=first_observed,
        median_rent_pln=rent_stats.median if rent_stats else None,
        median_ppm2=ppm2_stats.median if ppm2_stats else None,
        p25_ppm2=ppm2_stats.p25 if ppm2_stats else None,
        p75_ppm2=ppm2_stats.p75 if ppm2_stats else None,
        sufficient=len(priced) >= MIN_PRICED,
        input_digest=_digest(series, members),
        backfilled=backfilled,
        refresh_at=refresh_at,
        gap_since=gap_since,
    )


def build_rows(
    location_id: str,
    day: date,
    offers: Sequence[OfferFacts],
    *,
    as_of: datetime,
    summarise: Summariser,
    backfilled: bool = False,
    refresh_at: datetime | None = None,
    gap_since: datetime | None = None,
) -> list[SummaryRow]:
    """Pure: the rows of one location-day. `offers` may be any superset; only what was known before `as_of`
    counts. The `all` row of each series is always present (a day with zero offers is a published zero)."""
    known = [o for o in offers if o.first_seen_at < as_of]
    additions = [o for o in known if o.source_date == day]
    first_seen_today = [o for o in known if o.first_seen_date == day]
    # The bootstrap stamps the whole backlog "first seen" on its own day. That day has no honest count of
    # new arrivals, so it says "not applicable" (None) instead of a backlog figure or a misleading zero.
    initial_load_day = any(o.initial_load for o in first_seen_today)
    cohort = [o for o in known if o.expires_at > as_of]
    out: list[SummaryRow] = []
    for series, members in (("additions", additions), ("cohort", cohort)):
        by_key: dict[str, list[OfferFacts]] = defaultdict(list)
        for o in members:
            for k in cohort_keys(o):
                by_key[k].append(o)
        first_by_key: dict[str, int] = defaultdict(int)
        if series == "additions":
            for o in first_seen_today:
                for k in cohort_keys(o):
                    first_by_key[k] += 1
        keys = sorted({ALL, *by_key, *first_by_key})
        for k in keys:
            out.append(
                _row(
                    location_id=location_id,
                    day=day,
                    series=series,  # type: ignore[arg-type]  # one of the two literals above
                    key=k,
                    members=by_key.get(k, []),
                    first_observed=(
                        None if initial_load_day or series != "additions" else first_by_key.get(k, 0)
                    ),
                    as_of=as_of,
                    summarise=summarise,
                    backfilled=backfilled,
                    refresh_at=refresh_at,
                    gap_since=gap_since,
                )
            )
    return out


def freshness(
    *,
    bootstrapped: bool,
    refresh_at: datetime | None,
    gap_since: datetime | None,
    now: datetime,
    fresh_hours: int = FRESH_HOURS,
    stale_hours: int = STALE_HOURS,
) -> DataStatus:
    """Pending bootstrap is unavailable; a gap or age past `stale_hours` is stale; past `fresh_hours`,
    delayed. The ages are the settings `OTODOM_MARKET_FRESH_HOURS` / `_STALE_HOURS` (defaults 36 / 72)."""
    if not bootstrapped or refresh_at is None:
        return DataStatus.unavailable
    age = now - refresh_at
    if gap_since is not None or age > timedelta(hours=stale_hours):
        return DataStatus.stale
    return DataStatus.delayed if age > timedelta(hours=fresh_hours) else DataStatus.fresh


class AskingRentObservation(BaseModel):
    """What a reader may show: an aggregate of original asking rents, labelled as such. Never an achieved
    rent, never stock, never a deed price (invariant 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    price_basis: Literal["asking"] = "asking"
    measure: Literal["original_asking_rent"] = "original_asking_rent"
    source: Literal["otodom"] = "otodom"
    archive_days: Literal[90] = 90
    caveats: tuple[str, ...] = CAVEATS
    location_id: str
    summary_date: date
    series: Series
    cohort_key: str
    calc_version: int
    as_of: datetime
    observed_count: int
    priced_count: int
    first_observed_count: int | None
    median_rent_pln: Decimal | None
    median_ppm2: Decimal | None
    p25_ppm2: Decimal | None
    p75_ppm2: Decimal | None
    sufficient: bool
    backfilled: bool


class MarketView(BaseModel):
    """Latest cohort of a location with its live freshness (computed from the checkpoint at read time)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    location_id: str
    data_status: DataStatus
    last_successful_refresh_at: datetime | None
    covered_until: datetime | None
    unresolved_gap_since: datetime | None
    cohort: tuple[AskingRentObservation, ...]
    usable_for_ranking: bool  # fresh and enough priced observations in the `all` cohort


class LocationListing(BaseModel):
    """One place of the catalogue with the headline of its latest published `cohort`/`all` row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    location_id: str
    name: str
    data_status: DataStatus
    last_successful_refresh_at: datetime | None
    headline: AskingRentObservation | None


@dataclass(frozen=True)
class DistrictRow:
    district_id: str
    name: str
    observation: SummaryRow


@dataclass(frozen=True)
class DistrictsView:
    location_id: str
    data_status: DataStatus
    coverage: Literal["supported", "none"]
    cohort_key: str
    as_of: datetime
    offers_in_cohort: int
    offers_with_district: int
    districts: tuple[DistrictRow, ...]


@dataclass(frozen=True)
class PublishResult:
    status: PublishStatus
    rows: int = 0


def _obs(r: MarketDailySummary) -> AskingRentObservation:
    return AskingRentObservation(
        location_id=r.location_id,
        summary_date=r.summary_date,
        series=cast("Series", r.series),  # CHECKed vocabulary
        cohort_key=r.cohort_key,
        calc_version=r.calc_version,
        as_of=r.as_of,
        observed_count=r.observed_count,
        priced_count=r.priced_count,
        first_observed_count=r.first_observed_count,
        median_rent_pln=r.median_rent_pln,
        median_ppm2=r.median_ppm2,
        p25_ppm2=r.p25_ppm2,
        p75_ppm2=r.p75_ppm2,
        sufficient=r.sufficient,
        backfilled=r.backfilled,
    )


def _latest_versions(rows: Sequence[MarketDailySummary]) -> list[MarketDailySummary]:
    best: dict[tuple[date, str, str], MarketDailySummary] = {}
    for r in rows:
        k = (r.summary_date, r.series, r.cohort_key)
        if k not in best or r.calc_version > best[k].calc_version:
            best[k] = r
    return sorted(best.values(), key=lambda r: (r.summary_date, r.series, r.cohort_key))


class PgMarketHistory:
    """Publishes and reads daily summaries. Each call is its own short transaction; none spans I/O."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        fresh_hours: int = FRESH_HOURS,
        stale_hours: int = STALE_HOURS,
    ) -> None:
        self._sessions = sessions
        self._fresh = fresh_hours
        self._stale = stale_hours

    # --- publication -----------------------------------------------------------------------------

    async def publish_day(
        self, location_id: str, day: date, *, now: datetime, summarise: Summariser
    ) -> PublishResult:
        """Publish all rows of `day` for the location, atomically and once per calculation version.

        Today's rows use `as_of=now`; an earlier day is a backfill with `as_of` at the end of that day and is
        refused before the location's bootstrap (those offers did not exist in our corpus yet). Offers from
        runs that did not publish are ignored."""
        today = now.astimezone(UTC).date()
        if day > today:
            raise ValueError("cannot publish a summary for a future day")
        backfilled = day < today
        as_of = now if not backfilled else datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
        day_start = datetime.combine(day, datetime.min.time(), UTC)
        async with self._sessions() as s, s.begin():
            await s.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"market_history:{location_id}:{DATASET}:{day.isoformat()}"},
            )
            cp = await s.get(MarketImportCheckpoint, (location_id, DATASET))
            if cp is None or cp.bootstrap_completed_at is None:
                return PublishResult("bootstrap_pending")
            if backfilled and day < cp.bootstrap_completed_at.astimezone(UTC).date():
                return PublishResult("before_bootstrap")
            exists = await s.scalar(
                select(func.count())
                .select_from(MarketDailySummary)
                .where(
                    MarketDailySummary.location_id == location_id,
                    MarketDailySummary.dataset == DATASET,
                    MarketDailySummary.summary_date == day,
                    MarketDailySummary.calc_version == CALC_VERSION,
                )
            )
            if exists:
                return PublishResult("already_published")
            offers = await self._offers(s, location_id, as_of=as_of, day_start=day_start)
            rows = build_rows(
                location_id,
                day,
                offers,
                as_of=as_of,
                summarise=summarise,
                backfilled=backfilled,
                refresh_at=cp.last_successful_refresh_at,
                gap_since=cp.unresolved_gap_since,
            )
            await s.execute(
                insert(MarketDailySummary).on_conflict_do_nothing(),
                [{**r.model_dump(), "dataset": DATASET} for r in rows],
            )
            return PublishResult("published", len(rows))

    async def _offers(
        self, s: AsyncSession, location_id: str, *, as_of: datetime, day_start: datetime
    ) -> list[OfferFacts]:
        day_end = day_start + timedelta(days=1)
        anchor = func.coalesce(MarketOffer.published_at, MarketOffer.first_seen_at)
        covering = MarketImportRun.__table__.alias("covering")
        # An offer counts when its own run published, or when a later published run of the same place
        # covered its creation time: inserts are idempotent, so an offer first stored by a run that never
        # published (killed, superseded) stays attributed to that run although the covering run re-read it.
        covered = (
            select(literal(1))
            .where(
                covering.c.location_id == MarketOffer.location_id,
                covering.c.state == "published",
                covering.c.created_at > MarketImportRun.created_at,
                covering.c.window_start <= anchor,
                covering.c.window_end >= anchor,
            )
            .exists()
        )
        result = await s.execute(
            select(
                MarketOffer.source_offer_id,
                MarketOffer.asking_rent_pln,
                MarketOffer.area_m2,
                func.coalesce(MarketOffer.rooms, MarketOfferRooms.rooms),
                MarketOffer.published_at,
                MarketOffer.first_seen_at,
                MarketOffer.age_basis,
                MarketOffer.expires_at,
                MarketImportRun.mode,
                MarketOfferDistrict.district_id,
            )
            .join(MarketImportRun, MarketImportRun.run_id == MarketOffer.run_id)
            .join(
                MarketOfferRooms,
                (MarketOfferRooms.source == MarketOffer.source)
                & (MarketOfferRooms.source_offer_id == MarketOffer.source_offer_id),
                isouter=True,
            )
            .join(
                MarketOfferDistrict,
                (MarketOfferDistrict.source == MarketOffer.source)
                & (MarketOfferDistrict.source_offer_id == MarketOffer.source_offer_id),
                isouter=True,
            )
            .where(
                (MarketImportRun.state == "published") | covered,
                MarketOffer.location_id == location_id,
                MarketOffer.first_seen_at < as_of,
                (MarketOffer.expires_at > as_of)
                | ((MarketOffer.first_seen_at >= day_start) & (MarketOffer.first_seen_at < day_end))
                | ((MarketOffer.published_at >= day_start) & (MarketOffer.published_at < day_end)),
            )
        )
        return [
            OfferFacts(int(i), rent, area, rooms, pub, seen, basis, exp, mode == "bootstrap", district)
            for i, rent, area, rooms, pub, seen, basis, exp, mode, district in result
        ]

    async def backfill(
        self, location_id: str, start: date, end: date, *, now: datetime, summarise: Summariser
    ) -> dict[date, PublishResult]:
        """Publish missing past days `start..end` (inclusive, before today). Idempotent; days already
        published or before the bootstrap are reported, not rewritten."""
        today = now.astimezone(UTC).date()
        if end >= today or end < start or (end - start).days >= MAX_HISTORY_DAYS:
            raise ValueError("backfill takes past days, ordered, at most 400 days")
        out: dict[date, PublishResult] = {}
        day = start
        while day <= end:
            out[day] = await self.publish_day(location_id, day, now=now, summarise=summarise)
            day += timedelta(days=1)
        return out

    async def publish_all(
        self, location_ids: Sequence[str], day: date, *, now: datetime, summarise: Summariser
    ) -> dict[str, PublishResult | Exception]:
        """One location failing never blocks the others; its exception is returned for the caller to log."""
        out: dict[str, PublishResult | Exception] = {}
        for loc in location_ids:
            try:
                out[loc] = await self.publish_day(loc, day, now=now, summarise=summarise)
            except Exception as exc:
                out[loc] = exc
        return out

    # --- reads (asking observations only) --------------------------------------------------------

    async def view(self, location_id: str, *, now: datetime) -> MarketView:
        """Latest published cohort with live freshness. Pending bootstrap: `unavailable`, no rows."""
        async with self._sessions() as s:
            cp = await s.get(MarketImportCheckpoint, (location_id, DATASET))
            status = freshness(
                bootstrapped=cp is not None and cp.bootstrap_completed_at is not None,
                refresh_at=cp.last_successful_refresh_at if cp else None,
                gap_since=cp.unresolved_gap_since if cp else None,
                now=now,
                fresh_hours=self._fresh,
                stale_hours=self._stale,
            )
            cohort: tuple[AskingRentObservation, ...] = ()
            if status is not DataStatus.unavailable:
                latest = await s.scalar(
                    select(func.max(MarketDailySummary.summary_date)).where(
                        MarketDailySummary.location_id == location_id,
                        MarketDailySummary.dataset == DATASET,
                        MarketDailySummary.series == "cohort",
                    )
                )
                if latest is not None:
                    rows = (
                        await s.scalars(
                            select(MarketDailySummary).where(
                                MarketDailySummary.location_id == location_id,
                                MarketDailySummary.dataset == DATASET,
                                MarketDailySummary.series == "cohort",
                                MarketDailySummary.summary_date == latest,
                            )
                        )
                    ).all()
                    cohort = tuple(_obs(r) for r in _latest_versions(rows))
        everything = next((o for o in cohort if o.cohort_key == ALL), None)
        return MarketView(
            location_id=location_id,
            data_status=status,
            last_successful_refresh_at=cp.last_successful_refresh_at if cp else None,
            covered_until=cp.covered_until if cp else None,
            unresolved_gap_since=cp.unresolved_gap_since if cp else None,
            cohort=cohort,
            usable_for_ranking=status is DataStatus.fresh
            and everything is not None
            and everything.sufficient,
        )

    async def districts(
        self, location_id: str, *, cohort_key: str, now: datetime, summarise: Summariser
    ) -> DistrictsView:
        """The districts the source named under the place, each summarised over the same rolling cohort the
        place's own `cohort` series uses, computed now from the stored offers. Nothing is allocated from the
        city to a district and no history is invented: a district is only what its own adverts say.

        `coverage` is `none` when the source has named no district for any stored offer of the place (a
        place without a district level), otherwise `supported`; a known district with fewer than
        `MIN_PRICED` priced adverts keeps its counts and withholds its statistics."""
        today = now.astimezone(UTC)
        day_start = datetime.combine(today.date(), datetime.min.time(), UTC)
        async with self._sessions() as s:
            cp = await s.get(MarketImportCheckpoint, (location_id, DATASET))
            status = freshness(
                bootstrapped=cp is not None and cp.bootstrap_completed_at is not None,
                refresh_at=cp.last_successful_refresh_at if cp else None,
                gap_since=cp.unresolved_gap_since if cp else None,
                now=now,
                fresh_hours=self._fresh,
                stale_hours=self._stale,
            )
            found = await s.execute(
                select(MarketDistrict.district_id, MarketDistrict.name).where(
                    MarketDistrict.location_id == location_id
                )
            )
            names = {district_id: name for district_id, name in found.all()}  # noqa: C416  (rows are tuples)
            offers = (
                await self._offers(s, location_id, as_of=now, day_start=day_start)
                if status is not DataStatus.unavailable
                else []
            )
        eligible = [
            o for o in offers if o.first_seen_at < now and o.expires_at > now and cohort_key in cohort_keys(o)
        ]
        by_district: dict[str, list[OfferFacts]] = defaultdict(list)
        for o in eligible:
            if o.district_id is not None:
                by_district[o.district_id].append(o)
        rows: list[DistrictRow] = []
        for district_id, name in names.items():
            members = by_district.get(district_id, [])
            row = _row(
                location_id=location_id,
                day=today.date(),
                series="cohort",
                key=cohort_key,
                members=members,
                first_observed=None,
                as_of=now,
                summarise=summarise,
                backfilled=False,
                refresh_at=cp.last_successful_refresh_at if cp else None,
                gap_since=cp.unresolved_gap_since if cp else None,
            )
            rows.append(DistrictRow(district_id=district_id, name=name, observation=row))
        rows.sort(key=lambda r: (-r.observation.priced_count, r.name))
        return DistrictsView(
            location_id=location_id,
            data_status=status,
            coverage="supported" if names else "none",
            cohort_key=cohort_key,
            as_of=now,
            offers_in_cohort=len(eligible),
            offers_with_district=sum(1 for o in eligible if o.district_id is not None),
            districts=tuple(rows),
        )

    async def history(
        self,
        location_id: str,
        series: Series,
        start: date,
        end: date,
        *,
        cohort_key: str = ALL,
    ) -> list[AskingRentObservation]:
        """Daily history of one series and cohort, oldest first, the latest calculation per day."""
        if end < start or (end - start).days >= MAX_HISTORY_DAYS:
            raise ValueError("history takes an ordered range of at most 400 days")
        async with self._sessions() as s:
            rows = (
                await s.scalars(
                    select(MarketDailySummary).where(
                        MarketDailySummary.location_id == location_id,
                        MarketDailySummary.dataset == DATASET,
                        MarketDailySummary.series == series,
                        MarketDailySummary.cohort_key == cohort_key,
                        MarketDailySummary.summary_date.between(start, end),
                    )
                )
            ).all()
        return [_obs(r) for r in _latest_versions(rows)]

    # --- catalogue listing (names, search, keyset paging) ----------------------------------------

    async def sample_depths(self, catalogue_version: int) -> list[tuple[str, int]]:
        """`(location_id, priced_count)` of the newest published `all` cohort of every enabled place that has
        one with a sufficient sample: the input of the free-tier rule (`rm_core.market_access`)."""
        async with self._sessions() as s:
            rows = (
                await s.execute(
                    select(MarketDailySummary.location_id, MarketDailySummary.priced_count)
                    .join(
                        MarketLocation,
                        (MarketLocation.location_id == MarketDailySummary.location_id)
                        & (MarketLocation.catalogue_version == catalogue_version)
                        & MarketLocation.launch_enabled.is_(True),
                    )
                    .where(
                        MarketDailySummary.dataset == DATASET,
                        MarketDailySummary.series == "cohort",
                        MarketDailySummary.cohort_key == ALL,
                        MarketDailySummary.priced_count >= MIN_PRICED,
                    )
                    .distinct(MarketDailySummary.location_id)
                    .order_by(
                        MarketDailySummary.location_id,
                        MarketDailySummary.summary_date.desc(),
                        MarketDailySummary.calc_version.desc(),
                    )
                )
            ).all()
        return [(r.location_id, int(r.priced_count)) for r in rows]

    async def count_locations(self, *, catalogue_version: int) -> int:
        async with self._sessions() as s:
            return int(
                await s.scalar(
                    select(func.count())
                    .select_from(MarketLocation)
                    .where(
                        MarketLocation.catalogue_version == catalogue_version,
                        MarketLocation.launch_enabled.is_(True),
                    )
                )
                or 0
            )

    async def location_name(self, location_id: str, *, catalogue_version: int) -> str | None:
        """The name of an enabled catalogue place, or None for an unknown or switched-off one."""
        async with self._sessions() as s:
            return await s.scalar(
                select(MarketLocation.name).where(
                    MarketLocation.catalogue_version == catalogue_version,
                    MarketLocation.location_id == location_id,
                    MarketLocation.launch_enabled.is_(True),
                )
            )

    async def list_locations(
        self,
        *,
        catalogue_version: int,
        now: datetime,
        limit: int,
        query: str | None = None,
        after: tuple[str, str] | None = None,
        only_ids: Collection[str] | None = None,
        cohort_key: str = ALL,
    ) -> tuple[list[LocationListing], bool]:
        """Enabled places ordered by `(name, location_id)`, keyset after `after`. `query` is a literal
        case-insensitive substring of the name (LIKE metacharacters are escaped). Returns the page and whether
        more follow. A place without a published row has `headline=None`."""
        stmt = select(MarketLocation.location_id, MarketLocation.name).where(
            MarketLocation.catalogue_version == catalogue_version, MarketLocation.launch_enabled.is_(True)
        )
        if only_ids is not None:
            stmt = stmt.where(MarketLocation.location_id.in_(sorted(only_ids)))
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(MarketLocation.name.ilike(f"%{escaped}%", escape="\\"))
        if after is not None:
            stmt = stmt.where(
                tuple_(MarketLocation.name, MarketLocation.location_id)
                > tuple_(literal(after[0]), literal(after[1]))
            )
        async with self._sessions() as s:
            found = (
                await s.execute(
                    stmt.order_by(MarketLocation.name, MarketLocation.location_id).limit(limit + 1)
                )
            ).all()
            page = found[:limit]
            ids = [r.location_id for r in page]
            checkpoints = {
                c.location_id: c
                for c in (
                    await s.scalars(
                        select(MarketImportCheckpoint).where(
                            MarketImportCheckpoint.location_id.in_(ids),
                            MarketImportCheckpoint.dataset == DATASET,
                        )
                    )
                ).all()
            }
            latest = {
                r.location_id: r
                for r in (
                    await s.scalars(
                        select(MarketDailySummary)
                        .where(
                            MarketDailySummary.location_id.in_(ids),
                            MarketDailySummary.dataset == DATASET,
                            MarketDailySummary.series == "cohort",
                            MarketDailySummary.cohort_key == cohort_key,
                        )
                        .distinct(MarketDailySummary.location_id)
                        .order_by(
                            MarketDailySummary.location_id,
                            MarketDailySummary.summary_date.desc(),
                            MarketDailySummary.calc_version.desc(),
                        )
                    )
                ).all()
            }
        out: list[LocationListing] = []
        for r in page:
            cp = checkpoints.get(r.location_id)
            status = freshness(
                bootstrapped=cp is not None and cp.bootstrap_completed_at is not None,
                refresh_at=cp.last_successful_refresh_at if cp else None,
                gap_since=cp.unresolved_gap_since if cp else None,
                now=now,
                fresh_hours=self._fresh,
                stale_hours=self._stale,
            )
            row = latest.get(r.location_id)
            out.append(
                LocationListing(
                    location_id=r.location_id,
                    name=r.name,
                    data_status=status,
                    last_successful_refresh_at=cp.last_successful_refresh_at if cp else None,
                    headline=_obs(row) if row is not None and status is not DataStatus.unavailable else None,
                )
            )
        return out, len(found) > limit
