"""The system under smoke test: the real API, Postgres, session auth, ledger, Procrastinate worker and engine
child, with named fakes for everything that would leave the machine (#263).

Evidence class: **fake provider data**. The listing source, market context, vision model, Paddle and Google
are in-memory fakes defined here or in `tests/`; nothing in this module says anything about Otodom, a model
or a payment provider (docs/STATUS.md level 3).

One `World` serves two lanes with the same scenarios: pytest (`transport="asgi"`, in-process) and the sample
capture (`transport="tcp"`: a local uvicorn on a loopback port, so the bytes cross a real HTTP connection).
"""

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, Literal
from uuid import UUID, uuid4

import httpx
import procrastinate
import uvicorn
from asgi_lifespan import LifespanManager
from deal_analyzer import Listing, RentInput
from deal_analyzer.vision import VisionOutput
from fastapi import FastAPI
from google_helpers import GOOGLE_AUDIENCE, GoogleKeys, build_keys, sign_token
from listings import SUCCESS, SaleListing, sale_ad, vision_answer
from paddle_fake import FakePaddle
from pydantic import SecretStr
from rm_api.app import create_app
from rm_api.auth.google import GoogleVerifier
from rm_api.auth.passwords import PasswordHasher
from rm_api.auth.sessions import create_session
from rm_api.queue import ProcrastinateEmailQueue
from rm_contracts.jobs import AUDIT_QUEUE
from rm_core.billing_catalog import Catalog, Pack
from rm_core.db.models import (
    AccountEntitlement,
    Audit,
    AuditStatus,
    ChargeSource,
    ChargeState,
    FeatureFlag,
    Plan,
    User,
    UserCredential,
)
from rm_core.db.models import Listing as ListingRow
from rm_core.deadline import Deadline
from rm_core.ledger import admin_adjust, ensure_credit_account
from rm_core.object_store import MemoryObjectStore
from rm_core.paddle import Adjustment
from rm_core.paddle_webhook import sign
from rm_core.risk_free import RiskFreeRate
from rm_core.settings import Settings
from rm_core.snapshots import FetchedListing, content_hash
from rm_worker import audit_services
from rm_worker.app import app as worker_app
from rm_worker.audit_pipeline import AuditServices
from rm_worker.engine_child import ChildEngine
from rm_worker.tasks import audit as _audit_task  # noqa: F401  (registers run_audit on the worker app)
from rm_worker.tasks.billing import run_sweep
from rm_worker.vision_stage import PROMPT_VERSION, VisionAssessment
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

ORIGIN = "https://app.test"
WEBHOOK_SECRET = "pdl_ntfset_smoke"
SIGNUP_CREDITS = 3
LOGIN_PHRASE = "correct-horse-battery-staple-91"
CATALOG = Catalog(
    environment="sandbox",  # test amounts only: the owner has not approved real prices (B-017, #43)
    packs=(
        Pack("reports_1", 1, "pri_smoke_one", 1000),
        Pack("reports_5", 5, "pri_smoke_five", 4000),
        Pack("reports_10", 10, "pri_smoke_ten", 7000),
    ),
)
Transport = Literal["asgi", "tcp"]
REDACTED = "[redacted]"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ----------------------------------------------------------------------------------------------- fakes
class SmokeMail:
    """The job queue for mail: records what would be sent, so a scenario can follow the link."""

    def __init__(self) -> None:
        self.magic_links: list[tuple[str, str]] = []
        self.auth_mail: list[tuple[str, str, str | None]] = []

    async def send_magic_link(self, *, email: str, url: str) -> None:
        self.magic_links.append((email, url))

    async def send_auth_mail(self, *, kind: str, email: str, url: str | None) -> None:
        self.auth_mail.append((kind, email, url))

    async def process_billing_events(self) -> None:
        return None

    def token(self, kind: str, email: str) -> str:
        """The fragment token of the newest `kind` mail to `email` (the link is `<origin>/path#t=<token>`)."""
        for sent_kind, to, url in reversed(self.auth_mail):
            if sent_kind == kind and to == email and url:
                return url.split("#t=", 1)[1]
        msg = f"no {kind} mail to {email}"
        raise LookupError(msg)

    def magic_token(self, email: str) -> str:
        for to, url in reversed(self.magic_links):
            if to == email:
                return url.split("#t=", 1)[1]
        msg = f"no magic link to {email}"
        raise LookupError(msg)


