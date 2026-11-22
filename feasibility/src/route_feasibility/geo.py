"""Small geometry helpers. Coordinates are GeoJSON order: [longitude, latitude]."""

import itertools
import math

EARTH_RADIUS_M = 6_371_008.8
METRES_PER_DEGREE_LAT = math.pi * EARTH_RADIUS_M / 180


def distance_m(a: list[float], b: list[float]) -> float:
    """Great-circle (haversine) distance between two [lon, lat] points."""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2
    h += math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def line_length_m(coordinates: list[list[float]]) -> float:
    total = 0.0
    for a, b in itertools.pairwise(coordinates):
        total += distance_m(a, b)
    return total


def point_to_segment_m(point: list[float], a: list[float], b: list[float]) -> float:
    """Distance from a point to the segment a-b, using a flat local projection.

    Over the few hundred metres this is used for in Singapore, the flat projection
    is accurate to well under a metre.
    """
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


def ring_contains(ring: list[list[float]], point: list[float]) -> bool:
    """Ray-casting point-in-polygon test for one closed ring."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in itertools.pairwise(ring):
        crosses = (y1 > y) != (y2 > y)
        if crosses and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


GRID_CELL_DEGREES = 0.002  # about 220 m


class LineIndex[Item]:
    """Line segments bucketed into a coarse grid, so the nearest line to a point is quick to find.

    Each segment carries the item it came from (a green track, a restricted road).
    """

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], list[tuple[Item, list[float], list[float]]]] = {}

    def add_line(self, item: Item, line: list[list[float]]) -> None:
        for a, b in itertools.pairwise(line):
            x1, x2 = sorted([int(a[0] // GRID_CELL_DEGREES), int(b[0] // GRID_CELL_DEGREES)])
            y1, y2 = sorted([int(a[1] // GRID_CELL_DEGREES), int(b[1] // GRID_CELL_DEGREES)])
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    self.cells.setdefault((x, y), []).append((item, a, b))

    def nearest(self, point: list[float], within_m: float) -> Item | None:
        x = int(point[0] // GRID_CELL_DEGREES)
        y = int(point[1] // GRID_CELL_DEGREES)
        best: Item | None = None
        best_distance = within_m
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for item, a, b in self.cells.get((x + dx, y + dy), []):
                    offset = point_to_segment_m(point, a, b)
                    if offset <= best_distance:
                        best = item
                        best_distance = offset
        return best


def sample_route(coordinates: list[list[float]], spacing_m: float) -> list[tuple[list[float], int]]:
    """Points every spacing_m along the route, each with the index of the vertex it follows."""
    samples = [(coordinates[0], 0)]
    for index in range(len(coordinates) - 1):
        a, b = coordinates[index], coordinates[index + 1]
        steps = max(1, int(distance_m(a, b) // spacing_m))
        for step in range(1, steps + 1):
            fraction = step / steps
            point = [a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction]
            samples.append((point, index))
    return samples
