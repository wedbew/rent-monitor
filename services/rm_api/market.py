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

from deal_analyzer.market_stats import summarise_asking
from fastapi import APIRouter, Depends, Path, Query, Request, Response
from rm_contracts.market_api import (
    AskingRentOut,
    DistrictOut,
    LocationDetailOut,
    LocationDistrictsOut,
    LocationHistoryOut,
    LocationPage,
    LocationSummaryOut,
    Series,
)
from rm_contracts.market_context import (
    LocationContextOut,
    LocationIndexOut,
    OverviewOut,
    OverviewPlaceOut,
    PlaceMappingOut,
    RankingEntryOut,
    RankingOverviewOut,
    SourceOut,
)
from rm_contracts.problems import ProblemCode
from rm_core.bdl_metrics import METRICS
from rm_core.location_contracts import TerritoryHierarchy
from rm_core.location_index import INDEX_VERSION
from rm_core.location_index_read import IndexSnapshot, current_signature, load_index
from rm_core.location_index_view import CAVEAT_PL, COHORT_PL, TITLE_PL, index_out, unavailable
from rm_core.location_mapping import MappingStatus, PlaceMapping
from rm_core.location_places import PgPlaceMapping
from rm_core.location_profile import metric_view, territory_out
from rm_core.location_repo import PgLocationRepo
from rm_core.market_access import FREE_PLACE_LIMIT, FREE_RULE_PL, MarketAccess, account_access, top_by_depth
from rm_core.market_history import (
    ALL,
    CAVEATS,
    MAX_HISTORY_DAYS,
    AskingRentObservation,
    PgMarketHistory,
)

from rm_api.deps import PrincipalDep, SessionDep, SettingsDep
from rm_api.problems import Problem

router = APIRouter(prefix="/api/market", tags=["market"])

INDEX_ATTRIBUTION_PL = "Źródło: GUS, Bank Danych Lokalnych (BDL); obliczenia własne."
COHORT_PATTERN = r"^[a-z0-9_]{1,16}$"
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


async def _access(
    request: Request, settings: SettingsDep, session: SessionDep, principal: PrincipalDep
) -> MarketAccess:
    """Full for admins, Pro, pass and pack buyers; otherwise a fixed top list (`rm_core.market_access`)."""
    if await account_access(session, principal) == "full":
        return MarketAccess("full", None)
    depths = await _history(request, settings).sample_depths(settings.otodom_market_catalogue_version)
    return MarketAccess("free", top_by_depth(depths))


AccessDep = Annotated[MarketAccess, Depends(_access)]


def _not_in_plan() -> Problem:
    return Problem(
        403,
        ProblemCode.FEATURE_NOT_IN_PLAN,
        "This place is outside the free Rynek list",
        FREE_RULE_PL,
        upgrade_url="/app/credits",
    )


async def _reference(request: Request, settings: SettingsDep) -> TerritoryHierarchy | None:
    """The frozen territorial reference, loaded once per version and kept in process memory."""
    cache: dict[int, TerritoryHierarchy] = request.app.state.__dict__.setdefault("reference_cache", {})
    version = settings.location_reference_version
    if version not in cache:
        sessions = request.app.state.sessionmaker
        reference = await PgLocationRepo(sessions).get_reference(version) if sessions else None
        if reference is None:
            return None
        cache[version] = TerritoryHierarchy(reference)
    return cache[version]


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
    access: AccessDep,
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
        only_ids=access.allowed_ids,
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
    location_id: LocationId, request: Request, response: Response, settings: SettingsDep, access: AccessDep
) -> LocationDetailOut:
    """One place: live freshness and its latest cohort, one entry per cohort key."""
    response.headers["Cache-Control"] = "private, no-store"
    repo = _history(request, settings)
    name = await repo.location_name(location_id, catalogue_version=settings.otodom_market_catalogue_version)
    if name is None:
        raise Problem.not_found("Location")
    if not access.allows(location_id):
        raise _not_in_plan()
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
    access: AccessDep,
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
    if not access.allows(location_id):
        raise _not_in_plan()
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


@router.get("/locations/{location_id}/districts", response_model=LocationDistrictsOut)
async def get_location_districts(
    location_id: LocationId,
    request: Request,
    response: Response,
    settings: SettingsDep,
    access: AccessDep,
    *,
    cohort: Annotated[
        str, Query(pattern=COHORT_PATTERN, description="apartment size or rooms cohort, `all` by default")
    ] = ALL,
) -> LocationDistrictsOut:
    """The districts the source names under one place, with asking-rent statistics per district.

    Computed from the place's own stored adverts; a place whose adverts carry no district answers
    `coverage: none` with an empty list, a district under the sufficiency threshold keeps its counts and
    withholds its statistics."""
    response.headers["Cache-Control"] = "private, no-store"
    repo = _history(request, settings)
    name = await repo.location_name(location_id, catalogue_version=settings.otodom_market_catalogue_version)
    if name is None:
        raise Problem.not_found("Location")
    if not access.allows(location_id):
        raise _not_in_plan()
    view = await repo.districts(location_id, cohort_key=cohort, now=_now(request), summarise=summarise_asking)
    rows: list[DistrictOut] = []
    for d in view.districts:
        o = d.observation
        withheld = not o.sufficient
        rows.append(
            DistrictOut(
                district_id=d.district_id,
                name=d.name,
                observed_count=o.observed_count,
                priced_count=o.priced_count,
                median_rent_pln=None if withheld else o.median_rent_pln,
                median_ppm2=None if withheld else o.median_ppm2,
                p25_ppm2=None if withheld else o.p25_ppm2,
                p75_ppm2=None if withheld else o.p75_ppm2,
                sufficient=o.sufficient,
                withheld_reason="insufficient_sample" if withheld else None,
            )
        )
    return LocationDistrictsOut(
        location_id=location_id,
        name=name,
        data_status=view.data_status,
        coverage=view.coverage,
        cohort_key=view.cohort_key,
        as_of=view.as_of,
        offers_in_cohort=view.offers_in_cohort,
        offers_with_district=view.offers_with_district,
        districts=rows,
        caveats=list(CAVEATS),
    )


