# ruff: noqa: F811  (the `app` fixture is imported from test_me_saved_admin and used as a parameter)
"""`/api/market/locations`: list, detail and history on real Postgres through the real API (RM-421, #21).

LEGAL[third-party-data]: hand-built asking figures published through the production repository; no network.

Real: the API, session auth, Postgres, the corpus and the summary publisher. Offers are hand-made so every
expected figure below is computed by hand, not read back from the code under test.
"""

import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from deal_analyzer.market_stats import summarise_asking
from fastapi import FastAPI
from market_corpus_contract import obs, run
from rm_contracts.market import LocationCatalogue, LocationEntry, OfferObservation, RunMode, RunState
from rm_core.market_corpus import PgCorpus
from rm_core.market_history import PgMarketHistory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_me_saved_admin import MakeToken, app, client_for, make_admin, sign_in  # noqa: F401  (fixture: `app`)

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_daily_summary, app.market_offer_rooms, app.market_offer_district, app.market_district,"
    " app.market_offer, app.market_import_run, app.market_import_checkpoint,"
    " app.market_location_territory, app.market_location, app.market_catalogue"
)
BOOT = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
PLACES = {"toruń": "Toruń", "gdansk": "Gdańsk", "gdynia": "Gdynia", "kraków": "Kraków"}
# Catalogue ids are ASCII; the names carry the diacritics the search has to handle.
IDS = {"toruń": "torun", "gdansk": "gdansk", "gdynia": "gdynia", "kraków": "krakow"}


def catalogue() -> LocationCatalogue:
    return LocationCatalogue.build(
        1,
        "test-catalogue",
        [
            LocationEntry(location_id=IDS[k], name=name, otodom_path=f"cala-polska/{IDS[k]}")
            for k, name in PLACES.items()
        ],
    )


def twelve(start: int) -> list[OfferObservation]:
    """Rents 2000, 2050 ... 2550 PLN on 50 m2: PLN/m2 40 ... 51, so the figures are known without the code."""
    return [obs(str(start + i), rent=str(2000 + 50 * i), area="50", rooms=2) for i in range(12)]


async def ingest(
    corpus: PgCorpus,
    rid: str,
    loc: str,
    observations: list[OfferObservation],
    *,
    seen: datetime = BOOT,
    mode: RunMode = RunMode.bootstrap,
    start: datetime = BOOT - timedelta(hours=24),
) -> None:
    await corpus.start_run(run(rid, loc, mode, start=start))
    await corpus.save_progress(rid, pages_fetched=1, pages_expected=1)
    await corpus.record_offers(rid, observations, seen)
    await corpus.finish_run(rid, state=RunState.published, now=seen)


