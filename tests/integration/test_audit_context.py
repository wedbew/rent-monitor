# ruff: noqa: F811  (the `h` fixture is imported from test_audit_journey and used as a parameter)
"""The real listing source and market context behind the S1 protocols (#187, blueprint §2 `fetch`, `context`).

Real: the API, Postgres, the Procrastinate worker, the engine child, the Otodom client with its Postgres slot
and breaker policy, the comparable-rent store and `estimate_rent`. Faked, by name: the HTTP transport (an
Otodom-shaped page built by hand, no seller data) and the rental sidecar rows (hand-built). This proves the
adapters work offline end to end; it is NOT live-provider evidence (docs/STATUS.md level 3).
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from deal_analyzer import analyse_listing, extract_listing
from deal_analyzer.rent import RentComparable, estimate_rent
from rm_core.comparables import StoredComparable, city_slug, replace_comparables
from rm_core.db.models import AuditStatus, ChargeState, MarketSidecar, SidecarKind
from rm_core.settings import Settings
from rm_worker.audit_pipeline import AuditServices
from rm_worker.audit_wiring import build_audit_services
from rm_worker.clients.otodom import OtodomClient, RawResponse
from rm_worker.clients.otodom_policy import PostgresHostPolicy
from rm_worker.context import MarketContext
from rm_worker.engine_child import ChildEngine
from rm_worker.listing_source import GatedListingSource
from sqlalchemy import delete, select
from test_audit_journey import (  # noqa: F401  (fixtures: `h`, the autouse `clean_up`)
    SIGNUP_CREDITS,
    Harness,
    clean_up,
    h,
    new_ref,
    sale_ad,
    submit,
)
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
RISK_FREE = Decimal("0.055")
CITY = "Testowo"  # sale_ad's city
SIDECAR_STEM = "otodom_rental-testowo-recorded-test"


@dataclass
class FakeTransport:
    """Returns a hand-built Otodom page for whichever listing id the URL names."""

    ads: dict[str, dict[str, Any]]
    urls: list[str] = field(default_factory=list[str])

    async def get(self, url: str, *, headers: dict[str, str], total_s: float) -> RawResponse:
        self.urls.append(url)
        ad = self.ads[url.rsplit("/", 1)[-1]]
        data = {"props": {"pageProps": {"ad": ad}}}
        body = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'
        return RawResponse(200, {}, body.encode(), url)


@pytest.fixture
async def rental_sidecar(h: Harness) -> AsyncIterator[list[StoredComparable]]:
    """Six hand-built asking rents for Testowo (PLN/m2 60..65), removed again afterwards."""
    rows = [StoredComparable(Decimal(p * 48), Decimal(48)) for p in (60, 61, 62, 63, 64, 65)]
    async with h.sm() as s, s.begin():
        sc = MarketSidecar(
            kind=SidecarKind.otodom_rental,
            price_basis="rent",
            city_slug=city_slug(CITY),
            period=date(2026, 10, 1),
            size_bucket="30-50",
            source_stem=SIDECAR_STEM,
            sha256="d" * 64,
            payload={},
            generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
        s.add(sc)
        await s.flush()
        await replace_comparables(s, sc.id, rows)
    yield rows
    async with h.sm() as s, s.begin():
        await s.execute(delete(MarketSidecar).where(MarketSidecar.source_stem == SIDECAR_STEM))


def real_services(
    h: Harness, transport: FakeTransport, *, enabled: bool = True, risk_free: Decimal | None = RISK_FREE
) -> AuditServices:
    policy = PostgresHostPolicy(h.sm, timedelta(milliseconds=1))
    client = OtodomClient(transport=transport, slots=policy, breaker=policy)
    return AuditServices(
        sessionmaker=h.sm,
        source=GatedListingSource(client, enabled=enabled),
        context=MarketContext(h.sm, risk_free=risk_free),
        timeout_s=60.0,
        engine=ChildEngine(),
    )


# ------------------------------------------------------------------------------ helpers
def test_city_slug_is_one_stable_ascii_spelling() -> None:
    assert city_slug("Łódź") == "lodz"
    assert city_slug("Kraków") == "krakow"
    assert city_slug("  Bielsko-Biała ") == "bielsko-biala"
    assert city_slug("Gorzów Wielkopolski") == "gorzow-wielkopolski"
    assert city_slug("Testowo") == city_slug("TESTOWO") == "testowo"


# ------------------------------------------------------------------------------ the journey
async def test_real_adapters_produce_the_result_the_stored_comparables_imply(
    h: Harness, make_google_token: Any, rental_sidecar: list[StoredComparable]
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    transport = FakeTransport({ref: sale_ad()})
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker(services=real_services(h, transport))

    got = (await c.get(f"/api/audits/{audit_id}")).json()
    assert got["status"] == "succeeded_degraded"
    assert got["charge_state"] == "captured"
    assert transport.urls == [
        f"https://www.otodom.pl/pl/oferta/{ref}"
    ]  # only the parsed short id is requested

    estimate = estimate_rent(
        Decimal("48.5"),
        [RentComparable(monthly_rent_pln=r.monthly_rent_pln, area_m2=r.area_m2) for r in rental_sidecar],
    )
    expected = analyse_listing(extract_listing(sale_ad()), rent=estimate.to_input(), risk_free=RISK_FREE)
    assert got["result"] == expected.model_dump(mode="json")  # the engine's own numbers, from stored rents
    assert estimate.to_input().basis == "asking"  # invariant 2: rents are asking, never deed
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
    await h.assert_ledger_consistent()


async def test_a_city_without_comparables_gets_the_engines_refused_rent_not_an_invented_one(
    h: Harness, make_google_token: Any
) -> None:
    c, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker(services=real_services(h, FakeTransport({ref: sale_ad()})))
    got = (await c.get(f"/api/audits/{audit_id}")).json()
    assert got["status"] in {"succeeded", "succeeded_degraded"}
    expected = analyse_listing(
        extract_listing(sale_ad()), rent=estimate_rent(Decimal("48.5"), []).to_input(), risk_free=RISK_FREE
    )
    assert got["result"] == expected.model_dump(mode="json")
    assert "rent_refused_too_few_comparables" in json.dumps(
        got["result"]
    )  # the refusal is visible, not hidden


# ------------------------------------------------------------------------------ failures release the credit
@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"enabled": False}, AuditStatus.failed_upstream, "UPSTREAM_BLOCKED"),
        ({"risk_free": None}, AuditStatus.failed_internal, "CONTEXT_UNAVAILABLE"),
    ],
    ids=["scraping-switched-off", "risk-free-rate-unset"],
)
async def test_a_missing_input_or_the_kill_switch_fails_the_audit_and_releases_the_credit(
    h: Harness, make_google_token: Any, kwargs: dict[str, Any], status: AuditStatus, code: str
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    transport = FakeTransport({ref: sale_ad()})
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker(services=real_services(h, transport, **kwargs))
    got = await h.audit(audit_id)
    assert (got.status, got.error_code, got.charge_state) == (status, code, ChargeState.released)
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    if "enabled" in kwargs:
        assert transport.urls == []  # the switch stops the request itself
    await h.assert_ledger_consistent()


async def test_a_listing_without_a_city_cannot_be_anchored(h: Harness, make_google_token: Any) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    ad = sale_ad()
    ad["location"] = {"coordinates": ad["location"]["coordinates"], "address": {}}
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker(services=real_services(h, FakeTransport({ref: ad})))
    got = await h.audit(audit_id)
    assert (got.status, got.error_code, got.charge_state) == (
        AuditStatus.failed_internal,
        "CONTEXT_UNAVAILABLE",
        ChargeState.released,
    )
    assert await h.balance(me["id"]) == SIGNUP_CREDITS


# ------------------------------------------------------------------------------ wiring from settings
async def test_the_worker_builds_real_services_only_when_asked(migrated_url: str) -> None:
    base: dict[str, Any] = {"app_env": "test", "database_url": migrated_url}
    assert build_audit_services(Settings(**base)) is None  # default: fail closed, no half-configured host
    services = build_audit_services(Settings(**base, audit_providers="real", risk_free_rate=RISK_FREE))
    assert services is not None
    assert isinstance(services.source, GatedListingSource)
    assert isinstance(services.context, MarketContext)
    assert isinstance(services.engine, ChildEngine)
    assert services.timeout_s == 900.0
    async with services.sessionmaker() as s:
        assert await s.scalar(select(1)) == 1  # the worker's own connection pool is live
    await services.sessionmaker.kw["bind"].dispose()