@router.get("/overview", response_model=OverviewOut)
async def overview(
    request: Request,
    response: Response,
    settings: SettingsDep,
    access: AccessDep,
    *,
    cohort: Annotated[
        str, Query(pattern=COHORT_PATTERN, description="apartment size or rooms cohort, `all` by default")
    ] = ALL,
) -> OverviewOut:
    """Every place this account may see, with its headline, what it maps to and its administrative area.

    One answer for a map, a sort and a comparison. The free tier gets the fixed top list only."""
    response.headers["Cache-Control"] = "private, no-store"
    version = settings.otodom_market_catalogue_version
    repo = _history(request, settings)
    places: list[LocationSummaryOut] = []
    after: tuple[str, str] | None = None
    while True:
        page, more = await repo.list_locations(
            catalogue_version=version,
            now=_now(request),
            limit=100,
            after=after,
            only_ids=access.allowed_ids,
            cohort_key=cohort,
        )
        for p in page:
            h = _out(p.headline) if p.headline is not None else None
            places.append(
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
        if not more or not page:
            break
        after = (page[-1].name, page[-1].location_id)
    mappings = await PgPlaceMapping(request.app.state.sessionmaker).all_for(version)
    tree = await _reference(request, settings)
    items: list[OverviewPlaceOut] = []
    for p in places:
        m = mappings.get(p.location_id)
        gmina = tree.get(m.gmina_id) if tree and m and m.gmina_id else None
        powiat = tree.get(m.powiat_id) if tree and m and m.powiat_id else None
        woj = tree.get(m.wojewodztwo_id) if tree and m and m.wojewodztwo_id else None
        items.append(
            OverviewPlaceOut(
                **p.model_dump(),
                mapping=m.status.value if m else None,
                relation=m.relation.value if m and m.relation else None,
                gmina_teryt=gmina.teryt if gmina else None,
                powiat_name=powiat.name if powiat else None,
                wojewodztwo_name=woj.name if woj else None,
            )
        )
    total = await repo.count_locations(catalogue_version=version)
    return OverviewOut(
        items=items,
        total_places=total,
        visible_places=len(items),
        access=access.level,
        free_limit=FREE_PLACE_LIMIT,
        free_rule_pl=FREE_RULE_PL,
        cohort_key=cohort,
    )


async def _index_snapshot(
    request: Request, settings: SettingsDep
) -> tuple[IndexSnapshot, TerritoryHierarchy] | None:
    """The finished index of every gmina, kept in process memory under the identity of the BDL releases it
    was built from (a new publication changes the key). None while no reference or no release exists."""
    tree = await _reference(request, settings)
    sessions = request.app.state.sessionmaker
    if tree is None or sessions is None:
        return None
    repo = PgLocationRepo(sessions)
    signature = await current_signature(repo)
    if not signature:
        return None
    cache: dict[int, IndexSnapshot] = request.app.state.__dict__.setdefault("index_cache", {})
    version = settings.location_reference_version
    held = cache.get(version)
    if held is None or held.signature != signature:
        held = await load_index(repo, tree)
        cache[version] = held
    return held, tree


def _place_target(mapping: PlaceMapping | None) -> str | None:
    """The gmina an index describes for a place: only a settled mapping, never a guess among candidates."""
    if mapping is None or mapping.status is not MappingStatus.mapped:
        return None
    return mapping.gmina_id


@router.get("/locations/{location_id}/ranking", response_model=LocationIndexOut)
async def get_location_ranking(
    location_id: LocationId, request: Request, response: Response, settings: SettingsDep, access: AccessDep
) -> LocationIndexOut:
    """The experimental locality index of the gmina a place belongs to: score, national and regional
    position with their denominators, every component with its value, year, unit and contribution, and the
    reasons when there is no score. Statistics about the area, never a property valuation."""
    response.headers["Cache-Control"] = "private, no-store"
    version = settings.otodom_market_catalogue_version
    name = await _history(request, settings).location_name(location_id, catalogue_version=version)
    if name is None:
        raise Problem.not_found("Location")
    if not access.allows(location_id):
        raise _not_in_plan()
    mapping = await PgPlaceMapping(request.app.state.sessionmaker).get(version, location_id)
    tree = await _reference(request, settings)
    status = mapping.status if mapping else MappingStatus.unmatched
    candidates = [territory_out(tree.get(c)) for c in mapping.candidates] if tree and mapping else []
    mapping_out = PlaceMappingOut(
        status=status.value,
        relation=mapping.relation.value if mapping and mapping.relation else None,
        method=mapping.method if mapping else "not_mapped",
        candidates=candidates if status is not MappingStatus.mapped else [],
    )
    source = SourceOut(
        attribution_pl=INDEX_ATTRIBUTION_PL,
        note_pl="Dane roczne, najnowszy opublikowany rok każdego wskaźnika; metoda opisana w wyniku.",
    )
    target = _place_target(mapping)
    held = await _index_snapshot(request, settings)
    if target is None:
        why = (
            "Nazwa miejsca pasuje do kilku gmin: nie zgadujemy, której dotyczy wynik."
            if status is MappingStatus.ambiguous
            else "Tego miejsca nie udało się jednoznacznie przypisać do gminy GUS."
        )
        index = unavailable([why])
    elif held is None:
        index = unavailable(["GUS nie opublikował jeszcze danych potrzebnych do wskaźnika."])
    else:
        index = index_out(held[0], held[1], target)
    return LocationIndexOut(
        location_id=location_id, name=name, mapping=mapping_out, index=index, source=source
    )


@router.get("/ranking", response_model=RankingOverviewOut)
async def ranking_overview(
    request: Request, response: Response, settings: SettingsDep, access: AccessDep
) -> RankingOverviewOut:
    """Every place this account may see with the index of its gmina, best position first; a place that has
    no score (unmatched, ambiguous or too little data) is listed last with its state, never hidden."""
    response.headers["Cache-Control"] = "private, no-store"
    version = settings.otodom_market_catalogue_version
    repo = _history(request, settings)
    places: list[tuple[str, str]] = []
    after: tuple[str, str] | None = None
    while True:
        page, more = await repo.list_locations(
            catalogue_version=version,
            now=_now(request),
            limit=100,
            after=after,
            only_ids=access.allowed_ids,
        )
        places.extend((p.location_id, p.name) for p in page)
        if not more or not page:
            break
        after = (page[-1].name, page[-1].location_id)
    mappings = await PgPlaceMapping(request.app.state.sessionmaker).all_for(version)
    held = await _index_snapshot(request, settings)
    items: list[RankingEntryOut] = []
    for location_id, name in places:
        m = mappings.get(location_id)
        target = _place_target(m)
        g = held[0].index.get(target) if held and target else None
        items.append(
            RankingEntryOut(
                location_id=location_id,
                name=name,
                gmina_name=held[1].get(target).name if held and target and g else None,
                state=g.state.value if g else "unavailable",
                score=g.score if g else None,
                rank=g.rank if g else None,
                of=g.of if g else None,
                relation=m.relation.value if m and m.relation else None,
            )
        )
    items.sort(key=lambda e: (e.rank is None, e.rank or 0, e.name))
    return RankingOverviewOut(
        method_version=INDEX_VERSION,
        title_pl=TITLE_PL,
        caveat_pl=CAVEAT_PL,
        cohort_name_pl=COHORT_PL,
        scored_gminas=held[0].scored if held else 0,
        total_places=await repo.count_locations(catalogue_version=version),
        visible_places=len(items),
        access=access.level,
        items=items,
        source=SourceOut(
            attribution_pl=INDEX_ATTRIBUTION_PL,
            note_pl="Dane roczne, najnowszy opublikowany rok każdego wskaźnika.",
        ),
    )


@router.get("/locations/{location_id}/context", response_model=LocationContextOut)
async def get_location_context(
    location_id: LocationId, request: Request, response: Response, settings: SettingsDep, access: AccessDep
) -> LocationContextOut:
    """GUS BDL context of a place: hierarchy, per-metric value, trend, parent and peer comparison, sources."""
    response.headers["Cache-Control"] = "private, no-store"
    version = settings.otodom_market_catalogue_version
    name = await _history(request, settings).location_name(location_id, catalogue_version=version)
    if name is None:
        raise Problem.not_found("Location")
    if not access.allows(location_id):
        raise _not_in_plan()
    sessions = request.app.state.sessionmaker
    mapping: PlaceMapping | None = await PgPlaceMapping(sessions).get(version, location_id)
    tree = await _reference(request, settings)
    source = SourceOut(
        attribution_pl="Źródło: Główny Urząd Statystyczny, Bank Danych Lokalnych (BDL).",
        note_pl="Dane roczne, najnowszy opublikowany rok; poziom jednostki jest podany przy każdej wartości.",
    )
    status = mapping.status if mapping else MappingStatus.unmatched
    candidates = [territory_out(tree.get(c)) for c in mapping.candidates] if tree and mapping else []
    mapping_out = PlaceMappingOut(
        status=status.value,
        relation=mapping.relation.value if mapping and mapping.relation else None,
        method=mapping.method if mapping else "not_mapped",
        candidates=candidates if status is not MappingStatus.mapped else [],
    )
    target = (mapping.gmina_id or mapping.powiat_id) if mapping else None
    if tree is None or target is None:
        return LocationContextOut(
            location_id=location_id,
            name=name,
            mapping=mapping_out,
            chain=[],
            metrics=[],
            published_metrics=0,
            source=source,
        )
    repo = PgLocationRepo(sessions)
    views = [await metric_view(repo, tree, spec, target) for spec in METRICS]
    chain = [tree.get(target), *tree.ancestors(target)]
    return LocationContextOut(
        location_id=location_id,
        name=name,
        mapping=mapping_out,
        chain=[territory_out(t) for t in chain],
        metrics=views,
        published_metrics=sum(1 for v in views if v.state != "unavailable"),
        source=source,
    )
