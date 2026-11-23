"""Rank candidate long cycling-allowed NParks tracks for the core loop.

    uv run python scripts/rank_green_tracks.py data/nparks_tracks.geojson

For each candidate corridor, keeps NParks Tracks with ALLOW_CYCLING=Y (one per INC_CRC),
joins tracks whose end lies within JOIN_M of another track, and prints the biggest joined
network: its track length, its end-to-end span (how far one ride along it can go) and how
far its nearest point is from the start.
"""

import json
import sys

from route_feasibility.geo import distance_m, line_length_m
from route_feasibility.green import Track, load_tracks

START = [103.82911, 1.27663]  # Avenue South Residence, Silat Avenue (OneMap)
JOIN_M = 15.0
CANDIDATES = {
    "East Coast Park + Coastal PC": ["EAST COAST PARK AREA", "COASTAL PC"],
    "East Coast Park": ["EAST COAST PARK AREA"],
    "Rail Corridor": ["RAIL CORRIDOR"],
    "Punggol Waterway": ["PUNGGOL WATERWAY"],
    "Bishan-Ang Mo Kio Park": ["Bishan-Ang Mo Kio Park"],
}


def in_candidate(track: Track, prefixes: list[str]) -> bool:
    return any(track.park.startswith(prefix) for prefix in prefixes)


def touches(a: Track, b: Track) -> bool:
    for line in a.lines:
        for end in (line[0], line[-1]):
            for other_line in b.lines:
                for point in other_line:
                    if distance_m(end, point) <= JOIN_M:
                        return True
    return False


def biggest_network(tracks: list[Track]) -> list[Track]:
    unvisited = list(tracks)
    biggest: list[Track] = []
    while unvisited:
        network = [unvisited.pop()]
        index = 0
        while index < len(network):
            current = network[index]
            still_unvisited = []
            for other in unvisited:
                if touches(current, other) or touches(other, current):
                    network.append(other)
                else:
                    still_unvisited.append(other)
            unvisited = still_unvisited
            index += 1
        if track_km(network) > track_km(biggest):
            biggest = network
    return biggest


def track_km(tracks: list[Track]) -> float:
    total = 0.0
    for track in tracks:
        for line in track.lines:
            total += line_length_m(line)
    return total / 1000


def span_km(tracks: list[Track]) -> float:
    """The longer of the west-east and south-north extents of the network."""
    first = tracks[0].lines[0][0]
    west, east, south, north = first, first, first, first
    for track in tracks:
        for line in track.lines:
            for point in line:
                if point[0] < west[0]:
                    west = point
                if point[0] > east[0]:
                    east = point
                if point[1] < south[1]:
                    south = point
                if point[1] > north[1]:
                    north = point
    return max(distance_m(west, east), distance_m(south, north)) / 1000


def nearest_km(tracks: list[Track]) -> float:
    nearest = None
    for track in tracks:
        for line in track.lines:
            for point in line:
                metres = distance_m(START, point)
                if nearest is None or metres < nearest:
                    nearest = metres
    return (nearest or 0.0) / 1000


def main() -> None:
    with open(sys.argv[1]) as file:
        tracks = load_tracks(json.load(file))
    allowed = []
    for track in tracks:
        if track.cycling == "allowed":
            allowed.append(track)
    print("| candidate | allowed tracks | biggest joined network km | span km | from start km |")
    print("| --- | --- | --- | --- | --- |")
    for name, prefixes in CANDIDATES.items():
        corridor = []
        for track in allowed:
            if in_candidate(track, prefixes):
                corridor.append(track)
        network = biggest_network(corridor)
        print(
            f"| {name} | {len(corridor)} | {track_km(network):.1f} "
            f"| {span_km(network):.1f} | {nearest_km(network):.1f} |"
        )


if __name__ == "__main__":
    main()
