"""The P0 journey, offline (docs/STATUS.md): sign in -> submit a sale listing -> reserve a credit -> queue ->
acquire context -> run the engine -> persist and retrieve the canonical result.

Real: the FastAPI app, session auth, Postgres, the credit ledger, Procrastinate (the API defers, a real worker
processes the `audit` queue) and the deterministic engine. Faked, by name: the listing source (`FakeSource`)
and the market context (`FakeContext`). So this proves level 2 (integrated, offline), not that Otodom, market
data or any vendor works (docs/STATUS.md levels 3 and 4).
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import procrastinate
import pytest
from asgi_lifespan import LifespanManager
from deal_analyzer import RentInput, analyse_listing, extract_listing
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_api.queue import ProcrastinateEmailQueue
from rm_contracts.jobs import AUDIT_QUEUE
from rm_core.db.models import Audit, AuditStatus, ChargeState, CreditAccount, CreditLedger
from rm_core.deadline import Deadline
from rm_core.ledger import admin_adjust, ledger_mismatches
from rm_core.settings import Settings
from rm_core.snapshots import FetchedListing, content_hash
from rm_worker import audit_services
from rm_worker.app import app as worker_app
from rm_worker.audit_pipeline import AuditServices, execute_audit
from rm_worker.clients.otodom import ListingGone, UpstreamBlocked
from rm_worker.engine_child import EngineRunner
from rm_worker.tasks import audit as audit_task  # also registers run_audit on the worker app
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from test_auth import FakeCerts, FakeQueue, client_for
from test_me_saved_admin import sign_in

pytestmark = [pytest.mark.integration]
MakeToken = Callable[..., str]
RENT = RentInput(monthly_rent_pln=Decimal("2600"), basis="asking", comparables=14)
RISK_FREE = Decimal("0.055")
SIGNUP_CREDITS = 3  # Settings.free_signup_credits


def sale_ad(**overrides: Any) -> dict[str, Any]:
    """A hand-built, anonymised SALE ad (no real seller data)."""
    ad: dict[str, Any] = {
        "id": 90000001,
        "title": "Mieszkanie 2 pokoje, Testowo",
        "description": "Jasne mieszkanie na drugim piętrze. Cisza, spokój, blisko komunikacji.",
        "createdAt": "2026-09-01T10:00:00Z",
        "modifiedAt": "2026-10-01T08:30:00Z",
        "adCategory": {"type": "SELL"},
        "characteristics": [
            {"key": "price", "value": "450000"},
            {"key": "m", "value": "48.5"},
            {"key": "rooms_num", "value": "2"},
            {"key": "rent", "value": "600"},
            {"key": "floor_no", "value": "2"},
            {"key": "building_floors_num", "value": "5"},
            {"key": "build_year", "value": "1998"},
        ],
        "location": {
            "coordinates": {"latitude": 52.2297, "longitude": 21.0122},
            "address": {"city": {"name": "Testowo"}, "street": {"name": "Przykładowa", "number": "1"}},
        },
    }
    ad.update(deepcopy(overrides))
    return ad


class FakeSource:
    """Offline listing source. A value may be an ad, or an exception to raise, or a coroutine function."""

    def __init__(self) -> None:
        self.ads: dict[str, Any] = {}
        self.calls: list[str] = []
        self.delay_s = 0.0

    async def fetch_listing(
        self, short_id: str, *, deadline: Deadline, priority: str = "interactive"
    ) -> FetchedListing:
        self.calls.append(short_id)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        ad = self.ads[short_id]
        if isinstance(ad, Exception):
            raise ad
        return FetchedListing(
            otodom_id=short_id, url=f"https://fake.test/{short_id}", ad=ad, content_sha256=content_hash(ad)
        )


class FakeContext:
    """Offline market context. Records calls so a test can prove none was made."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail: Exception | None = None

    async def rent_input(self, listing: Any, *, deadline: Deadline) -> RentInput:
        self.calls.append("rent_input")
        if self.fail is not None:
            raise self.fail
        return RENT

    async def risk_free_rate(self, *, deadline: Deadline) -> Decimal:
        self.calls.append("risk_free_rate")
        return RISK_FREE


