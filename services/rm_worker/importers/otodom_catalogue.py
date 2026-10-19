"""Fresh Otodom location catalogue from the site's own location sitemap (RM-411, OTO-01c).

LEGAL[scraping]: reads `sitemap_locations_0.xml`, which robots.txt advertises, and one search page per
location to learn its display name; no listing data is kept (RM-411).
LEGAL[third-party-data]: location paths and names only (RM-411).

What the catalogue is, so nobody reads more into it:
- The unit is the **gmina-level place**: a gmina (path depth 3: voivodeship/county/gmina) whenever Otodom
  lists one, otherwise the depth-4 place (city or locality) whose gmina is not listed. A gmina page
  returns its city and villages together, the grain of GUS BDL's whole gminas. Districts (depth 5-6), a
  city or village below a listed gmina, and counties/voivodeships (depth 1-2) are left out, because a
  search for a parent already returns the adverts of its children and the corpus attributes an offer to
  the one location that first saw it: nested places would leave children empty and parents wrong.
  Districts of the big cities are therefore not separate places in this version.
- It is what Otodom itself lists for flats (rent or sale), discovered on the date recorded in the
  provenance. It is not the owner's 727-entry verified list, whose identities no artifact in this
  repository carries; `reconcile` records the difference instead of padding or trimming either side to
  727.
"""

import hashlib
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

from rm_contracts.market import LocationCatalogue, LocationEntry

SITEMAP_URL = "https://www.otodom.pl/sitemap_locations_0.xml"
APPROVED_TARGET = 727  # the owner's stated size (B-023); an identity list was never supplied
FLAT_KINDS = frozenset({"mieszkanie"})
TRANSACTIONS = frozenset({"wynajem", "sprzedaz"})
SETTLEMENT_DEPTHS = (3, 4)
_PATH = re.compile(
    r"[a-z0-9-]+(/[a-z0-9-]+){0,5}"
)  # a settlement is at most depth 4; deeper ones are counted
_LOC = re.compile(r"<loc>\s*(?P<url>[^<\s]+)\s*</loc>")
_RESULTS = re.compile(
    r"^https://www\.otodom\.pl/pl/wyniki/(?P<tx>[a-z]+)/(?P<kind>[a-z]+)(?:,[a-z0-9-]+)*/(?P<path>.+)$"
)


def parse_sitemap(xml: bytes) -> list[tuple[str, str, str]]:
    """(transaction, kind, location path) of every results URL, qualifiers such as `,2-pokoje` stripped.
    Anything that is not a well-formed results URL is skipped, never trusted."""
    found: list[tuple[str, str, str]] = []
    for match in _LOC.finditer(xml.decode("utf-8", errors="replace")):
        hit = _RESULTS.match(match.group("url"))
        if hit is None:
            continue
        path = hit.group("path").split("?")[0].strip("/")
        if _PATH.fullmatch(path):
            found.append((hit.group("tx"), hit.group("kind"), path))
    return found


def flat_paths(entries: Iterable[tuple[str, str, str]]) -> dict[str, set[str]]:
    """Location paths Otodom lists for flats, by transaction."""
    out: dict[str, set[str]] = {tx: set() for tx in TRANSACTIONS}
    for tx, kind, path in entries:
        if tx in TRANSACTIONS and kind in FLAT_KINDS:
            out[tx].add(path)
    return out


def settlement_units(paths: Iterable[str]) -> list[str]:
    """Non-overlapping gmina-level paths (module docstring): every depth-3 gmina, plus every depth-4 place
    whose depth-3 gmina is not listed. Sorted, so the result is deterministic."""
    all_paths = set(paths)
    gminas = {p for p in all_paths if p.count("/") == 2}
    below_listed = {p for p in all_paths if p.count("/") == 3 and "/".join(p.split("/")[:3]) in gminas}
    places = {p for p in all_paths if p.count("/") == 3} - below_listed
    return sorted(gminas | places)


def location_id_for(path: str) -> str:
    """Stable, readable id from the path alone: last segment plus 8 hex of the path's SHA-256."""
    digest = hashlib.sha256(path.encode()).hexdigest()[:8]
    return f"{path.rsplit('/', 1)[-1]}-{digest}"[:64]


