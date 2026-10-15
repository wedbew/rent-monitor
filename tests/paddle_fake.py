"""An offline Paddle for billing tests: records calls, holds transactions and adjustments in memory, and
can be told to time out. Used by the checkout, webhook and refund suites (docs/PADDLE-INTEGRATION.md §9)."""

from collections.abc import Mapping
from uuid import uuid4

from rm_core.paddle import (
    Adjustment,
    PaddleAmbiguousError,
    PaddleError,
    PriceInfo,
    Transaction,
    TransactionItem,
)


class FakePaddle:
    def __init__(self) -> None:
        self.prices: dict[str, PriceInfo] = {}
        self.transactions: dict[str, Transaction] = {}
        self.adjustments: dict[str, Adjustment] = {}
        self.calls: list[str] = []
        self.fail_create_after_store = False  # the create times out but the transaction exists (ambiguous)
        self.fail_create_before_store = False
        self.fail_refund_before_store = False
        self.fail_refund_after_store = False

    def add_price(
        self, price_id: str, *, amount_minor: int, currency: str = "PLN", one_time: bool = True
    ) -> None:
        self.prices[price_id] = PriceInfo(
            id=price_id,
            product_id="pro_" + uuid4().hex[:10],
            currency_code=currency,
            amount_minor=amount_minor,
            one_time=one_time,
            quantity_min=1,
            quantity_max=1,
            status="active",
        )

    async def create_transaction(self, *, price_id: str, custom_data: Mapping[str, str]) -> Transaction:
        self.calls.append("create_transaction")
        if self.fail_create_before_store:
            raise PaddleAmbiguousError("timed out")
        price = self.prices[price_id]
        txn_id = "txn_" + uuid4().hex[:20]
        txn = Transaction(
            id=txn_id,
            status="ready",
            currency_code=price.currency_code,
            items=(TransactionItem(price_id=price_id, product_id=price.product_id, quantity=1),),
            total_minor=price.amount_minor,
            custom_data=dict(custom_data),
            checkout_url="https://checkout.test/pay?_ptxn=" + txn_id,
        )
        self.transactions[txn.id] = txn
        if self.fail_create_after_store:
            raise PaddleAmbiguousError("timed out after the transaction was created")
        return txn

    async def get_transaction(self, transaction_id: str) -> Transaction:
        self.calls.append("get_transaction")
        try:
            return self.transactions[transaction_id]
        except KeyError as exc:
            raise PaddleError("404") from exc

    async def list_transactions(
        self, *, custom_data_key: str, created_after: str | None = None
    ) -> list[Transaction]:
        self.calls.append("list_transactions")
        return [t for t in self.transactions.values() if t.custom_data and custom_data_key in t.custom_data]

    async def get_price(self, price_id: str) -> PriceInfo:
        self.calls.append("get_price")
        try:
            return self.prices[price_id]
        except KeyError as exc:
            raise PaddleError("404") from exc

    async def list_adjustments(self, transaction_id: str) -> list[Adjustment]:
        self.calls.append("list_adjustments")
        return [a for a in self.adjustments.values() if a.transaction_id == transaction_id]

    async def get_invoice_url(self, transaction_id: str) -> str:
        self.calls.append("get_invoice_url")
        if transaction_id not in self.transactions:
            raise PaddleError("404")
        return f"https://invoices.test/{transaction_id}?sig=short-lived"

    async def create_full_refund(self, *, transaction_id: str, reason: str) -> Adjustment:
        self.calls.append("create_full_refund")
        if self.fail_refund_before_store:
            raise PaddleAmbiguousError("timed out")
        txn = self.transactions[transaction_id]
        adj = Adjustment(
            id="adj_" + uuid4().hex[:20],
            transaction_id=transaction_id,
            action="refund",
            type="full",
            status="pending_approval",
            currency_code=txn.currency_code,
            total_minor=txn.total_minor,
        )
        self.adjustments[adj.id] = adj
        if self.fail_refund_after_store:
            raise PaddleAmbiguousError("timed out after the refund was created")
        return adj