class Harness:
    def __init__(
        self, app: FastAPI, engine: AsyncEngine, dsn: str, source: FakeSource, ctx: FakeContext
    ) -> None:
        self.app, self.engine, self.dsn, self.source, self.ctx = app, engine, dsn, source, ctx
        self.sm = async_sessionmaker(engine, expire_on_commit=False)

    def services(self, *, timeout_s: float = 30.0, engine: EngineRunner | None = None) -> AuditServices:
        extra = {} if engine is None else {"engine": engine}
        return AuditServices(
            sessionmaker=self.sm, source=self.source, context=self.ctx, timeout_s=timeout_s, **extra
        )

    async def run_worker(self, *, timeout_s: float = 30.0, engine: EngineRunner | None = None) -> None:
        """Process every todo job on the `audit` queue with the real Procrastinate worker, then return."""
        audit_services.configure(self.services(timeout_s=timeout_s, engine=engine))
        connector = procrastinate.PsycopgConnector(conninfo=self.dsn, min_size=1, max_size=3)
        try:
            with worker_app.replace_connector(connector) as app:
                async with app.open_async():
                    await app.run_worker_async(
                        queues=[AUDIT_QUEUE], wait=False, install_signal_handlers=False, listen_notify=False
                    )
        finally:
            audit_services.configure(None)

    async def audit(self, audit_id: str) -> Audit:
        async with self.sm() as s:
            return (await s.execute(select(Audit).where(Audit.id == UUID(audit_id)))).scalar_one()

    async def balance(self, user_id: str) -> int:
        async with self.sm() as s:
            return int(
                await s.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == user_id)) or 0
            )

    async def ledger_rows(self, audit_id: str) -> list[str]:
        async with self.sm() as s:
            rows = await s.scalars(
                select(CreditLedger.reason)
                .where(CreditLedger.audit_id == UUID(audit_id))
                .order_by(CreditLedger.id)
            )
            return [r.value for r in rows]

    async def assert_ledger_consistent(self) -> None:
        async with self.sm() as s:
            assert await ledger_mismatches(s) == []

    async def audit_job_count(self) -> int:
        async with self.engine.connect() as conn:
            return int(
                await conn.scalar(text("SELECT count(*) FROM procrastinate_jobs WHERE queue_name = 'audit'"))
            )


REFS: list[str] = []  # listings this module created, so its snapshots can be removed again


@pytest.fixture(autouse=True)
async def clean_up(engine: AsyncEngine, procrastinate_schema: None) -> AsyncIterator[None]:
    """The database is shared by the whole session: leave no audit jobs or snapshots behind (others count
    snapshot rows)."""

    async def wipe_jobs() -> None:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM procrastinate_jobs WHERE queue_name = 'audit'"))

    await wipe_jobs()
    REFS.clear()
    yield
    await wipe_jobs()
    async with engine.begin() as conn:
        refs = list(REFS)
        await conn.execute(  # progress events are shared global state too (another module counts them)
            text(
                "DELETE FROM app.audit_event WHERE audit_id IN"
                " (SELECT id FROM app.audit WHERE otodom_id = ANY(:r))"
            ),
            {"r": refs},
        )
        await conn.execute(
            text("UPDATE app.audit SET snapshot_id = NULL WHERE otodom_id = ANY(:r)"), {"r": refs}
        )
        await conn.execute(text("DELETE FROM app.listing_snapshot WHERE otodom_id = ANY(:r)"), {"r": refs})


@pytest.fixture
async def h(migrated_url: str, engine: AsyncEngine, google_keys: GoogleKeys) -> AsyncIterator[Harness]:
    dsn = migrated_url.replace("postgresql+psycopg://", "postgresql://", 1)
    settings = Settings(
        app_env="test",
        database_url=migrated_url,
        public_app_url="https://app.test",
        google_client_id=GOOGLE_AUDIENCE,
        free_signup_credits=SIGNUP_CREDITS,
    )
    queue = ProcrastinateEmailQueue(
        procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=dsn, min_size=1, max_size=2))
    )
    verifier = GoogleVerifier(GOOGLE_AUDIENCE, FakeCerts(google_keys.certs))
    application = create_app(settings, email_queue=FakeQueue(), audit_queue=queue, google_verifier=verifier)
    async with LifespanManager(application):
        await asyncio.wait_for(application.state.notify_listener.listening.wait(), 10)
        try:
            yield Harness(application, engine, dsn, FakeSource(), FakeContext())
        finally:
            await queue.close()