@pytest.fixture
async def market(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[PgMarketHistory]:
    """Toruń: 12 priced offers. Gdynia: 3 (withheld). Gdańsk: bootstrap pending. Kraków: nothing."""
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    sm = async_sessionmaker(engine, expire_on_commit=False)
    corpus = PgCorpus(sm)
    await corpus.ensure_catalogue(catalogue())
    await ingest(
        corpus, "r-torun", IDS["toruń"], [o.model_copy(update={"location_id": "torun"}) for o in twelve(100)]
    )
    await ingest(
        corpus,
        "r-gdynia",
        IDS["gdynia"],
        [o.model_copy(update={"location_id": "gdynia"}) for o in twelve(200)[:3]],
    )
    for loc in ("torun", "gdynia"):  # a nightly refresh two hours before NOW keeps both places fresh
        await ingest(
            corpus, f"n-{loc}", loc, [], seen=NOW - timedelta(hours=2), mode=RunMode.incremental, start=BOOT
        )
    history = PgMarketHistory(sm)
    app.state.clock = lambda: NOW
    for loc in ("torun", "gdynia"):
        await history.publish_day(loc, NOW.date(), now=NOW, summarise=summarise_asking)
    yield history
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def get(c: Any, path: str, **params: Any) -> Any:
    return await c.get(path, params=params)


async def test_every_market_route_needs_a_session(app: FastAPI, market: PgMarketHistory) -> None:
    async with client_for(app) as c:
        for path in (
            "/api/market/locations",
            "/api/market/locations/torun",
            "/api/market/locations/torun/history",
        ):
            r = await c.get(path)
            assert r.status_code == 401, path
            assert r.json()["code"] == "UNAUTHENTICATED"


async def test_detail_shows_exact_figures_with_provenance(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    r = await get(c, "/api/market/locations/torun")
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["name"], body["data_status"], body["usable_for_ranking"]) == ("Toruń", "fresh", True)
    everything = next(o for o in body["cohort"] if o["cohort_key"] == "all")
    # by hand: median of 2000..2550 step 50 = 2275; PLN/m2 40..51: median 45.5, quartiles 42.75 / 48.25
    assert everything["median_rent_pln"] == "2275.00"
    assert (everything["median_ppm2"], everything["p25_ppm2"], everything["p75_ppm2"]) == (
        "45.50",
        "42.75",
        "48.25",
    )
    assert (everything["priced_count"], everything["observed_count"], everything["sufficient"]) == (
        12,
        12,
        True,
    )
    assert everything["withheld_reason"] is None
    assert (everything["price_basis"], everything["source"], everything["series"]) == (
        "asking",
        "otodom",
        "cohort",
    )
    assert set(everything["caveats"]) == {"asking_not_achieved_rent", "not_active_stock", "not_deed_price"}
    assert everything["summary_date"] == "2026-10-19"


async def test_an_insufficient_sample_keeps_counts_and_withholds_statistics(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await get(c, "/api/market/locations/gdynia")).json()
    everything = next(o for o in body["cohort"] if o["cohort_key"] == "all")
    assert everything["priced_count"] == 3
    assert everything["sufficient"] is False
    assert everything["withheld_reason"] == "insufficient_sample"
    assert everything["median_rent_pln"] is None  # never zero
    assert everything["median_ppm2"] is None
    assert body["usable_for_ranking"] is False


async def test_pending_bootstrap_is_unavailable_with_no_rows_and_an_unknown_place_is_404(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await get(c, "/api/market/locations/gdansk")).json()
    assert (body["data_status"], body["cohort"], body["last_successful_refresh_at"]) == (
        "unavailable",
        [],
        None,
    )
    for path in ("/api/market/locations/nowhere", "/api/market/locations/nowhere/history"):
        r = await get(c, path)
        assert (r.status_code, r.json()["code"]) == (404, "NOT_FOUND")
    assert (await get(c, "/api/market/locations/NOT%20VALID")).status_code == 422


async def test_freshness_follows_the_clock(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    expected = {
        NOW + timedelta(hours=1): "fresh",
        NOW + timedelta(hours=40): "delayed",
        NOW + timedelta(hours=80): "stale",
    }
    for at, status in expected.items():
        app.state.clock = lambda at=at: at
        assert (await get(c, "/api/market/locations/torun")).json()["data_status"] == status
        listed = (await get(c, "/api/market/locations", q="toru")).json()["items"]
        assert [(i["location_id"], i["data_status"]) for i in listed] == [("torun", status)]


async def test_list_is_ordered_by_name_and_shows_each_place_honestly(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await get(c, "/api/market/locations")).json()
    assert body["next_cursor"] is None
    by_id = {i["location_id"]: i for i in body["items"]}
    assert [i["name"] for i in body["items"]] == sorted(PLACES.values())
    assert by_id["torun"]["median_rent_pln"] == "2275.00"
    assert by_id["torun"]["priced_count"] == 12
    assert by_id["gdynia"]["median_rent_pln"] is None
    assert by_id["gdynia"]["withheld_reason"] == "insufficient_sample"
    assert by_id["gdansk"]["data_status"] == "unavailable"
    assert by_id["gdansk"]["priced_count"] is None
    assert by_id["krakow"]["latest_summary_date"] is None


async def test_search_is_a_literal_substring_and_paging_never_repeats_or_skips(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    assert [i["location_id"] for i in (await get(c, "/api/market/locations", q="gd")).json()["items"]] == [
        "gdansk",
        "gdynia",
    ]
    for wildcard in ("%", "_", "\\"):
        assert (await get(c, "/api/market/locations", q=wildcard)).json()["items"] == []
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        body = (
            await get(c, "/api/market/locations", limit=1, **({"cursor": cursor} if cursor else {}))
        ).json()
        seen += [i["location_id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == sorted(IDS.values())
    assert len(seen) == 4


@pytest.mark.parametrize("cursor", ["garbage", base64.urlsafe_b64encode(b"[1,2]").decode()])
async def test_a_bad_cursor_and_out_of_range_limits_are_422(
    app: FastAPI, market: PgMarketHistory, engine: AsyncEngine, make_google_token: MakeToken, cursor: str
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    assert (await get(c, "/api/market/locations", cursor=cursor)).status_code == 422
    for limit in (0, 101):
        assert (await get(c, "/api/market/locations", limit=limit)).status_code == 422


async def test_history_is_oldest_first_gaps_stay_absent_and_series_never_mix(
    app: FastAPI,
    engine: AsyncEngine,
    market: PgMarketHistory,
    make_google_token: MakeToken,
) -> None:
    for back in (1, 3):  # two backfilled days; days between stay unpublished
        day = NOW.date() - timedelta(days=back)
        await market.publish_day("torun", day, now=NOW, summarise=summarise_asking)
    c, _ = await make_admin(app, engine, make_google_token)
    r = await get(c, "/api/market/locations/torun/history", days=7)
    assert r.status_code == 200, r.text
    body = r.json()
    dates = [p["summary_date"] for p in body["points"]]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))
    assert dates == [
        "2026-10-16",
        "2026-10-18",
        "2026-10-19",
    ]  # the 17th was never published: absent, not zero
    assert {p["series"] for p in body["points"]} == {"cohort"}
    assert (body["start"], body["end"]) == ("2026-10-13", "2026-10-19")
    additions = (await get(c, "/api/market/locations/torun/history", series="additions", days=7)).json()
    assert {p["series"] for p in additions["points"]} <= {"additions"}
    rooms = (await get(c, "/api/market/locations/torun/history", cohort="rooms_2", days=7)).json()
    assert rooms["cohort_key"] == "rooms_2"
    assert {p["cohort_key"] for p in rooms["points"]} == {"rooms_2"}


@pytest.mark.parametrize(
    "params", [{"series": "deed"}, {"days": 0}, {"days": 400}, {"cohort": "ALL"}, {"cohort": "x" * 17}]
)
async def test_history_rejects_unsupported_selections(
    app: FastAPI,
    market: PgMarketHistory,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    params: dict[str, Any],
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    r = await get(c, "/api/market/locations/torun/history", **params)
    assert (r.status_code, r.json()["code"]) == (422, "VALIDATION_ERROR")


# --- the free tier sees a fixed top list, everything else is closed (RM-282, #43) --------------------------


async def test_a_free_account_sees_only_places_with_a_sufficient_sample_and_cannot_reach_the_rest(
    app: FastAPI, market: PgMarketHistory, make_google_token: MakeToken
) -> None:
    c, _ = await sign_in(app, make_google_token)  # a new verified account: no pack, no Pro
    listed = (await get(c, "/api/market/locations")).json()["items"]
    assert [i["location_id"] for i in listed] == ["torun"]  # Gdynia has 3 priced offers, Gdańsk is pending
    assert (await get(c, "/api/market/locations/torun")).status_code == 200
    for path in (  # a direct id reaches nothing outside the list, whatever the route
        "/api/market/locations/gdynia",
        "/api/market/locations/gdynia/history",
        "/api/market/locations/gdynia/context",
        "/api/market/locations/gdansk",
    ):
        r = await get(c, path)
        assert (r.status_code, r.json()["code"]) == (403, "FEATURE_NOT_IN_PLAN"), path
        assert r.json()["upgrade_url"] == "/app/credits"
    assert (await get(c, "/api/market/locations/nowhere")).status_code == 404  # unknown stays unknown
    searched = (await get(c, "/api/market/locations", q="gdy")).json()["items"]
    assert searched == []  # a search term cannot reach a closed place
    overview = (await get(c, "/api/market/overview")).json()
    assert (overview["access"], overview["total_places"], overview["visible_places"]) == ("free", 4, 1)
    assert [i["location_id"] for i in overview["items"]] == ["torun"]
    assert overview["free_limit"] == 20


async def test_the_free_list_is_capped_at_twenty_for_every_route_and_cursor(
    app: FastAPI, engine: AsyncEngine, market: PgMarketHistory, make_google_token: MakeToken
) -> None:
    """Twenty-five places with sufficient samples of 10..34 priced offers: the 20 deepest stay, five close."""
    sm = async_sessionmaker(engine, expire_on_commit=False)
    corpus = PgCorpus(sm)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES}"))
    entries = [
        LocationEntry(location_id=f"p{i:02d}", name=f"Miejsce {i:02d}", otodom_path=f"cala-polska/p{i:02d}")
        for i in range(25)
    ]
    await corpus.ensure_catalogue(LocationCatalogue.build(1, "cap-test", entries))
    for i, e in enumerate(entries):
        rows = [
            obs(str(10_000 * (i + 1) + k), rent=str(2000 + k), area="50", rooms=2).model_copy(
                update={"location_id": e.location_id}
            )
            for k in range(10 + i)
        ]
        await ingest(corpus, f"r{i}", e.location_id, rows)
        await ingest(
            corpus,
            f"n{i}",
            e.location_id,
            [],
            seen=NOW - timedelta(hours=2),
            mode=RunMode.incremental,
            start=BOOT,
        )
        await market.publish_day(e.location_id, NOW.date(), now=NOW, summarise=summarise_asking)
    deepest = {f"p{i:02d}" for i in range(5, 25)}  # sample size grows with i: p00..p04 are the shallowest

    free, _ = await sign_in(app, make_google_token)
    seen: list[str] = []
    cursor: str | None = None
    while True:  # paging cannot exceed the cap: the filter is in the query, not in the page size
        page = (
            await get(free, "/api/market/locations", limit=7, **({"cursor": cursor} if cursor else {}))
        ).json()
        seen += [i["location_id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert set(seen) == deepest
    assert len(seen) == 20
    overview = (await get(free, "/api/market/overview")).json()
    assert {i["location_id"] for i in overview["items"]} == deepest
    assert (overview["total_places"], overview["visible_places"]) == (25, 20)
    for closed in ("p00", "p04"):
        for suffix in ("", "/history", "/context"):
            assert (await get(free, f"/api/market/locations/{closed}{suffix}")).status_code == 403
    assert (await get(free, "/api/market/locations/p05/history")).status_code == 200

    paid, _ = await make_admin(app, engine, make_google_token)  # full access: same routes, nothing closed
    full = (await get(paid, "/api/market/overview")).json()
    assert (full["access"], full["visible_places"]) == ("full", 25)
    assert (await get(paid, "/api/market/locations/p00")).status_code == 200
    all_pages: list[str] = []
    cursor = None
    while True:
        page = (
            await get(paid, "/api/market/locations", limit=10, **({"cursor": cursor} if cursor else {}))
        ).json()
        all_pages += [i["location_id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(all_pages) == 25


async def test_context_for_an_unmapped_place_says_so_and_never_invents_numbers(
    app: FastAPI, engine: AsyncEngine, market: PgMarketHistory, make_google_token: MakeToken
) -> None:
    c, _ = await make_admin(app, engine, make_google_token)
    body = (await get(c, "/api/market/locations/torun/context")).json()
    assert body["mapping"] == {
        "status": "unmatched",
        "relation": None,
        "method": "not_mapped",
        "candidates": [],
    }
    assert (body["chain"], body["metrics"], body["published_metrics"]) == ([], [], 0)
    assert body["source"]["name"] == "GUS BDL"