def humanize(path: str) -> str:
    """Fallback display name from the slug (no Polish letters): used only until a page read supplies one."""
    return " ".join(path.rsplit("/", 1)[-1].replace("-", " ").split()).title()[:120]


@dataclass(frozen=True)
class Reconciliation:
    """Facts about how the discovered catalogue relates to the owner's stated target."""

    approved_target: int
    discovered: int
    by_transaction: dict[str, int]
    flat_rent_settlements: int
    sale_only_settlements: int
    nested_locations_excluded: dict[str, int]  # by path depth: voivodeship, county, district, sub-district
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved_target": self.approved_target,
            "discovered": self.discovered,
            "difference_from_target": self.discovered - self.approved_target,
            "identity_match_possible": False,
            "places_with_a_flat_rent_landing_page": self.flat_rent_settlements,
            "places_with_only_a_flat_sale_landing_page": self.sale_only_settlements,
            "nested_locations_excluded_by_depth": self.nested_locations_excluded,
            "note": self.note,
        }


def reconcile(by_tx: dict[str, set[str]], units: Sequence[str]) -> Reconciliation:
    rent_units = set(settlement_units(by_tx["wynajem"]))
    union = {p for paths in by_tx.values() for p in paths}
    depth = Counter(p.count("/") + 1 for p in union)
    excluded = {str(d): n for d, n in sorted(depth.items()) if d not in SETTLEMENT_DEPTHS}
    return Reconciliation(
        approved_target=APPROVED_TARGET,
        discovered=len(units),
        by_transaction={tx: len(settlement_units(p)) for tx, p in sorted(by_tx.items())},
        flat_rent_settlements=len(rent_units),
        sale_only_settlements=len(set(units) - rent_units),
        nested_locations_excluded=excluded,
        note=(
            "The owner's 727 identities are not in this repository, so equality cannot be established. "
            "The count is the settlements Otodom lists today, neither trimmed nor padded to 727."
        ),
    )


def build_entries(units: Sequence[str], names: dict[str, str] | None = None) -> list[LocationEntry]:
    names = names or {}
    return [
        LocationEntry(
            location_id=location_id_for(path),
            name=(names.get(path) or humanize(path))[:120],
            otodom_path=path,
        )
        for path in units
    ]


def build_catalogue(version: int, source_ref: str, entries: Sequence[LocationEntry]) -> LocationCatalogue:
    return LocationCatalogue.build(version, source_ref, entries)


def display_name(search_ads: dict[str, Any], path: str) -> str | None:
    """`fullName` of the location a results page answered for, only when it is the location asked for."""
    objects: Any = search_ads.get("locationsObjects")
    if not isinstance(objects, list) or not objects:
        return None
    first = cast("list[Any]", objects)[0]
    if not isinstance(first, dict):
        return None
    got = cast("dict[str, Any]", first)
    if got.get("id") != path:
        return None
    name = got.get("fullName")
    return name.strip()[:120] if isinstance(name, str) and name.strip() else None


ARTIFACT_SCHEMA = 1


class ArtifactError(ValueError):
    """The catalogue artifact is not what `scripts/seed_catalogue.py discover` writes."""


def catalogue_from_artifact(data: dict[str, Any], version: int | None = None) -> LocationCatalogue:
    """Rebuild and verify the catalogue stored in the committed artifact: schema, checksum, no overlap."""
    if data.get("schema") != ARTIFACT_SCHEMA:
        raise ArtifactError("unknown artifact schema")
    rows: Any = data.get("locations")
    if not isinstance(rows, list) or not rows:
        raise ArtifactError("artifact has no locations")
    entries = [
        LocationEntry(location_id=r["location_id"], name=r["name"], otodom_path=r["otodom_path"])
        for r in cast("list[dict[str, Any]]", rows)
    ]
    catalogue = build_catalogue(version or int(data["version"]), str(data["source_ref"]), entries)
    if catalogue.checksum != data.get("checksum"):
        raise ArtifactError("artifact checksum does not match its locations")
    paths = sorted(e.otodom_path for e in entries)
    for earlier, later in pairwise(paths):
        if later.startswith(earlier + "/"):
            raise ArtifactError(f"{later} is nested in {earlier}: one place would hide the other")
    return catalogue
