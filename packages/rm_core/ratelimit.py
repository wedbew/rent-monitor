"""Atomic fixed-window rate limiting in Postgres (blueprint §2 Auth decision, rule 5).

One `INSERT ... ON CONFLICT DO UPDATE ... RETURNING n` per hit, so any number of API processes share one
counter and cannot overshoot. The row lock serialises same-key hits; a request that is refused rolls back
its own
increment (the session dependency rolls back on any exception), so a refused hit does not extend the block.

GDPR[personal-data]: the key stored is a SHA-256 of "<scope>:<subject>", never the raw email or IP (RM-12).
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy import Integer, cast, func, literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import RateLimit


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    count: int
    retry_after_s: int


def limit_key(scope: str, subject: str) -> str:
    return hashlib.sha256(f"{scope}:{subject}".encode()).hexdigest()


async def hit(session: AsyncSession, scope: str, subject: str, *, limit: int, window_s: int) -> RateDecision:
    """Count one attempt for `subject` in the current window and say whether it is within `limit`."""
    epoch = func.extract("epoch", func.now())
    window_start = func.to_timestamp(func.floor(epoch / window_s) * window_s)
    stmt = insert(RateLimit).values(key=limit_key(scope, subject), window_start=window_start, n=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RateLimit.key, RateLimit.window_start], set_={"n": RateLimit.n + 1}
    ).returning(
        RateLimit.n,
        cast(
            func.ceil(func.extract("epoch", RateLimit.window_start) + literal(window_s) - epoch),
            Integer,
        ),
    )
    row = (await session.execute(stmt)).one()
    count = int(row[0])
    return RateDecision(allowed=count <= limit, count=count, retry_after_s=max(1, int(row[1])))
