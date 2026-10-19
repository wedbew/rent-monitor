"""`/api/market/locations`: asking-rent aggregates per place, freshness, daily history (RM-421, #21).

Read-only and session-authenticated. The data is shared market data, not tenant-owned; nothing here writes.
Searching, paging and history length are bounded on the server. A sample under the sufficiency threshold
has its statistics withheld (`withheld_reason`); a place whose bootstrap is pending answers `unavailable`
with no rows.

LEGAL[third-party-data]: aggregates of original Otodom asking rents; terms unreviewed (B-012) (RM-421).
LEGAL[republication]: aggregates only, never an offer or listing content (RM-421).
GDPR[personal-data]: no personal data is read or returned (RM-421).
"""

import base64
import binascii
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response
from rm_contracts.market_api import (
    AskingRentOut,
    LocationDetailOut,
    LocationHistoryOut,
    LocationPage,
    LocationSummaryOut,
    Series,
)
from rm_contracts.problems import ProblemCode
from rm_core.market_history import ALL, MAX_HISTORY_DAYS, AskingRentObservation, PgMarketHistory

from rm_api.deps import PrincipalDep, SettingsDep
from rm_api.problems import Problem

router = APIRouter(prefix="/api/market", tags=["market"])

LocationId = Annotated[str, Path(pattern=r"^[a-z0-9-]{1,64}$", description="stable internal place id")]


def _history(request: Request, settings: SettingsDep) -> PgMarketHistory:
    sessions = request.app.state.sessionmaker
    if sessions is None:
        raise Problem(503, ProblemCode.NOT_READY, "Database is not configured")
    return PgMarketHistory(
        sessions,
        fresh_hours=settings.otodom_market_fresh_hours,
        stale_hours=settings.otodom_market_stale_hours,
    )


def _now(request: Request) -> datetime:
    clock = getattr(request.app.state, "clock", None)  # tests pin it; production uses the wall clock
    return clock() if clock is not None else datetime.now(UTC)


def _out(o: AskingRentObservation) -> AskingRentOut:
    withheld = not o.sufficient
    return AskingRentOut(
        caveats=list(o.caveats),
        summary_date=o.summary_date,
        series=o.series,
        cohort_key=o.cohort_key,
        as_of=o.as_of,
        observed_count=o.observed_count,
        priced_count=o.priced_count,
        first_observed_count=o.first_observed_count,
        median_rent_pln=None if withheld else o.median_rent_pln,
        median_ppm2=None if withheld else o.median_ppm2,
        p25_ppm2=None if withheld else o.p25_ppm2,
        p75_ppm2=None if withheld else o.p75_ppm2,
        sufficient=o.sufficient,
        withheld_reason="insufficient_sample" if withheld else None,
        backfilled=o.backfilled,
    )


def _encode_cursor(name: str, location_id: str) -> str:
    raw = json.dumps([name, location_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    """Strict: anything but what `_encode_cursor` makes is a 422, never a 500 or a guess."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        name, ident = json.loads(raw)
        if not isinstance(name, str) or not isinstance(ident, str):
            raise ValueError
        return name, ident
    except (ValueError, TypeError, binascii.Error):
        raise Problem(
            422,
            ProblemCode.VALIDATION_ERROR,
            "Invalid cursor",
            errors=[
                {"loc": ["query", "cursor"], "type": "invalid_cursor", "msg": "Not a cursor from this API"}
            ],
        ) from None


@router.get("/locations", response_model=LocationPage)
async def list_locations(
    request: Request,
    response: Response,
    settings: SettingsDep,
    _: PrincipalDep,
    *,
    q: Annotated[str | None, Query(min_length=1, max_length=60, description="part of the place name")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[
        str | None, Query(max_length=300, description="`next_cursor` of the previous page")
    ] = None,
) -> LocationPage:
    """Catalogue places by name with the headline of their latest published cohort."""
    response.headers["Cache-Control"] = "private, no-store"
    after = _decode_cursor(cursor) if cursor is not None else None
    places, more = await _history(request, settings).list_locations(
        catalogue_version=settings.otodom_market_catalogue_version,
        now=_now(request),
        limit=limit,
        query=q.strip() if q else None,
        after=after,
    )
    items: list[LocationSummaryOut] = []
    for p in places:
        h = _out(p.headline) if p.headline is not None else None
        items.append(
            LocationSummaryOut(
                location_id=p.location_id,
                name=p.name,
                data_status=p.data_status,
                last_successful_refresh_at=p.last_successful_refresh_at,
                latest_summary_date=h.summary_date if h else None,
                median_rent_pln=h.median_rent_pln if h else None,
                median_ppm2=h.median_ppm2 if h else None,
                priced_count=h.priced_count if h else None,
                sufficient=h.sufficient if h else None,
                withheld_reason=h.withheld_reason if h else None,
            )
        )
    return LocationPage(
        items=items,
        next_cursor=_encode_cursor(places[-1].name, places[-1].location_id) if more and places else None,
    )


@router.get("/locations/{location_id}", response_model=LocationDetailOut)
async def get_location(
    location_id: LocationId, request: Request, response: Response, settings: SettingsDep, _: PrincipalDep
) -> LocationDetailOut:
    """One place: live freshness and its latest cohort, one entry per cohort key."""
    response.headers["Cache-Control"] = "private, no-store"
    repo = _history(request, settings)
    name = await repo.location_name(location_id, catalogue_version=settings.otodom_market_catalogue_version)
    if name is None:
        raise Problem.not_found("Location")
    view = await repo.view(location_id, now=_now(request))
    return LocationDetailOut(
        location_id=location_id,
        name=name,
        data_status=view.data_status,
        last_successful_refresh_at=view.last_successful_refresh_at,
        covered_until=view.covered_until,
        unresolved_gap_since=view.unresolved_gap_since,
        usable_for_ranking=view.usable_for_ranking,
        cohort=[_out(o) for o in view.cohort],
    )


@router.get("/locations/{location_id}/history", response_model=LocationHistoryOut)
async def get_location_history(
    location_id: LocationId,
    request: Request,
    response: Response,
    settings: SettingsDep,
    _: PrincipalDep,
    *,
    series: Annotated[Series, Query(description="`additions` and `cohort` are never mixed")] = "cohort",
    cohort: Annotated[
        str, Query(pattern=r"^[a-z0-9_]{1,16}$", description="cohort key, `all` by default")
    ] = ALL,
    days: Annotated[int, Query(ge=1, le=MAX_HISTORY_DAYS - 1, description="days ending today (UTC)")] = 90,
) -> LocationHistoryOut:
    """Daily history of one series and cohort, oldest first. A day without a published row is absent."""
    response.headers["Cache-Control"] = "private, no-store"
    repo = _history(request, settings)
    if (
        await repo.location_name(location_id, catalogue_version=settings.otodom_market_catalogue_version)
        is None
    ):
        raise Problem.not_found("Location")
    end = _now(request).astimezone(UTC).date()
    start = end - timedelta(days=days - 1)
    points = await repo.history(location_id, series, start, end, cohort_key=cohort)
    return LocationHistoryOut(
        location_id=location_id,
        series=series,
        cohort_key=cohort,
        start=start,
        end=end,
        points=[_out(o) for o in points],
    )
