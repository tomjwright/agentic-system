"""Build the simplified Singapore land outline used for start validation.

Input: data.gov.sg "Master Plan 2019 Planning Area Boundary (No Sea)"
(d_4765db0e87b9c86336792efe8a1f7a66, Singapore Open Data Licence v1.0), downloaded with
the poll-download API. The 55 planning areas are merged, widened by about 50 m so
points on the shoreline still count, and simplified to keep the file small.

Run: uv run --with shapely python scripts/build_singapore_land.py boundary.geojson
"""

import json
import sys
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

BUFFER_DEGREES = 0.00045  # about 50 m at Singapore's latitude
SIMPLIFY_DEGREES = 0.0002  # about 22 m
OUTPUT = Path(__file__).parent.parent / "src" / "route_api" / "singapore_land.geojson"


def main() -> None:
    source = json.loads(Path(sys.argv[1]).read_text())
    areas = []
    for feature in source["features"]:
        areas.append(shape(feature["geometry"]))
    land = unary_union(areas).buffer(BUFFER_DEGREES).simplify(SIMPLIFY_DEGREES)
    outline = {
        "type": "Feature",
        "properties": {
            "source": "data.gov.sg d_4765db0e87b9c86336792efe8a1f7a66",
            "licence": "Singapore Open Data Licence v1.0",
            "buffer_m": 50,
        },
        "geometry": mapping(land),
    }
    OUTPUT.write_text(json.dumps(outline, separators=(",", ":")) + "\n")
    print(f"{land.geom_type}, {len(json.dumps(outline))} bytes -> {OUTPUT}")


main()