class SmokeCerts:
    def __init__(self, certs: Mapping[str, str]) -> None:
        self.certs = dict(certs)

    async def get(self, *, refresh: bool = False) -> Mapping[str, str]:
        return self.certs


class SmokeSource:
    """Offline listing source. A value is an ad, or an exception to raise."""

    def __init__(self) -> None:
        self.ads: dict[str, Any] = {}

    async def fetch_listing(
        self, short_id: str, *, deadline: Deadline, priority: str = "interactive"
    ) -> FetchedListing:
        ad = self.ads[short_id]
        if isinstance(ad, Exception):
            raise ad
        return FetchedListing(
            otodom_id=short_id, url=f"https://fake.test/{short_id}", ad=ad, content_sha256=content_hash(ad)
        )


class SmokeContext:
    """Offline market context: a rent per m2 that depends on the city, so results differ."""

    PER_M2: ClassVar[dict[str, int]] = {"Warszawa": 68, "Kraków": 61, "Łódź": 42, "Gdańsk": 58, "Toruń": 38}

    async def rent_input(self, listing: Listing, *, deadline: Deadline) -> RentInput:
        per_m2 = self.PER_M2.get(listing.city or "", 45)
        return RentInput(monthly_rent_pln=Decimal(per_m2) * listing.area_m2, basis="asking", comparables=14)

    async def risk_free_rate(self, *, deadline: Deadline) -> RiskFreeRate:
        return RiskFreeRate(rate=Decimal("0.055"), source="setting:RISK_FREE_RATE", as_of=None)


class SmokeVision:
    """Offline vision provider: an answer per listing title, or none (the stage ends degraded)."""

    def __init__(self) -> None:
        self.answers: dict[str, VisionOutput] = {}

    async def assess(
        self, listing: Listing, *, audit_id: UUID, deadline: Deadline
    ) -> VisionAssessment | None:
        answer = self.answers.get(listing.title)
        return None if answer is None else VisionAssessment(answer, "vendor/smoke-model", PROMPT_VERSION)


# ------------------------------------------------------------------------------------------ recording
@dataclass
class Exchange:
    """One request and its response, as sent. Bodies are parsed JSON when the response is JSON."""

    method: str
    path: str
    request_headers: dict[str, str]
    request_body: Any
    status: int
    content_type: str
    headers: dict[str, str]
    body: Any
    elapsed_ms: int = 0
    notes: list[str] = field(default_factory=list[str])

    def json(self) -> Any:
        return self.body

    @property
    def code(self) -> str | None:
        return self.body.get("code") if isinstance(self.body, dict) else None


def redact_text(value: str, aliases: dict[str, str]) -> str:
    """Replace every email with a stable pseudonym so one person stays one pseudonym within a capture."""

    def alias(match: re.Match[str]) -> str:
        return aliases.setdefault(match.group(0).lower(), f"user-{len(aliases) + 1}@example.test")

    return EMAIL_RE.sub(alias, value)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in headers.items():
        low = name.lower()
        if low == "set-cookie":
            attrs = value.split(";", 1)[1] if ";" in value else ""
            name_only = value.split("=", 1)[0]
            out[name] = f"{name_only}={REDACTED};{attrs}"
        elif low in {"cookie", "authorization", "x-request-id", "paddle-signature", "x-forwarded-for"}:
            out[name] = REDACTED
        else:
            out[name] = value
    return out


def redact_json(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, str):
        return redact_text(value, aliases)
    if isinstance(value, list):
        return [redact_json(v, aliases) for v in value]
    if isinstance(value, dict):
        return {k: redact_json(v, aliases) for k, v in value.items()}
    return value


@dataclass
class Actor:
    """A person with a session. `client` sends their cookie and the Origin the API insists on."""

    user_id: str
    email: str
    cookie: str | None
    client: httpx.AsyncClient


# ------------------------------------------------------------------------------------------------ world
# GDPR[personal-data]: every account here is synthetic (example.test addresses); exchanges are redacted before
# they are written anywhere (RM-263)
MARKET_CATALOGUE_VERSION = 7  # smoke-only catalogue, so seeding never collides with the integration suites


