"""Build the Rynek map geometry from the official PRG administrative boundaries (RM-282).

Run (the two libraries are build-time only and are not project dependencies):

  uvx --with pyshp --with shapely python scripts/build_map_geometry.py <dir with the PRG shapefiles> frontend/public/geo

Input: `A01_Granice_wojewodztw` and `A03_Granice_gmin` from GUGiK's Państwowy Rejestr Granic
(https://opendata.geoportal.gov.pl/prg/granice/00_jednostki_administracyjne.zip, ETRS89 longitude/latitude, free of
charge; attribution "Źródło: Państwowy Rejestr Granic, GUGiK"). Output: `gminas.json` (every current gmina keyed by its
7-digit TERYT code, simplified to about 400 m, with one interior point each) and `wojewodztwa.json` (16 outlines).
Joined to Renti data by TERYT code, never by name. Nothing here is a listing position.

LEGAL[third-party-data]: official public boundaries; source terms to be confirmed with counsel (B-012) (RM-282).
"""

import json
import sys
from pathlib import Path
from typing import Any

import shapefile  # type: ignore[import-not-found]
from shapely.geometry import shape  # type: ignore[import-not-found]

GMINA_TOLERANCE = 0.004  # degrees, about 400 m
VOIVODESHIP_TOLERANCE = 0.01
DECIMALS = 3
SOURCE = "Państwowy Rejestr Granic, GUGiK"


def rings(geometry: Any, tolerance: float) -> list[list[list[float]]]:
    simple = geometry.simplify(tolerance, preserve_topology=True)
    parts = [simple] if simple.geom_type == "Polygon" else list(simple.geoms)
    return [
        [[round(x, DECIMALS), round(y, DECIMALS)] for x, y in part.exterior.coords]
        for part in parts
        if not part.is_empty
    ]


def read(path: Path, key: str, tolerance: float) -> tuple[dict[str, Any], dict[str, list[float]], list[float]]:
    reader = shapefile.Reader(str(path), encoding="utf-8")
    shapes: dict[str, Any] = {}
    points: dict[str, list[float]] = {}
    for item in reader.iterShapeRecords():
        code = str(item.record[key])
        geometry = shape(item.shape.__geo_interface__)
        shapes[code] = rings(geometry, tolerance)
        inside = geometry.representative_point()
        points[code] = [round(inside.x, DECIMALS), round(inside.y, DECIMALS)]
    return shapes, points, [round(v, DECIMALS) for v in reader.bbox]


def main(source: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    gminas, points, bbox = read(source / "A03_Granice_gmin", "JPT_KOD_JE", GMINA_TOLERANCE)
    voivodeships, _, _ = read(source / "A01_Granice_wojewodztw", "JPT_KOD_JE", VOIVODESHIP_TOLERANCE)
    (out / "gminas.json").write_text(
        json.dumps({"source": SOURCE, "bbox": bbox, "gminas": gminas, "points": points}, separators=(",", ":"))
    )
    (out / "wojewodztwa.json").write_text(
        json.dumps({"source": SOURCE, "bbox": bbox, "wojewodztwa": voivodeships}, separators=(",", ":"))
    )
    print(f"{len(gminas)} gminas, {len(voivodeships)} voivodeships -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
