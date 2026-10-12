"""Erasing the payment processor's copy of a user when the account is deleted (GDPR[erasure],
GDPR[processor]).

Billing (#14) supplies the real implementation that deletes the Stripe customer. Until then the seam exists,
and the
route fails safe: a user who has a Stripe customer cannot be deleted without an eraser, because deleting the
database
row first would lose the customer id and the processor's copy could never be erased.
"""

from typing import Protocol


class BillingUnavailable(Exception):
    """The processor could not be reached; nothing has been deleted and the request can be retried."""


class BillingEraser(Protocol):
    async def delete_customer(self, customer_id: str) -> None:
        """Delete the customer at the processor. Deleting one that is already gone must succeed."""
        ...
