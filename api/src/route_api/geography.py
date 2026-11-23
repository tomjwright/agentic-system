"""Is a point on Singapore's land? Uses the outline built by scripts/build_singapore_land.py."""

import itertools
import json
import math
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


EARTH_RADIUS_M = 6_371_008.8
METRES_PER_DEGREE_LAT = math.pi * EARTH_RADIUS_M / 180


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle (haversine) distance between two (longitude, latitude) points."""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2
    h += math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def line_length_m(coordinates: list[tuple[float, float]]) -> float:
    total = 0.0
    for a, b in itertools.pairwise(coordinates):
        total += distance_m(a, b)
    return total


def distance_to_land_edge_m(lon: float, lat: float) -> float:
    nearest = math.inf
    for polygon in LAND_POLYGONS:
        for ring in polygon:
            for a, b in itertools.pairwise(ring):
                nearest = min(nearest, point_to_segment_m((lon, lat), a, b))
    return nearest


def point_to_segment_m(point: tuple[float, float], a: list[float], b: list[float]) -> float:
    """Distance from a point to the segment a-b, on a flat local projection (fine at city scale)."""
    metres_per_degree_lon = METRES_PER_DEGREE_LAT * math.cos(math.radians(point[1]))
    px = (point[0] - a[0]) * metres_per_degree_lon
    py = (point[1] - a[1]) * METRES_PER_DEGREE_LAT
    bx = (b[0] - a[0]) * metres_per_degree_lon
    by = (b[1] - a[1]) * METRES_PER_DEGREE_LAT
    segment_length_squared = bx * bx + by * by
    if segment_length_squared == 0:
        return math.hypot(px, py)
    t = (px * bx + py * by) / segment_length_squared
    t = max(0.0, min(1.0, t))
    return math.hypot(px - t * bx, py - t * by)


def offset(point: tuple[float, float], metres: float, bearing_deg: float) -> tuple[float, float]:
    """The point `metres` away along a compass bearing, on a flat local projection."""
    bearing = math.radians(bearing_deg)
    metres_per_degree_lon = METRES_PER_DEGREE_LAT * math.cos(math.radians(point[1]))
    lon = point[0] + metres * math.sin(bearing) / metres_per_degree_lon
    lat = point[1] + metres * math.cos(bearing) / METRES_PER_DEGREE_LAT
    return (round(lon, 6), round(lat, 6))
