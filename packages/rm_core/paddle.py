"""Paddle Billing client (docs/PADDLE-INTEGRATION.md section 2 and 3): an injectable protocol, the real
`httpx` implementation and the typed results the billing code consumes.

GDPR[processor]: Paddle is the merchant of record and receives the buyer's checkout data; we send it only the
price id, quantity and our own opaque references, never an address, name or listing data (RM-215).

Rules baked in: explicit connect and total timeouts; bounded retries with jitter for reads (429, 5xx,
honouring `Retry-After`); creation of a transaction or a refund is never retried blindly, because an ambiguous
timeout may still have created it. The caller recovers by listing (`PaddleAmbiguousError`). Responses are
parsed into bounded typed models, unknown fields ignored; money is a string of minor units, read as `int`.
"""

import asyncio
import random
from collections.abc import Mapping
from typing import Any, Protocol, TypeVar, cast

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from rm_core.settings import Settings

log = structlog.get_logger(__name__)
BASE_URLS = {"sandbox": "https://sandbox-api.paddle.com", "live": "https://api.paddle.com"}
CONNECT_TIMEOUT_S = 3.0
TOTAL_TIMEOUT_S = 10.0
MAX_READ_ATTEMPTS = 3
MAX_RETRY_AFTER_S = 5.0
MAX_BODY_BYTES = 1_000_000


_M = TypeVar("_M", bound=BaseModel)


class PaddleError(RuntimeError):
    """The request failed in a way the caller may treat as definite (4xx, bad shape, retries exhausted)."""


