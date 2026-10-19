"""A small fake of the GUS BDL API in the shapes observed live on 2026-10-20 (RM-48).

Hand-built territory and values (no real statistics). Observed behaviour reproduced: 12-digit unit ids;
`/units` lists whole gminas (types 1-3), urban/rural parts (4, 5), districts (8) and defunct units next to
current ones; `/variables/{id}` has numeric ids and a `years` list; `/data/by-variable/{id}` has no
`page`/`pageSize`, years as strings, `attrId` 1 for a value and 91 for confidential cells (placeholder 0), and
a unit without rows is simply absent from the answer.
"""

import json
from collections import Counter
from dataclasses import dataclass, field

import httpx

COUNTRY = ("000000000000", "POLSKA", 0, None)
WOJ = [("011200000000", "MAŁOPOLSKIE", 2, "010000000000"), ("012400000000", "ŚLĄSKIE", 2, "010000000000")]
POWIAT = [
    ("011212001000", "Powiat bocheński", 5, "011212000000"),
    ("011212161000", "Powiat Kraków", 5, "011212000000"),
    ("012424010000", "Powiat bieruńsko-lędziński", 5, "012424000000"),
    ("011212999000", "Powiat historyczny", 5, "011212000000"),  # no value in the reference year
]
GMINA_ACTIVE = [
    ("011212001011", "Bochnia", 6, "011212001000"),  # type 1, urban
    ("011212001022", "Bochnia", 6, "011212001000"),  # type 2, rural
    ("011212161011", "Kraków", 6, "011212161000"),  # a city with powiat rights
    ("012424010013", "Bieruń", 6, "012424010000"),  # type 3, urban-rural (whole)
]
GMINA_OTHER = [
    ("011212001034", "Bieruń - miasto", 6, "012424010013"),  # type 4: urban part, never a reference unit
    ("012424010015", "Bieruń - obszar wiejski", 6, "012424010013"),  # type 5
    ("011212161088", "Stare Miasto - dzielnica", 6, "011212161011"),  # type 8: a district
    ("011212001052", "Gmina zlikwidowana", 6, "011212001000"),  # type 2, defunct: rows in old years only
]
LEVEL_UNITS = {
    0: [COUNTRY],
    2: WOJ,
    5: POWIAT,
    6: GMINA_ACTIVE + GMINA_OTHER,
}
ACTIVE_YEAR = 2025


def value_for(variable: int, unit: str, year: int) -> int:
    """Deterministic, positive, different per variable, unit and year."""
    return 1000 + (variable % 97) * 10 + int(unit[-4:-1]) + (year - 2015) * 7


@dataclass
class FakeBdl:
    years: dict[int, tuple[int, ...]]  # variable id -> years the variable lists
    unit_of: dict[int, str]  # variable id -> measureUnitName
    withheld: dict[int, set[str]] = field(
        default_factory=dict[int, set[str]]
    )  # variable -> units with attr 91
    missing: dict[int, set[str]] = field(default_factory=dict[int, set[str]])  # variable -> units with no row
    requests: Counter[str] = field(default_factory=Counter[str])

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1")
        q = request.url.params
        if path == "/units":
            self.requests["units"] += 1
            return self._units(int(q["level"]), int(q["page"]), int(q["page-size"]))
        if path.startswith("/variables/"):
            self.requests["variable"] += 1
            vid = int(path.rsplit("/", 1)[1])
            return httpx.Response(
                200,
                json={
                    "id": vid,
                    "subjectId": "P0",
                    "n1": "ogółem",
                    "level": 6,
                    "measureUnitId": 1,
                    "measureUnitName": self.unit_of[vid],
                    "years": list(self.years[vid]),
                },
            )
        if path.startswith("/data/by-variable/"):
            vid = int(path.rsplit("/", 1)[1])
            size = int(q["page-size"])
            self.requests["count" if size == 1 else "data"] += 1
            return self._data(
                vid, int(q["unit-level"]), [int(y) for y in q.get_list("year")], int(q["page"]), size
            )
        return httpx.Response(404)

    def _units(self, level: int, page: int, size: int) -> httpx.Response:
        rows = LEVEL_UNITS[level]
        chunk = rows[page * size : (page + 1) * size]
        results = []
        for uid, name, lvl, parent in chunk:
            row: dict[str, object] = {"id": uid, "name": name, "level": lvl, "hasDescription": False}
            if parent:
                row["parentId"] = parent
            if lvl in (5, 6):
                row["kind"] = uid[-1]
            results.append(row)
        return httpx.Response(
            200, json={"totalRecords": len(rows), "page": page, "pageSize": size, "results": results}
        )

    def _has_rows(self, vid: int, unit: str, years: list[int]) -> bool:
        if unit in self.missing.get(vid, set()):
            return False
        defunct = unit == "011212999000" or (unit == "011212001052" and ACTIVE_YEAR in years)
        return not defunct  # defunct units report nothing in the reference year

    def _data(self, vid: int, level: int, years: list[int], page: int, size: int) -> httpx.Response:
        listed = [u for u in LEVEL_UNITS[level] if self._has_rows(vid, u[0], years)]
        # Units carry rows only for the years the variable lists; parts and districts have rows too.
        wanted = [y for y in years if y in self.years[vid]]
        listed = [u for u in listed if wanted]
        chunk = listed[page * size : (page + 1) * size]
        results = []
        for uid, name, _lvl, _parent in chunk:
            values = []
            for y in wanted:
                if uid in self.withheld.get(vid, set()):
                    values.append({"year": str(y), "val": 0, "attrId": 91})
                else:
                    values.append({"year": str(y), "val": value_for(vid, uid, y), "attrId": 1})
            results.append({"id": uid, "name": name, "values": values})
        body = {
            "totalRecords": len(listed),
            "links": {"first": "x", "self": "x", "next": "x", "last": "x"},
            "variableId": vid,
            "measureUnitId": 1,
            "aggregateId": 1,
            "lastUpdate": None,
            "results": results,
        }
        return httpx.Response(200, content=json.dumps(body))