class World:
    def __init__(
        self,
        database_url: str,
        *,
        transport: Transport = "asgi",
        settings: Settings | None = None,
        real_providers: bool = False,
    ) -> None:
        """`real_providers` (live capture only, owner-authorised) leaves the worker to build its own Otodom
        client, market context and vision model from `settings`; otherwise every provider is a fake."""
        self.real_providers = real_providers
        self.database_url = database_url
        self.transport: Transport = transport
        self.dsn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self.keys: GoogleKeys = build_keys()
        self.mail = SmokeMail()
        self.source = SmokeSource()
        self.context = SmokeContext()
        self.vision = SmokeVision()
        self.paddle = FakePaddle()
        self.media_store = MemoryObjectStore()  # the private image bucket, offline (ADR 0014)
        for pack in CATALOG.packs:
            self.paddle.add_price(pack.price_id, amount_minor=pack.amount_minor)
        self.settings = settings or Settings(
            app_env="test",
            database_url=database_url,
            public_app_url=ORIGIN,
            google_client_id=GOOGLE_AUDIENCE,
            free_signup_credits=SIGNUP_CREDITS,
            otodom_market_catalogue_version=MARKET_CATALOGUE_VERSION,
            interior_image_provider="fake",  # the offline model (RM-450)
            catalogue_provider="demo",  # the named deterministic fake source (RM-449)
            log_level="WARNING",  # a capture of 170 scenarios should not print 170 access lines
            paddle_webhook_secret=SecretStr(WEBHOOK_SECRET),
        )
        self.app: FastAPI
        self.engine: AsyncEngine
        self.sm: async_sessionmaker[AsyncSession]
        self.base_url = ORIGIN
        self.exchanges: list[Exchange] = []
        self.aliases: dict[str, str] = {}
        self._clients: list[httpx.AsyncClient] = []
        self._emails: list[str] = []
        self._refs: list[str] = []
        self._flags: list[str] = []
        self._plans: list[str] = []
        self._ip = 0
        self._queue: ProcrastinateEmailQueue
        self._server: uvicorn.Server | None = None
        self._serve_task: asyncio.Task[None] | None = None
        self._hasher = PasswordHasher(self.settings)

    # ------------------------------------------------------------------------------------- lifecycle
    @asynccontextmanager
    async def running(self) -> AsyncIterator["World"]:
        self.engine = create_async_engine(self.database_url, pool_size=5)
        self.sm = async_sessionmaker(self.engine, expire_on_commit=False)
        self._queue = ProcrastinateEmailQueue(
            procrastinate.App(
                connector=procrastinate.PsycopgConnector(conninfo=self.dsn, min_size=1, max_size=2)
            )
        )
        self.app = create_app(
            self.settings,
            email_queue=self.mail,
            audit_queue=self._queue,
            generation_queue=self._queue,
            google_verifier=GoogleVerifier(GOOGLE_AUDIENCE, SmokeCerts(self.keys.certs)),
            paddle_client=self.paddle,
            catalog=CATALOG,
            object_store=self.media_store,
        )
        try:
            if self.transport == "asgi":
                async with LifespanManager(self.app):
                    await asyncio.wait_for(self.app.state.notify_listener.listening.wait(), 10)
                    await self._wipe_stale_jobs()
                    await self._ensure_plans()
                    yield self
            else:
                await self._start_server()
                await self._wipe_stale_jobs()
                await self._ensure_plans()
                yield self
        finally:
            await self._cleanup()
            for client in self._clients:
                await client.aclose()
            if self._server is not None and self._serve_task is not None:
                self._server.should_exit = True
                await self._serve_task
            await self._queue.close()
            await self.engine.dispose()

    async def _start_server(self) -> None:
        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",
            port=0,
            log_level="warning",
            proxy_headers=True,
            forwarded_allow_ips="*",
            lifespan="on",
        )
        self._server = uvicorn.Server(config)
        self._serve_task = asyncio.create_task(self._server.serve())
        for _ in range(200):
            if self._server.started:
                break
            await asyncio.sleep(0.05)
        else:
            msg = "uvicorn did not start"
            raise RuntimeError(msg)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        await asyncio.wait_for(self.app.state.notify_listener.listening.wait(), 10)

    async def _ensure_plans(self) -> None:
        """Flags reference `plan.code`; an unseeded database lacks them. Remove only what we add."""
        async with self.sm() as s, s.begin():
            for code in ("free", "pro"):
                if await s.get(Plan, code) is None:
                    s.add(Plan(code=code))
                    self._plans.append(code)

    async def _wipe_stale_jobs(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("DELETE FROM procrastinate_jobs WHERE queue_name = 'audit'"))

    async def _cleanup(self) -> None:
        """Leave a shared database as found: other test modules count rows in these tables."""
        async with self.engine.begin() as conn:
            await conn.execute(text("DELETE FROM procrastinate_jobs WHERE queue_name = 'audit'"))
            await conn.execute(text("DELETE FROM app.billing_event"))
            await conn.execute(text("DELETE FROM app.billing_adjustment"))
            await conn.execute(
                text("UPDATE app.report_credit_lot SET purchase_id = NULL WHERE purchase_id IS NOT NULL")
            )
            await conn.execute(text("DELETE FROM app.billing_purchase"))
            await conn.execute(
                text(
                    "DELETE FROM app.audit_event WHERE audit_id IN"
                    " (SELECT id FROM app.audit WHERE otodom_id = ANY(:r))"
                ),
                {"r": self._refs},
            )
            await conn.execute(
                text("UPDATE app.audit SET snapshot_id = NULL WHERE otodom_id = ANY(:r)"), {"r": self._refs}
            )
            await conn.execute(
                text("DELETE FROM app.listing_snapshot WHERE otodom_id = ANY(:r)"), {"r": self._refs}
            )
            await conn.execute(text("DELETE FROM app.app_user WHERE email = ANY(:e)"), {"e": self._emails})
            await conn.execute(text("DELETE FROM app.listing WHERE otodom_id = ANY(:r)"), {"r": self._refs})
            await conn.execute(text("DELETE FROM app.feature_flag WHERE key = ANY(:k)"), {"k": self._flags})
            await conn.execute(text("DELETE FROM app.plan WHERE code = ANY(:p)"), {"p": self._plans})
            await conn.execute(text("DELETE FROM app.rate_limit WHERE true"))

    # ------------------------------------------------------------------------------------- market
    async def seed_market(self) -> None:
        """Synthetic market data through production code: two places (12 and 3 priced asking rents) published
        for today, one with a pending bootstrap and one never imported. Idempotent per process.
        Evidence class: fake provider data (hand-made offers, no Otodom response)."""
        if getattr(self, "_market_seeded", False):
            return
        from deal_analyzer.market_stats import summarise_asking  # noqa: PLC0415
        from rm_contracts.market import (  # noqa: PLC0415
            ImportRun,
            LocationCatalogue,
            LocationEntry,
            OfferObservation,
            RunMode,
            RunState,
        )
        from rm_core.market_corpus import PgCorpus  # noqa: PLC0415
        from rm_core.market_history import PgMarketHistory  # noqa: PLC0415

        now = datetime.now(UTC)
        boot = now - timedelta(days=3)
        places = {
            "smoke-torun": "Toruń",
            "smoke-gdynia": "Gdynia",
            "smoke-gdansk": "Gdańsk",
            "smoke-kielce": "Kielce",
        }
        corpus = PgCorpus(self.sm)
        await corpus.ensure_catalogue(
            LocationCatalogue.build(
                MARKET_CATALOGUE_VERSION,
                "smoke-catalogue",
                [
                    LocationEntry(location_id=i, name=n, otodom_path=f"cala-polska/{i}")
                    for i, n in places.items()
                ],
            )
        )

        async def publish(loc: str, count: int) -> None:
            tag = uuid4().hex[:10]
            for rid, mode, seen, start in (
                (f"b-{tag}", RunMode.bootstrap, boot, boot - timedelta(hours=24)),
                (f"n-{tag}", RunMode.incremental, now - timedelta(hours=2), boot),
            ):
                await corpus.start_run(
                    ImportRun(
                        run_id=rid,
                        location_id=loc,
                        mode=mode,
                        window_start=start,
                        window_end=start + timedelta(hours=24),
                    )
                )
                await corpus.save_progress(rid, pages_fetched=1, pages_expected=1)
                offers = [
                    OfferObservation(
                        source_offer_id=str(abs(hash(loc)) % 10**9 * 100 + i),
                        location_id=loc,
                        asking_rent_pln=Decimal(2000 + 50 * i),
                        area_m2=Decimal(50),
                        rooms=2,
                        observed_at=seen,
                        district_id=(
                            f"cala-polska/{loc}/{'centrum' if i < 10 else 'rubinkowo'}"
                            if loc == "smoke-torun"
                            else None
                        ),
                        district_name=(
                            ("Centrum" if i < 10 else "Rubinkowo") if loc == "smoke-torun" else None
                        ),  # Toruń: two districts (10 and 2 adverts); the other place's source names none
                    )
                    for i in range(count)
                ]
                if mode is RunMode.bootstrap:
                    await corpus.record_offers(rid, offers, seen)
                await corpus.finish_run(rid, state=RunState.published, now=seen)

        await publish("smoke-torun", 12)
        await publish("smoke-gdynia", 3)
        history = PgMarketHistory(self.sm)
        for loc in ("smoke-torun", "smoke-gdynia"):
            await history.publish_day(loc, now.date(), now=now, summarise=summarise_asking)
        self._market_seeded = True

    # ------------------------------------------------------------------------------------- clients
    def _next_ip(self) -> str:
        self._ip += 1
        return f"10.{self._ip // 250}.{self._ip % 250}.7"

    def client(self, cookie: str | None = None, *, origin: str | None = ORIGIN) -> httpx.AsyncClient:
        ip = self._next_ip()
        headers: dict[str, str] = {}
        if origin:
            headers["Origin"] = origin
        if cookie:
            headers["Cookie"] = f"{self.settings.cookie_name}={cookie}"
        if self.transport == "asgi":
            client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False, client=(ip, 5000)),
                base_url=ORIGIN,
                headers=headers,
                timeout=60,
            )
        else:
            headers["X-Forwarded-For"] = ip
            client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=60)
        self._clients.append(client)
        return client

    def anonymous(self, *, origin: str | None = ORIGIN) -> Actor:
        return Actor("", "", None, self.client(origin=origin))

    def new_email(self, label: str = "user") -> str:
        email = f"{label}-{uuid4().hex[:10]}@example.test"
        self._emails.append(email)
        return email

    async def user(
        self,
        *,
        label: str = "user",
        credits: int = SIGNUP_CREDITS,
        role: str = "user",
        verified: bool = True,
        password: str | None = None,
        email: str | None = None,
        sessions: int = 1,
        user_agent: str = "Mozilla/5.0 (smoke) Chrome/130",
    ) -> Actor:
        """A user with a credit account and `sessions` browser sessions (the first is the actor's)."""
        email = email or self.new_email(label)
        if email not in self._emails:
            self._emails.append(email)
        cookies: list[str] = []
        credential = await self._hasher.hash(password) if password else None
        async with self.sm() as s, s.begin():
            user = User(
                email=email,
                email_verified_at=datetime.now(UTC) if verified else None,
                name=label.title(),
                role=role,
            )
            s.add(user)
            await s.flush()
            await ensure_credit_account(s, user.id, verified=verified, signup_credits=0)
            if credits:
                await admin_adjust(s, user.id, credits, key=f"smoke:{user.id}", note="smoke credits")
            if credential:
                s.add(UserCredential(user_id=user.id, password_hash=credential))
            for n in range(sessions):
                cookies.append(
                    await create_session(
                        s,
                        user.id,
                        user_agent=user_agent if n == 0 else f"Safari/17 device-{n}",
                        ip=f"198.51.100.{10 + n}",
                        settings=self.settings,
                    )
                )
            user_id = user.id
        return Actor(user_id, email, cookies[0], self.client(cookies[0]))

    # -------------------------------------------------------------------------------------- sending
    async def send(
        self,
        who: Actor | httpx.AsyncClient,
        method: str,
        path: str,
        *,
        json: Any = None,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | list[tuple[str, Any]] | None = None,
    ) -> Exchange:
        client = who.client if isinstance(who, Actor) else who
        started = time.monotonic()
        response = await client.request(
            method, path, json=json, content=content, headers=headers, params=params
        )
        elapsed = int((time.monotonic() - started) * 1000)
        content_type = response.headers.get("content-type", "")
        parsed: Any
        if content_type.startswith("image/"):  # a picture is never kept in a sample: size and type only
            parsed = f"[{content_type}, {len(response.content)} bytes]"
        else:
            parsed = response.json() if "json" in content_type else response.text or None
        sent = {
            k: v for k, v in response.request.headers.items() if k.lower() not in {"host", "content-length"}
        }
        shown_path = path if not params else f"{path}?{httpx.QueryParams(params)}"
        exchange = Exchange(
            method=method,
            path=shown_path,
            request_headers=redact_headers(sent),
            request_body=json,
            status=response.status_code,
            content_type=content_type,
            headers=redact_headers(dict(response.headers)),
            body=parsed,
            elapsed_ms=elapsed,
        )
        self.exchanges.append(exchange)
        return exchange

    async def tester(self, *, label: str = "tester") -> Actor:
        """A user in the interior closed beta: holds the explicit `unlimited_reports` entitlement."""
        who = await self.user(label=label)
        async with self.sm() as s, s.begin():
            s.add(AccountEntitlement(user_id=who.user_id, kind="unlimited_reports", note="smoke"))
        return who

    # --------------------------------------------------------------------------------------- audits
    def new_ref(self) -> str:
        ref = "ID" + uuid4().hex[:8].upper()
        self._refs.append(ref)
        return ref

    def serve(self, ad_or_error: Any) -> str:
        """Register what the fake source answers for a fresh listing id; returns the id."""
        ref = self.new_ref()
        self.source.ads[ref] = ad_or_error
        return ref

    def serve_sale(self, listing: SaleListing, *, with_vision: bool = True) -> str:
        ad = sale_ad(listing)
        if with_vision:
            self.vision.answers[ad["title"]] = vision_answer(listing)
        else:
            ad["title"] += " (bez opisu zdjęć)"  # no answer is registered for this title
        return self.serve(ad)

    async def run_worker(self) -> None:
        """Process every todo job on the `audit` queue with the real Procrastinate worker, then return."""
        audit_services.configure(
            None
            if self.real_providers
            else AuditServices(
                sessionmaker=self.sm,
                source=self.source,
                context=self.context,
                timeout_s=60.0,
                engine=ChildEngine(),
                vision=self.vision,
            )
        )
        connector = procrastinate.PsycopgConnector(conninfo=self.dsn, min_size=1, max_size=3)
        try:
            with worker_app.replace_connector(connector) as app:
                async with app.open_async():
                    await app.run_worker_async(
                        queues=[AUDIT_QUEUE], wait=False, install_signal_handlers=False, listen_notify=False
                    )
        finally:
            audit_services.configure(None)

    async def submit(self, who: Actor, ref: str, **body: Any) -> Exchange:
        return await self.send(who, "POST", "/api/audits", json={"listing_ref": ref, **body})

    async def audit_to_end(self, who: Actor, ref: str) -> str:
        """Submit `ref`, run the worker, and return the audit id (the audit is terminal afterwards)."""
        accepted = await self.submit(who, ref)
        assert accepted.status == 202, accepted.body
        await self.run_worker()
        return str(accepted.body["audit_id"])

    async def seed_audits(self, who: Actor, count: int) -> list[str]:
        """`count` finished, captured audits straight into the table (a heavy user without 120 worker runs).
        Returns their Otodom ids, newest first."""
        refs: list[str] = []
        async with self.sm() as s, s.begin():
            for n in range(count):
                ref = f"ID{uuid4().hex[:8].upper()}"
                self._refs.append(ref)
                refs.append(ref)
                s.add(ListingRow(otodom_id=ref, url=f"https://fake.test/{ref}"))
                await s.flush()
                finished = n % 7 != 3
                s.add(
                    Audit(
                        id=uuid4(),
                        user_id=who.user_id,
                        otodom_id=ref,
                        status=AuditStatus.succeeded if finished else AuditStatus.failed_input,
                        error_code=None if finished else "LISTING_GONE",
                        charge_source=ChargeSource.credit,
                        charge_state=ChargeState.captured if finished else ChargeState.released,
                        engine_version="smoke",
                        schema_version=1,
                        grade="ABCDF"[n % 5] if finished else None,
                        asking_price_pln=Decimal(300000 + n * 4500) if finished else None,
                        max_bid_pln=Decimal(280000 + n * 4000) if finished else None,
                        created_at=datetime.fromtimestamp(time.time() - n * 3600, UTC),
                        finished_at=datetime.fromtimestamp(time.time() - n * 3600 + 30, UTC),
                    )
                )
        return refs

    # -------------------------------------------------------------------------------------- billing
    @asynccontextmanager
    async def billing_disabled(self) -> AsyncIterator[None]:
        """Sales off, as on a host with no approved catalog (the app answers 503 / `enabled: false`)."""
        paddle, catalog = self.app.state.paddle, self.app.state.catalog
        self.app.state.paddle = self.app.state.catalog = None
        try:
            yield
        finally:
            self.app.state.paddle, self.app.state.catalog = paddle, catalog

    async def buy(self, who: Actor, pack: str = "reports_5", key: UUID | None = None) -> Exchange:
        return await self.send(
            who,
            "POST",
            "/api/billing/checkout",
            json={"pack_code": pack},
            headers={"Idempotency-Key": str(key or uuid4())},
        )

    async def deliver(self, txn_id: str, kind: str = "transaction.completed") -> Exchange:
        body = json.dumps(
            {
                "event_id": f"evt_{uuid4().hex[:20]}",
                "event_type": kind,
                "occurred_at": datetime.now(UTC).isoformat(),
                "notification_id": f"ntf_{uuid4().hex[:12]}",
                "data": {"id": txn_id, "status": "completed", "customer": {"email": "buyer@example.test"}},
            }
        ).encode()
        header = sign(WEBHOOK_SECRET, body, timestamp=int(time.time()))
        return await self.send(
            self.client(origin=None),
            "POST",
            "/api/webhooks/paddle",
            content=body,
            headers={"Paddle-Signature": header, "Content-Type": "application/json"},
        )

    async def pay(self, txn_id: str) -> None:
        """Paddle reports the transaction paid; the signed webhook and the grant sweep follow."""
        txn = self.paddle.transactions[txn_id]
        self.paddle.transactions[txn_id] = txn.model_copy(update={"status": "completed"})
        await self.deliver(txn_id)
        await run_sweep(self.sm, self.paddle, reconcile=False)

    async def approve_refund(self, txn_id: str, adjustment_id: str) -> None:
        adjustment: Adjustment = self.paddle.adjustments[adjustment_id]
        self.paddle.adjustments[adjustment_id] = adjustment.model_copy(update={"status": "approved"})
        await self.deliver(txn_id, "adjustment.updated")
        await run_sweep(self.sm, self.paddle, reconcile=False)

    async def bought(self, who: Actor, pack: str = "reports_5") -> dict[str, Any]:
        """A paid, granted purchase (checkout, payment, webhook, grant), as the API shows it."""
        created = await self.buy(who, pack)
        assert created.status == 200, created.body
        await self.pay(created.body["transaction_id"])
        got = await self.send(who, "GET", f"/api/billing/purchases/{created.body['purchase_id']}")
        assert got.body["state"] == "granted", got.body
        return got.body

    # ---------------------------------------------------------------------------------------- misc
    def google_token(self, **claims: Any) -> str:
        return sign_token(self.keys, **claims)

    async def sql(self, statement: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(statement), params)

    async def add_flag(
        self,
        key: str,
        *,
        description: str,
        enabled_default: bool = False,
        min_plan: str | None = None,
        rollout_pct: int = 0,
    ) -> str:
        async with self.sm() as s, s.begin():
            s.add(
                FeatureFlag(
                    key=key,
                    description=description,
                    enabled_default=enabled_default,
                    min_plan=min_plan,
                    rollout_pct=rollout_pct,
                )
            )
        self._flags.append(key)
        return key

    def clear_principals(self) -> None:
        self.app.state.principal_cache.clear()


Run = Callable[[World], Awaitable[Exchange]]
SUCCESS_LISTINGS = SUCCESS