def new_ref() -> str:
    ref = "ID" + uuid4().hex[:8].upper()
    REFS.append(ref)
    return ref


async def submit(c: Any, ref: str, **body: Any) -> Any:
    return await c.post("/api/audits", json={"listing_ref": ref, **body})


# ---------------------------------------------------------------- success
async def test_a_signed_in_user_gets_a_persisted_canonical_result(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    assert await h.balance(me["id"]) == SIGNUP_CREDITS

    r = await submit(c, f"https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-testowo-{ref}")
    assert r.status_code == 202, r.text
    accepted = r.json()
    assert accepted["status"] == "queued"
    assert accepted["credits_remaining"] == SIGNUP_CREDITS - 1
    audit_id = accepted["audit_id"]
    assert accepted["events_url"] == f"/api/audits/{audit_id}/events"

    queued = await c.get(f"/api/audits/{audit_id}")  # reserved, nothing computed yet
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    assert queued.json()["charge_state"] == "reserved"
    assert queued.json()["result"] is None
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
    assert await h.audit_job_count() == 1

    await h.run_worker()

    done = (await c.get(f"/api/audits/{audit_id}")).json()
    assert done["status"] == "succeeded_degraded"  # no vision in this slice: the engine says so itself
    assert done["error_code"] == "VISION_UNAVAILABLE"
    assert done["charge_state"] == "captured"
    assert done["started_at"]
    assert done["finished_at"]
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1  # captured: stays spent
    assert await h.ledger_rows(audit_id) == ["reserve"]
    await h.assert_ledger_consistent()

    # The API echoes the engine's output; it computes nothing (invariant 4).
    expected = analyse_listing(extract_listing(sale_ad()), rent=RENT, risk_free=RISK_FREE)
    assert done["result"] == expected.model_dump(mode="json")
    assert done["result"]["schema_version"] == 1
    val = done["result"]["valuation"]
    assert done["grade"] == val["grade"]
    assert Decimal(done["asking_price_pln"]) == Decimal(val["asking_price_pln"]) == Decimal("450000")
    assert Decimal(done["max_bid_pln"]) == Decimal(val["max_bid_pln"])
    assert Decimal(done["irr_10y"]) == Decimal(done["result"]["cash_flow"]["returns"]["irr"])
    assert Decimal(done["capex_pln"]) == Decimal(done["result"]["capex_used_pln"])
    assert h.ctx.calls == ["rent_input", "risk_free_rate"]

    listed = (await c.get("/api/audits")).json()
    assert [row["audit_id"] for row in listed] == [audit_id]
    assert "result" not in listed[0]


async def test_two_users_auditing_one_listing_cost_one_fetch(
    h: Harness, make_google_token: MakeToken
) -> None:
    a, _ = await sign_in(h.app, make_google_token)
    b, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    for c in (a, b):
        assert (await submit(c, ref)).status_code == 202
    await h.run_worker()
    assert h.source.calls == [ref]  # the 6 h cross-tenant snapshot (LEGAL[scraping]) served the second audit


# ---------------------------------------------------------------- duplicates
async def test_a_duplicate_submission_is_refused_and_charged_once(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    first = (await submit(c, ref)).json()["audit_id"]

    again = await submit(c, ref)
    assert again.status_code == 409
    assert again.json()["code"] == "AUDIT_IN_PROGRESS"
    assert again.json()["audit_id"] == first
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
    assert await h.audit_job_count() == 1

    await h.run_worker()
    await h.assert_ledger_consistent()
    assert (await submit(c, ref)).status_code == 202  # once finished, analysing again is a new, paid audit
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 2


async def test_simultaneous_submissions_of_one_listing_admit_exactly_one(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    results = await asyncio.gather(*(submit(c, ref) for _ in range(6)))
    assert sorted(r.status_code for r in results) == [202, 409, 409, 409, 409, 409]
    async with h.sm() as s:
        assert await s.scalar(select(func.count()).select_from(Audit).where(Audit.user_id == me["id"])) == 1
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
    await h.assert_ledger_consistent()


async def test_a_delivered_job_runs_the_engine_once(h: Harness, make_google_token: MakeToken) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    audit_id = UUID((await submit(c, ref)).json()["audit_id"])
    services = h.services()
    outcomes = await asyncio.gather(
        *(execute_audit(services, audit_id) for _ in range(5))
    )  # duplicate delivery
    assert [o for o in outcomes if o is not None] == [AuditStatus.succeeded_degraded]
    assert h.source.calls == [ref]
    assert await execute_audit(services, audit_id) is None  # a late redelivery is a no-op
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1
    await h.assert_ledger_consistent()


# ---------------------------------------------------------------- quota and input
async def test_with_no_credit_left_nothing_is_created_or_queued(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    async with h.sm() as s, s.begin():
        await admin_adjust(s, me["id"], -SIGNUP_CREDITS, key=f"drain:{me['id']}", note="test")
    r = await submit(c, new_ref())
    assert r.status_code == 402
    assert r.json()["code"] == "QUOTA_EXHAUSTED"
    assert r.json()["upgrade_url"] == "/billing"
    async with h.sm() as s:
        assert await s.scalar(select(func.count()).select_from(Audit).where(Audit.user_id == me["id"])) == 0
    assert await h.audit_job_count() == 0
    assert await h.balance(me["id"]) == 0


async def test_bad_requests_are_refused_before_any_charge(h: Harness, make_google_token: MakeToken) -> None:
    c, me = await sign_in(h.app, make_google_token)
    assert (await submit(c, "https://evil.example/pl/oferta/x-ID4CpHB")).json()[
        "code"
    ] == "INVALID_LISTING_REF"
    assert (await submit(c, "http://169.254.169.254/latest/meta-data")).status_code == 422
    assert (await c.post("/api/audits", json={"listing_ref": new_ref(), "surprise": 1})).status_code == 422
    analyst = await submit(c, new_ref(), analyst=True)
    assert (analyst.status_code, analyst.json()["code"]) == (403, "FEATURE_NOT_IN_PLAN")
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    assert await h.audit_job_count() == 0


async def test_every_audit_route_needs_a_session(h: Harness) -> None:
    async with client_for(h.app) as c:
        assert (await submit(c, new_ref())).status_code == 401
        assert (await c.get("/api/audits")).status_code == 401
        assert (await c.get(f"/api/audits/{uuid4()}")).status_code == 401


# ---------------------------------------------------------------- tenant isolation
async def test_another_users_audit_is_a_404_indistinguishable_from_unknown(
    h: Harness, make_google_token: MakeToken
) -> None:
    a, _ = await sign_in(h.app, make_google_token)
    b, _ = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    audit_id = (await submit(a, ref)).json()["audit_id"]
    await h.run_worker()

    foreign, unknown = await b.get(f"/api/audits/{audit_id}"), await b.get(f"/api/audits/{uuid4()}")
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json()["code"] == unknown.json()["code"] == "NOT_FOUND"
    assert (await b.get("/api/audits")).json() == []
    assert (await a.get(f"/api/audits/{audit_id}")).status_code == 200
    # B may analyse the same listing: A's active or finished audit does not block or reveal anything.
    assert (await submit(b, ref)).status_code == 202


# ---------------------------------------------------------------- failure releases the credit
@dataclass(frozen=True)
class Failure:
    name: str
    arrange: Callable[[FakeSource, FakeContext, str], None]
    status: str
    code: str
    context_untouched: bool = False  # RENT / fractional / unusable payloads stop before any market work


def _serve(ad: Any) -> Callable[[FakeSource, FakeContext, str], None]:
    def arrange(src: FakeSource, ctx: FakeContext, ref: str) -> None:
        src.ads[ref] = ad

    return arrange


def _crash(src: FakeSource, ctx: FakeContext, ref: str) -> None:
    src.ads[ref] = sale_ad()
    ctx.fail = RuntimeError("boom")


FAILURES = [
    Failure("rent", _serve(sale_ad(adCategory={"type": "RENT"})), "rejected", "RENT_NOT_DEAL", True),
    Failure(
        "fraction",
        _serve(sale_ad(title="Sprzedam 1/2 udziału w mieszkaniu")),
        "rejected",
        "FRACTIONAL_OWNERSHIP",
        True,
    ),
    Failure("gone", _serve(ListingGone("404")), "failed_input", "LISTING_GONE"),
    Failure(
        "blocked", _serve(UpstreamBlocked("captcha", retryable=False)), "failed_upstream", "UPSTREAM_BLOCKED"
    ),
    Failure(
        "unparseable",
        _serve({"id": 1, "adCategory": {"type": "SELL"}}),
        "failed_upstream",
        "UPSTREAM_SCHEMA_DRIFT",
        True,
    ),
    Failure("crash", _crash, "failed_internal", "INTERNAL"),
]


@pytest.mark.parametrize("case", FAILURES, ids=[f.name for f in FAILURES])
async def test_a_failed_audit_releases_its_credit(
    h: Harness, make_google_token: MakeToken, case: Failure
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    case.arrange(h.source, h.ctx, ref)
    audit_id = (await submit(c, ref)).json()["audit_id"]
    assert await h.balance(me["id"]) == SIGNUP_CREDITS - 1

    await h.run_worker()

    got = (await c.get(f"/api/audits/{audit_id}")).json()
    assert (got["status"], got["error_code"]) == (case.status, case.code)
    assert got["charge_state"] == "released"
    assert got["result"] is None
    assert await h.balance(me["id"]) == SIGNUP_CREDITS  # the user lost nothing
    assert await h.ledger_rows(audit_id) == ["reserve", "release"]
    await h.assert_ledger_consistent()
    if case.context_untouched:
        assert h.ctx.calls == []  # no market or vision work for a listing that is not a deal (invariant 1)


async def test_a_slow_listing_fetch_hits_the_deadline_and_releases_the_credit(
    h: Harness, make_google_token: MakeToken
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = sale_ad()
    h.source.delay_s = 5
    audit_id = (await submit(c, ref)).json()["audit_id"]
    await h.run_worker(timeout_s=0.2)
    got = (await c.get(f"/api/audits/{audit_id}")).json()
    assert (got["status"], got["error_code"], got["charge_state"]) == (
        "failed_internal",
        "TIMEOUT",
        "released",
    )
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    await h.assert_ledger_consistent()


async def test_a_released_charge_is_never_settled_twice(h: Harness, make_google_token: MakeToken) -> None:
    c, me = await sign_in(h.app, make_google_token)
    ref = new_ref()
    h.source.ads[ref] = ListingGone("404")
    audit_id = UUID((await submit(c, ref)).json()["audit_id"])
    await asyncio.gather(*(execute_audit(h.services(), audit_id) for _ in range(4)))
    async with h.sm() as s:
        assert (await _charge_state(s, audit_id)) == ChargeState.released
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    assert await h.ledger_rows(str(audit_id)) == ["reserve", "release"]


async def test_a_worker_without_adapters_fails_closed_and_releases(
    h: Harness, make_google_token: MakeToken, migrated_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    c, me = await sign_in(h.app, make_google_token)
    audit_id = (await submit(c, new_ref())).json()["audit_id"]
    monkeypatch.setattr(
        audit_task, "get_settings", lambda: Settings(app_env="test", database_url=migrated_url)
    )
    connector = procrastinate.PsycopgConnector(conninfo=h.dsn, min_size=1, max_size=3)
    with worker_app.replace_connector(
        connector
    ) as app:  # no audit_services.configure(...): production default
        async with app.open_async():
            await app.run_worker_async(
                queues=[AUDIT_QUEUE], wait=False, install_signal_handlers=False, listen_notify=False
            )
    got = (await c.get(f"/api/audits/{audit_id}")).json()
    assert (got["status"], got["error_code"], got["charge_state"]) == (
        "failed_internal",
        "INTERNAL",
        "released",
    )
    assert await h.balance(me["id"]) == SIGNUP_CREDITS
    await h.assert_ledger_consistent()


async def _charge_state(s: AsyncSession, audit_id: UUID) -> ChargeState:
    return (await s.execute(select(Audit.charge_state).where(Audit.id == audit_id))).scalar_one()


@pytest.fixture(autouse=True)
def _no_services_leak() -> Iterator[None]:
    yield
    audit_services.configure(None)
