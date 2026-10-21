# ruff: noqa: F811  (fixtures `app`, `plans` are imported from test_me_saved_admin)
"""Catalogue and picked products through the API on real Postgres, with the named demo source (RM-449).

The source is a deterministic fake: these tests prove the seam, the freshness states, server-side revalidation
and exact subtotals. They are not evidence about any real merchant feed (B-026).
"""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from rm_contracts.catalogue import Availability
from rm_core.catalogue import DemoCatalogue
from rm_core.db.models import AccountEntitlement
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from test_auth import Browser
from test_me_saved_admin import app, plans, sign_in  # noqa: F401  (fixtures: `app`, `plans`)

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
P = "/api/interior/projects"
BRIEF = {"room_type": "living_room", "budget_pln": "6000"}


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
async def source(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple[DemoCatalogue, Clock]]:
    """The demo source and the server's notion of 'now' move together, so a test can age an observation."""
    clock = Clock()

    async def server_now(_db: object) -> datetime:
        return clock.now

    monkeypatch.setattr("rm_core.interior.db_now", server_now)
    monkeypatch.setattr("rm_api.interior.repo_now", server_now)
    demo = DemoCatalogue(clock=clock)
    previous, app.state.catalogue = app.state.catalogue, demo
    yield demo, clock
    app.state.catalogue = previous


async def entitled(app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken) -> Browser:
    c, me = await sign_in(app, make_google_token)
    async with async_sessionmaker(engine)() as s, s.begin():
        s.add(AccountEntitlement(user_id=me["id"], kind="unlimited_reports", note="test"))
    return c


async def project(c: Browser) -> str:
    return (await c.post(P, json={"name": "Salon", "brief": BRIEF})).json()["project_id"]


async def pick(c: Browser, pid: str, product: str, variant: str, quantity: int = 1):
    return await c.post(
        f"{P}/{pid}/selections",
        json={"provider": "demo", "product_id": product, "variant_id": variant, "quantity": quantity},
    )