class PaddleAmbiguousError(PaddleError):
    """A write timed out or was cut off: the resource may exist. List before trying again."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class PriceInfo(_Model):
    id: str
    product_id: str
    currency_code: str
    amount_minor: int
    one_time: bool  # no billing cycle and no trial
    quantity_min: int
    quantity_max: int
    status: str


class TransactionItem(_Model):
    price_id: str
    product_id: str | None = None
    quantity: int


class Transaction(_Model):
    id: str
    status: str
    currency_code: str
    customer_id: str | None = None
    items: tuple[TransactionItem, ...] = ()
    total_minor: int | None = None
    discount_id: str | None = None
    subscription_id: str | None = None
    custom_data: Mapping[str, Any] | None = None
    invoice_id: str | None = None


class Adjustment(_Model):
    id: str
    transaction_id: str
    action: str
    type: str
    status: str
    currency_code: str
    total_minor: int | None = None


class PaddleClient(Protocol):
    async def create_transaction(self, *, price_id: str, custom_data: Mapping[str, str]) -> Transaction: ...

    async def get_transaction(self, transaction_id: str) -> Transaction: ...

    async def list_transactions(
        self, *, custom_data_key: str, created_after: str | None = None
    ) -> list[Transaction]:
        """Recovery after an ambiguous create: transactions carrying our own reference."""
        ...

    async def get_price(self, price_id: str) -> PriceInfo: ...

    async def list_adjustments(self, transaction_id: str) -> list[Adjustment]: ...

    async def create_full_refund(self, *, transaction_id: str, reason: str) -> Adjustment: ...


class _Money(_Model):
    amount: str = ""
    currency_code: str = ""


class _Totals(_Model):
    total: str | None = None


class _Details(_Model):
    totals: _Totals | None = None


class _Quantity(_Model):
    minimum: int = 0
    maximum: int = 0


class _RawPrice(_Model):
    id: str
    product_id: str | None = None
    unit_price: _Money | None = None
    billing_cycle: object | None = None
    trial_period: object | None = None
    quantity: _Quantity | None = None
    status: str = ""


class _RawItem(_Model):
    price: _RawPrice | None = None
    price_id: str | None = None
    quantity: int = 0


class _RawTransaction(_Model):
    id: str
    status: str
    currency_code: str = ""
    customer_id: str | None = None
    items: list[_RawItem] = []
    details: _Details | None = None
    totals: _Totals | None = None
    discount_id: str | None = None
    subscription_id: str | None = None
    custom_data: dict[str, object] | None = None
    invoice_id: str | None = None


class _RawAdjustment(_Model):
    id: str
    transaction_id: str
    action: str
    type: str = ""
    status: str
    currency_code: str = ""
    totals: _Totals | None = None


def _minor(value: str | None) -> int | None:
    return int(value) if value is not None and value.isdecimal() else None


def _transaction(raw: _RawTransaction) -> Transaction:
    totals = (raw.details.totals if raw.details else None) or raw.totals
    return Transaction(
        id=raw.id,
        status=raw.status,
        currency_code=raw.currency_code,
        customer_id=raw.customer_id,
        items=tuple(
            TransactionItem(
                price_id=(i.price.id if i.price else i.price_id) or "",
                product_id=i.price.product_id if i.price else None,
                quantity=i.quantity,
            )
            for i in raw.items
        ),
        total_minor=_minor(totals.total) if totals else None,
        discount_id=raw.discount_id,
        subscription_id=raw.subscription_id,
        custom_data=raw.custom_data,
        invoice_id=raw.invoice_id,
    )


def _price(raw: _RawPrice) -> PriceInfo:
    unit = raw.unit_price or _Money()
    quantity = raw.quantity or _Quantity()
    return PriceInfo(
        id=raw.id,
        product_id=raw.product_id or "",
        currency_code=unit.currency_code,
        amount_minor=_minor(unit.amount) or 0,
        one_time=raw.billing_cycle is None and raw.trial_period is None,
        quantity_min=quantity.minimum,
        quantity_max=quantity.maximum,
        status=raw.status,
    )


def _adjustment(raw: _RawAdjustment) -> Adjustment:
    return Adjustment(
        id=raw.id,
        transaction_id=raw.transaction_id,
        action=raw.action,
        type=raw.type,
        status=raw.status,
        currency_code=raw.currency_code,
        total_minor=_minor(raw.totals.total) if raw.totals else None,
    )


class HttpPaddleClient:
    def __init__(
        self,
        *,
        environment: str,
        api_key: str,
        http: httpx.AsyncClient | None = None,
        sleep: Any = asyncio.sleep,
    ) -> None:
        if environment not in BASE_URLS:
            msg = f"unknown Paddle environment {environment!r}"
            raise PaddleError(msg)
        self._base = BASE_URLS[environment]
        self._headers = {"Authorization": f"Bearer {api_key}", "Paddle-Version": "1"}
        self._http = http or httpx.AsyncClient(
            timeout=httpx.Timeout(TOTAL_TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
        )
        self._owns_http = http is None
        self._sleep = sleep
        self._rng = random.Random()  # noqa: S311  (retry jitter, not security)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _call(self, method: str, path: str, *, read: bool, **kwargs: Any) -> object:
        attempts = MAX_READ_ATTEMPTS if read else 1
        for attempt in range(1, attempts + 1):
            try:
                response = await self._http.request(
                    method, self._base + path, headers=self._headers, **kwargs
                )
            except httpx.TimeoutException as exc:
                if not read:
                    msg = f"{method} {path} timed out; the resource may exist"
                    raise PaddleAmbiguousError(msg) from exc
                if attempt == attempts:
                    msg = f"{method} {path} timed out"
                    raise PaddleError(msg) from exc
                await self._sleep(self._backoff(attempt, None))
                continue
            except httpx.HTTPError as exc:
                msg = f"{method} {path} failed: {type(exc).__name__}"
                raise (PaddleAmbiguousError if not read else PaddleError)(msg) from exc
            if response.status_code in {429, 500, 502, 503, 504}:
                if read and attempt < attempts:
                    await self._sleep(self._backoff(attempt, response.headers.get("retry-after")))
                    continue
                if not read and response.status_code >= 500:
                    msg = f"{method} {path} -> {response.status_code}; the resource may exist"
                    raise PaddleAmbiguousError(msg)
                msg = f"{method} {path} -> {response.status_code}"
                raise PaddleError(msg)
            if response.status_code >= 400:
                msg = f"{method} {path} -> {response.status_code}"
                raise PaddleError(msg)
            if len(response.content) > MAX_BODY_BYTES:
                msg = f"{method} {path} response too large"
                raise PaddleError(msg)
            try:
                envelope: object = response.json()
            except ValueError as exc:
                msg = f"{method} {path} returned non-JSON"
                raise PaddleError(msg) from exc
            if not isinstance(envelope, dict) or "data" not in envelope:
                msg = f"{method} {path} returned an unexpected envelope"
                raise PaddleError(msg)
            return cast("dict[str, object]", envelope)["data"]
        raise AssertionError("unreachable")  # pragma: no cover

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        base = min(MAX_RETRY_AFTER_S, 0.5 * 2 ** (attempt - 1)) * self._rng.uniform(0.5, 1.0)
        if retry_after and retry_after.isdecimal():
            return min(MAX_RETRY_AFTER_S, max(base, float(retry_after)))
        return base

    @staticmethod
    def _validate(model: type[_M], data: object) -> _M:
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            msg = "Paddle returned an unexpected shape"
            raise PaddleError(msg) from exc

    @classmethod
    def _validate_list(cls, model: type[_M], data: object) -> list[_M]:
        if not isinstance(data, list):
            msg = "Paddle returned an unexpected shape"
            raise PaddleError(msg)
        return [cls._validate(model, row) for row in cast("list[object]", data)]

    async def create_transaction(self, *, price_id: str, custom_data: Mapping[str, str]) -> Transaction:
        body = {"items": [{"price_id": price_id, "quantity": 1}], "custom_data": dict(custom_data)}
        data = await self._call("POST", "/transactions", read=False, json=body)
        return _transaction(self._validate(_RawTransaction, data))

    async def get_transaction(self, transaction_id: str) -> Transaction:
        data = await self._call("GET", f"/transactions/{transaction_id}", read=True)
        return _transaction(self._validate(_RawTransaction, data))

    async def list_transactions(
        self, *, custom_data_key: str, created_after: str | None = None
    ) -> list[Transaction]:
        params: dict[str, str] = {"per_page": "50", "order_by": "created_at[DESC]"}
        if created_after:
            params["created_at[GTE]"] = created_after
        data = await self._call("GET", "/transactions", read=True, params=params)
        found = [_transaction(r) for r in self._validate_list(_RawTransaction, data)]
        return [t for t in found if t.custom_data and custom_data_key in t.custom_data]

    async def get_price(self, price_id: str) -> PriceInfo:
        data = await self._call("GET", f"/prices/{price_id}", read=True)
        return _price(self._validate(_RawPrice, data))

    async def list_adjustments(self, transaction_id: str) -> list[Adjustment]:
        data = await self._call(
            "GET", "/adjustments", read=True, params={"transaction_id": transaction_id, "per_page": "50"}
        )
        return [_adjustment(r) for r in self._validate_list(_RawAdjustment, data)]

    async def create_full_refund(self, *, transaction_id: str, reason: str) -> Adjustment:
        body = {"action": "refund", "type": "full", "transaction_id": transaction_id, "reason": reason[:200]}
        data = await self._call("POST", "/adjustments", read=False, json=body)
        return _adjustment(self._validate(_RawAdjustment, data))


def build_paddle_client(settings: Settings) -> HttpPaddleClient | None:
    """None while billing is disabled. Refuses a live key in a non-live environment and the reverse."""
    if settings.billing_provider != "paddle":
        return None
    key = settings.paddle_api_key.get_secret_value()
    if not key:
        msg = "PADDLE_API_KEY is not set"
        raise PaddleError(msg)
    marker = "pdl_live_" if settings.paddle_environment == "live" else "pdl_sdbx_"
    if not key.startswith(marker):
        msg = "PADDLE_API_KEY does not belong to PADDLE_ENVIRONMENT (mixed environments are refused)"
        raise PaddleError(msg)
    return HttpPaddleClient(environment=settings.paddle_environment, api_key=key)


class CatalogMismatchError(PaddleError):
    """A configured price does not match the approved snapshot or is not a one-time quantity-one PLN price."""


async def verify_catalog(client: PaddleClient, packs: list[tuple[str, str, int]]) -> None:
    """Check each (code, price_id, approved amount in grosze) against Paddle before sales are enabled."""
    for code, price_id, amount in packs:
        price = await client.get_price(price_id)
        problems = [
            name
            for name, ok in (
                ("not active", price.status == "active"),
                ("not PLN", price.currency_code == "PLN"),
                ("amount differs from the approved snapshot", price.amount_minor == amount),
                ("recurring or trial", price.one_time),
                ("quantity not fixed at one", price.quantity_min == price.quantity_max == 1),
            )
            if not ok
        ]
        if problems:
            msg = f"{code} ({price_id}): {', '.join(problems)}"
            raise CatalogMismatchError(msg)
