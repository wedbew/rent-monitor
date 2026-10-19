"""Machine-readable coverage manifest of the Otodom rental corpus (RM-411).

LEGAL[third-party-data]: counts and states about stored asking-rent offers; no offer content (RM-411).

One honest record of what was collected: per location a state, the pages read against the pages expected,
the offers stored and the last successful refresh; overall counters; and the catalogue's reconciliation
against the owner's stated size. A location is `complete_empty` only when a published run proved it has no
adverts (valid empty search); a `pending`, `partial`, `blocked` or `failed` location is never counted as
covered, and the headline numbers say how many of each there are.
"""

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

STATES = (
    "complete_nonempty",
    "complete_empty",
    "running",
    "partial",
    "blocked",
    "failed",
    "pending",
    "disabled",
)
BLOCKED_CATEGORIES = frozenset({"upstream_blocked"})
FAILED_CATEGORIES = frozenset({"schema_drift", "fetch_error", "abandoned", "cancelled"})

_LOCATIONS = text(
    """
    SELECT l.location_id, l.name, l.otodom_path, l.launch_enabled,
           c.bootstrap_completed_at, c.covered_until, c.unresolved_gap_since,
           c.last_successful_refresh_at,
           (SELECT count(*) FROM app.market_offer o WHERE o.location_id = l.location_id) AS offers,
           (SELECT count(*) FROM app.market_offer o
              WHERE o.location_id = l.location_id AND o.asking_rent_pln IS NOT NULL
                AND o.area_m2 IS NOT NULL) AS priced_offers
    FROM app.market_location l
    LEFT JOIN app.market_import_checkpoint c
           ON c.location_id = l.location_id AND c.dataset = 'otodom_rental'
    WHERE l.catalogue_version = :version
    ORDER BY l.position
    """
)
_LAST_RUN = text(
    """
    SELECT DISTINCT ON (location_id) location_id, run_id, mode, state, error_category, truncated,
           pages_fetched, pages_expected, updated_at
    FROM app.market_import_run
    WHERE location_id IN (SELECT location_id FROM app.market_location WHERE catalogue_version = :version)
    ORDER BY location_id, created_at DESC
    """
)
_RUN_TOTALS = text(
    """
    SELECT mode, state, count(*) AS runs, coalesce(sum(pages_fetched), 0) AS pages_fetched,
           coalesce(sum(pages_expected), 0) AS pages_expected, coalesce(sum(inserted), 0) AS inserted,
           coalesce(sum(duplicates), 0) AS duplicates, coalesce(sum(location_conflicts), 0) AS conflicts
    FROM app.market_import_run
    WHERE location_id IN (SELECT location_id FROM app.market_location WHERE catalogue_version = :version)
    GROUP BY mode, state
    """
)
_SUMMARIES = text(
    """
    SELECT count(*) AS rows, count(DISTINCT location_id) AS locations,
           min(summary_date) AS first_date, max(summary_date) AS last_date
    FROM app.market_daily_summary
    WHERE location_id IN (SELECT location_id FROM app.market_location WHERE catalogue_version = :version)
    """
)
_CATALOGUE = text("SELECT version, source_ref, checksum FROM app.market_catalogue WHERE version = :version")


def classify(row: Any, last_run: Any | None) -> str:
    """The location's state from its checkpoint and its latest run (see the module docstring)."""
    if not row.launch_enabled:
        return "disabled"
    bootstrapped = row.bootstrap_completed_at is not None and row.covered_until is not None
    failed_latest = last_run is not None and last_run.state != "published" and last_run.error_category
    if bootstrapped and row.unresolved_gap_since is not None and failed_latest:
        return _failure_state(last_run)
    if bootstrapped:
        return "complete_nonempty" if row.offers > 0 else "complete_empty"
    if last_run is None:
        return "pending"
    if last_run.state in ("planned", "running"):
        return "running"
    return "failed" if last_run.state == "published" else _failure_state(last_run)


def _failure_state(run: Any) -> str:
    category = run.error_category or ""
    if category in BLOCKED_CATEGORIES:
        return "blocked"
    if category in FAILED_CATEGORIES:
        return "failed"
    return "partial"  # coverage not proven, budget, deadline, night window: resumable


async def coverage_manifest(
    sessionmaker: async_sessionmaker[AsyncSession], version: int, *, now: datetime | None = None
) -> dict[str, Any]:
    async with sessionmaker() as s:
        params = {"version": version}
        catalogue = (await s.execute(_CATALOGUE, params)).first()
        if catalogue is None:
            raise LookupError(f"no catalogue version {version}")
        locations = (await s.execute(_LOCATIONS, params)).all()
        last_runs = {r.location_id: r for r in (await s.execute(_LAST_RUN, params)).all()}
        totals = (await s.execute(_RUN_TOTALS, params)).all()
        summaries = (await s.execute(_SUMMARIES, params)).one()
    rows: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    for loc in locations:
        run = last_runs.get(loc.location_id)
        state = classify(loc, run)
        states[state] += 1
        rows.append(
            {
                "location_id": loc.location_id,
                "name": loc.name,
                "otodom_path": loc.otodom_path,
                "state": state,
                "offers_stored": int(loc.offers),
                "offers_with_rent_and_area": int(loc.priced_offers),
                "bootstrap_completed_at": _iso(loc.bootstrap_completed_at),
                "covered_until": _iso(loc.covered_until),
                "last_successful_refresh_at": _iso(loc.last_successful_refresh_at),
                "unresolved_gap_since": _iso(loc.unresolved_gap_since),
                "last_run": None
                if run is None
                else {
                    "run_id": run.run_id,
                    "mode": run.mode,
                    "state": run.state,
                    "error_category": run.error_category,
                    "truncated": run.truncated,
                    "pages_fetched": run.pages_fetched,
                    "pages_expected": run.pages_expected,
                    "updated_at": _iso(run.updated_at),
                },
            }
        )
    refreshed = [loc.last_successful_refresh_at for loc in locations if loc.last_successful_refresh_at]
    return {
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "catalogue": {
            "version": catalogue.version,
            "source_ref": catalogue.source_ref,
            "checksum": catalogue.checksum,
            "locations": len(locations),
            "enabled": sum(1 for loc in locations if loc.launch_enabled),
        },
        "covered_locations": states["complete_nonempty"] + states["complete_empty"],
        "states": {name: states.get(name, 0) for name in STATES},
        "offers_stored": sum(int(loc.offers) for loc in locations),
        "offers_with_rent_and_area": sum(int(loc.priced_offers) for loc in locations),
        "runs": [
            {
                "mode": t.mode,
                "state": t.state,
                "runs": int(t.runs),
                "pages_fetched": int(t.pages_fetched),
                "pages_expected": int(t.pages_expected),
                "inserted": int(t.inserted),
                "duplicates": int(t.duplicates),
                "location_conflicts": int(t.conflicts),
            }
            for t in totals
        ],
        "refresh": {
            "oldest_last_successful_refresh_at": _iso(min(refreshed, default=None)),
            "newest_last_successful_refresh_at": _iso(max(refreshed, default=None)),
        },
        "daily_summaries": {
            "rows": int(summaries.rows),
            "locations": int(summaries.locations),
            "first_date": summaries.first_date.isoformat() if summaries.first_date else None,
            "last_date": summaries.last_date.isoformat() if summaries.last_date else None,
        },
        "locations": rows,
    }


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat(timespec="seconds") if value is not None else None