async def test_status_search_and_ranking_use_only_the_sources_offers(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    c = await entitled(app, engine, make_google_token)
    status = (await c.get("/api/interior/catalogue")).json()
    assert status == {
        "available": True,
        "provider": "demo",
        "source_label": "Demo (dane przykładowe, nie sklep)",
        "is_demo": True,
    }
    pid = await project(c)
    found = (await c.get(f"{P}/{pid}/catalogue/search", params={"q": "sofa"})).json()
    assert [(f["offer"]["product_id"], f["offer"]["variant_id"]) for f in found] == [
        ("sofa-nordic", "grey"),
        ("sofa-nordic", "beige"),
    ]
    first = found[0]
    assert first["flags"] == ["matches_text"]
    assert first["offer"]["price_pln"] == "2499.00"
    assert first["offer"]["state"] == "fresh"
    assert first["offer"]["image_url"].startswith("/api/interior/catalogue/demo-image/")
    cheap = (await c.get(f"{P}/{pid}/catalogue/search", params={"max_price_pln": "200"})).json()
    assert cheap
    assert all(f["offer"]["price_pln"] is None or Decimal(f["offer"]["price_pln"]) <= 200 for f in cheap)
    assert (await c.get(f"{P}/{pid}/catalogue/search", params={"limit": 99})).status_code == 422


async def test_no_source_connected_is_an_honest_503_and_keeps_the_project(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken
) -> None:
    c = await entitled(app, engine, make_google_token)
    previous, app.state.catalogue = app.state.catalogue, None
    try:
        pid = await project(c)
        assert (await c.get("/api/interior/catalogue")).json()["available"] is False
        r = await c.get(f"{P}/{pid}/catalogue/search")
        assert (r.status_code, r.json()["code"]) == (503, "CATALOGUE_UNAVAILABLE")
        assert (await pick(c, pid, "sofa-nordic", "grey")).status_code == 503
        assert (await c.get(f"{P}/{pid}")).status_code == 200
    finally:
        app.state.catalogue = previous


async def test_the_server_fetches_the_offer_and_the_client_cannot_name_a_price(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    demo, _ = source
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    forged = await c.post(
        f"{P}/{pid}/selections",
        json={"provider": "demo", "product_id": "sofa-nordic", "variant_id": "grey", "price_pln": "1.00"},
    )
    assert forged.status_code == 422
    done = (await pick(c, pid, "sofa-nordic", "grey", 2)).json()
    line = done["selections"][0]
    assert (line["quantity"], line["offer"]["price_pln"], line["line_total_pln"]) == (2, "2499.00", "4998.00")
    assert demo.calls >= 1
    assert done["basket"] == {
        "known_subtotal_pln": "4998.00",
        "priced_lines": 1,
        "unpriced_lines": 0,
        "stale_lines": 0,
        "delivery_known_pln": "149.00",
        "delivery_unknown_lines": 0,
        "complete": True,
    }


@pytest.mark.parametrize(
    ("product", "variant", "code"),
    [("sofa-nordic", "green", "OFFER_UNAVAILABLE"), ("sofa-nordic", "purple", "OFFER_UNAVAILABLE")],
)
async def test_an_unavailable_or_unknown_variant_cannot_be_picked(  # noqa: PLR0917
    app: FastAPI,
    engine: AsyncEngine,
    make_google_token: MakeToken,
    source: tuple[DemoCatalogue, Clock],
    product: str,
    variant: str,
    code: str,
) -> None:
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    r = await pick(c, pid, product, variant)
    assert (r.status_code, r.json()["code"]) == (409, code)
    wrong = await c.post(
        f"{P}/{pid}/selections", json={"provider": "amazon", "product_id": "x", "variant_id": "y"}
    )
    assert (wrong.status_code, wrong.json()["code"]) == (409, "OFFER_UNAVAILABLE")
    assert (await c.get(f"{P}/{pid}")).json()["selections"] == []


async def test_unknown_price_and_delivery_stay_explicit_never_zero(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    await pick(c, pid, "lamp-arc", "white")  # price on request
    await pick(c, pid, "table-oak", "oak-140")  # priced, delivery unknown
    got = (await pick(c, pid, "lamp-arc", "black")).json()  # priced, free delivery
    by_variant = {s["offer"]["variant_id"]: s for s in got["selections"]}
    assert by_variant["white"]["offer"]["price_pln"] is None
    assert by_variant["white"]["line_total_pln"] is None
    assert by_variant["oak-140"]["offer"]["delivery_pln"] is None
    assert by_variant["oak-140"]["offer"]["delivery_known"] is False
    assert got["basket"] == {
        "known_subtotal_pln": "1488.00",
        "priced_lines": 2,
        "unpriced_lines": 1,
        "stale_lines": 0,
        "delivery_known_pln": "0.00",
        "delivery_unknown_lines": 1,
        "complete": False,
    }


async def test_expired_offers_stop_counting_and_refresh_restores_them(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    demo, clock = source
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    sid = (await pick(c, pid, "sofa-nordic", "grey")).json()["selections"][0]["selection_id"]
    clock.now += timedelta(hours=25)  # the observation is now history, not a quote
    stale = (await c.get(f"{P}/{pid}")).json()
    assert stale["selections"][0]["offer"]["state"] == "expired"
    assert stale["selections"][0]["line_total_pln"] is None
    assert (
        stale["basket"]["stale_lines"],
        stale["basket"]["known_subtotal_pln"],
        stale["basket"]["complete"],
    ) == (
        1,
        "0.00",
        False,
    )
    demo.set_price("sofa-nordic", "grey", "2399.00")
    fresh = (await c.post(f"{P}/{pid}/selections/{sid}/refresh")).json()
    assert fresh["selections"][0]["offer"]["state"] == "fresh"
    assert fresh["selections"][0]["offer"]["price_pln"] == "2399.00"  # a new observation, not the old price
    assert fresh["basket"]["known_subtotal_pln"] == "2399.00"


async def test_stock_loss_and_delisting_mark_the_selection_unavailable_but_keep_it(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    demo, _ = source
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    a = (await pick(c, pid, "sofa-nordic", "grey")).json()["selections"][0]["selection_id"]
    b = (await pick(c, pid, "mirror-round", "brass")).json()["selections"][1]["selection_id"]
    demo.set_availability("sofa-nordic", "grey", Availability.out_of_stock)
    demo.remove("mirror-round", "brass")
    first = (await c.post(f"{P}/{pid}/selections/{a}/refresh")).json()
    second = (await c.post(f"{P}/{pid}/selections/{b}/refresh")).json()
    states = {s["offer"]["variant_id"]: s["offer"]["state"] for s in second["selections"]}
    assert states == {"grey": "unavailable", "brass": "unavailable"}
    assert first["selections"][0]["line_total_pln"] is None
    assert second["basket"]["stale_lines"] == 2
    assert second["basket"]["known_subtotal_pln"] == "0.00"
    assert (await c.delete(f"{P}/{pid}/selections/{a}")).status_code == 204
    assert len((await c.get(f"{P}/{pid}")).json()["selections"]) == 1


async def test_a_source_outage_keeps_everything_and_says_503(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    demo, _ = source
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    sid = (await pick(c, pid, "sofa-nordic", "grey")).json()["selections"][0]["selection_id"]
    demo.fail_next = True
    down = await c.post(f"{P}/{pid}/selections/{sid}/refresh")
    assert (down.status_code, down.json()["code"]) == (503, "CATALOGUE_UNAVAILABLE")
    demo.fail_next = True
    assert (await c.get(f"{P}/{pid}/catalogue/search")).status_code == 503
    kept = (await c.get(f"{P}/{pid}")).json()["selections"]
    assert [s["offer"]["price_pln"] for s in kept] == ["2499.00"]


async def test_picking_the_same_variant_again_is_idempotent_and_quantity_is_editable(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    await pick(c, pid, "shelf-ladder", "white", 1)
    again = (await pick(c, pid, "shelf-ladder", "white", 3)).json()
    assert [(s["quantity"], s["line_total_pln"]) for s in again["selections"]] == [(3, "987.00")]
    sid = again["selections"][0]["selection_id"]
    edited = (await c.put(f"{P}/{pid}/selections/{sid}", json={"quantity": 2})).json()
    assert edited["selections"][0]["line_total_pln"] == "658.00"
    assert (await c.put(f"{P}/{pid}/selections/{sid}", json={"quantity": 0})).status_code == 422


async def test_selections_are_bounded_to_thirty_per_project(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    from rm_core.db.models import InteriorSelection  # noqa: PLC0415

    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    first = (await pick(c, pid, "shelf-ladder", "white")).json()["selections"][0]
    async with async_sessionmaker(engine)() as s, s.begin():
        row = await s.get(InteriorSelection, first["selection_id"])
        assert row is not None
        for i in range(29):
            s.add(
                InteriorSelection(
                    user_id=row.user_id,
                    project_id=row.project_id,
                    provider="demo",
                    product_id=f"filler-{i}",
                    variant_id="v",
                    offer=row.offer,
                )
            )
    r = await pick(c, pid, "shelf-ladder", "walnut")
    assert (r.status_code, r.json()["code"], r.json()["reason"]) == (
        409,
        "INTERIOR_LIMIT_REACHED",
        "selections",
    )


async def test_another_user_gets_404_for_every_selection_route(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    a = await entitled(app, engine, make_google_token)
    b = await entitled(app, engine, make_google_token)
    pid = await project(a)
    sid = (await pick(a, pid, "sofa-nordic", "grey")).json()["selections"][0]["selection_id"]
    calls = [
        ("GET", f"{P}/{pid}/catalogue/search", {}),
        (
            "POST",
            f"{P}/{pid}/selections",
            {"json": {"provider": "demo", "product_id": "sofa-nordic", "variant_id": "grey"}},
        ),
        ("PUT", f"{P}/{pid}/selections/{sid}", {"json": {"quantity": 5}}),
        ("DELETE", f"{P}/{pid}/selections/{sid}", {}),
        ("POST", f"{P}/{pid}/selections/{sid}/refresh", {}),
    ]
    for method, path, kw in calls:
        r = await b.request(method, path, **kw)
        assert (r.status_code, r.json()["code"]) == (404, "NOT_FOUND"), (method, path)
    assert (await a.get(f"{P}/{pid}")).json()["selections"][0]["quantity"] == 1


async def test_a_revision_rechecks_offers_and_keeps_what_it_saw(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    demo, clock = source
    c = await entitled(app, engine, make_google_token)
    pid = await project(c)
    await pick(c, pid, "lamp-arc", "black")
    clock.now += timedelta(hours=30)  # the stored observation expired
    demo.set_price("lamp-arc", "black", "179.00")
    saved = (await c.post(f"{P}/{pid}/revisions")).json()
    revision = saved["revisions"][0]
    assert revision["selections"][0]["offer"]["price_pln"] == "179.00"  # re-checked before saving
    assert revision["selections"][0]["offer"]["state"] == "fresh"
    assert revision["basket"]["known_subtotal_pln"] == "179.00"
    demo.set_price("lamp-arc", "black", "99.00")
    sid = saved["selections"][0]["selection_id"]
    await c.post(f"{P}/{pid}/selections/{sid}/refresh")
    later = (await c.get(f"{P}/{pid}")).json()
    assert later["selections"][0]["offer"]["price_pln"] == "99.00"
    assert (
        later["revisions"][0]["selections"][0]["offer"]["price_pln"] == "179.00"
    )  # the revision did not move
    demo.fail_next = True  # an unreachable source does not block saving; states stay honest
    clock.now += timedelta(hours=30)
    second = (await c.post(f"{P}/{pid}/revisions")).json()
    assert second["revisions"][0]["number"] == 2
    assert second["revisions"][0]["selections"][0]["offer"]["state"] == "expired"


async def test_the_demo_picture_is_gated_private_and_demo_only(
    app: FastAPI, engine: AsyncEngine, make_google_token: MakeToken, source: tuple[DemoCatalogue, Clock]
) -> None:
    c = await entitled(app, engine, make_google_token)
    r = await c.get("/api/interior/catalogue/demo-image/sofa-nordic/grey")
    assert (r.status_code, r.headers["content-type"], r.headers["x-content-type-options"]) == (
        200,
        "image/png",
        "nosniff",
    )
    assert r.content.startswith(b"\x89PNG")
    stranger, _ = await sign_in(app, make_google_token)
    assert (await stranger.get("/api/interior/catalogue/demo-image/sofa-nordic/grey")).status_code == 403
    app.state.catalogue = None
    assert (await c.get("/api/interior/catalogue/demo-image/sofa-nordic/grey")).status_code == 404
