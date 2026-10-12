"""Operational checks the worker runs every few minutes (blueprint §4.7, §6; docs/OBSERVABILITY-SPEC.md
section 5).

Pure measurements plus a threshold function, so the task that reports them stays tiny and the logic is
testable.
No personal data is read: queue names, counts and byte sizes only.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

QUEUE_AGE_WARN_S = 600  # a runnable job waiting longer than 10 minutes
CONNECTIONS_WARN = 70  # blueprint §6 connection budget: peak must stay under 70 of max_connections=100
MEMORY_PEAK_WARN = 0.6  # gate 4: concurrency 2 only if cgroup memory.peak stays under 60 % of the limit
CGROUP = Path("/sys/fs/cgroup")


@dataclass(frozen=True)
class Reading:
    queue_age_s: dict[str, float]
    connections: int
    memory_peak_ratio: float | None


@dataclass(frozen=True)
class Alert:
    key: str
    message: str


async def queue_ages(session: AsyncSession) -> dict[str, float]:
    """Seconds the oldest runnable `todo` job of each queue has been waiting (per Procrastinate's own event
    log)."""
    stmt = text(
        """
        SELECT j.queue_name, EXTRACT(EPOCH FROM (now() - min(COALESCE(j.scheduled_at, e.at))))::float8
        FROM procrastinate_jobs j
        JOIN procrastinate_events e ON e.job_id = j.id AND e.type = 'deferred'
        WHERE j.status = 'todo' AND (j.scheduled_at IS NULL OR j.scheduled_at <= now())
        GROUP BY j.queue_name
        """
    )
    rows = await session.execute(stmt)
    return {str(queue): max(0.0, float(age)) for queue, age in rows}


async def connection_count(session: AsyncSession) -> int:
    """Backends of this database, ours and Procrastinate's (the figure the 70-of-100 budget is about)."""
    count = await session.scalar(
        text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
    )
    return int(count or 0)


def memory_peak_ratio(root: Path = CGROUP) -> float | None:
    """cgroup v2 `memory.peak` over `memory.max`; None outside a limited cgroup (a laptop, an unlimited
    container)."""
    try:
        peak = int((root / "memory.peak").read_text().strip())
        limit_raw = (root / "memory.max").read_text().strip()
    except (OSError, ValueError):
        return None
    if limit_raw == "max":
        return None
    try:
        limit = int(limit_raw)
    except ValueError:
        return None
    return peak / limit if limit > 0 else None


def evaluate(reading: Reading) -> list[Alert]:
    alerts = [
        Alert(
            f"queue_lag:{queue}",
            f"queue '{queue}' has a job waiting {int(age)} s (limit {QUEUE_AGE_WARN_S} s)",
        )
        for queue, age in sorted(reading.queue_age_s.items())
        if age > QUEUE_AGE_WARN_S
    ]
    if reading.connections > CONNECTIONS_WARN:
        alerts.append(
            Alert(
                "connections",
                f"{reading.connections} database connections (budget {CONNECTIONS_WARN} of 100)",
            )
        )
    ratio = reading.memory_peak_ratio
    if ratio is not None and ratio > MEMORY_PEAK_WARN:
        alerts.append(
            Alert(
                "memory",
                f"cgroup memory peak at {ratio:.0%} of the limit (warn above {MEMORY_PEAK_WARN:.0%})",
            )
        )
    return alerts


async def read(session: AsyncSession) -> Reading:
    return Reading(await queue_ages(session), await connection_count(session), memory_peak_ratio())
