"""Is a point on Singapore's land? Uses the outline built by scripts/build_singapore_land.py."""

import json
from pathlib import Path

OUTLINE = Path(__file__).parent / "singapore_land.geojson"
LAND_POLYGONS = json.loads(OUTLINE.read_text())["geometry"]["coordinates"]


def on_singapore_land(lon: float, lat: float) -> bool:
    for polygon in LAND_POLYGONS:
        outer_ring = polygon[0]
        holes = polygon[1:]
        if not inside_ring(lon, lat, outer_ring):
            continue
        in_a_hole = False
        for hole in holes:
            if inside_ring(lon, lat, hole):
                in_a_hole = True
        if not in_a_hole:
            return True
    return False


def inside_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    """Ray casting: count how many ring edges a line going east from the point crosses."""
    inside = False
    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        crosses_row = (current_y > y) != (previous_y > y)
        if crosses_row:
            edge_x = current_x + (y - current_y) * (previous_x - current_x) / (
                previous_y - current_y
            )
            if x < edge_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside
