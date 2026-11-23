"""Seam 3: which parts of a route are a green section where cycling is allowed."""

from typing import Any

from route_feasibility.green import find_green_sections, load_tracks

# About 500 m of path due east along latitude 1.3000.
TRACK_LINE = [[103.8000, 1.3000], [103.8045, 1.3000]]
# A route that runs about 1 m north of that path, starting and ending off it.
ROUTE_ALONG_TRACK = [[103.7990, 1.30001], [103.8055, 1.30001]]


def nparks_tracks(*features: dict[str, Any]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


def track(
    allow_cycling: str | None, crc: str = "AAA111", park: str = "EAST COAST PK"
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": TRACK_LINE},
        "properties": {
            "OBJECTID": 1,
            "PARK": park,
            "TYPE": "Cycle Track",
            "ALLOW_CYCLING": allow_cycling,
            "INC_CRC": crc,
            "FMEL_UPD_D": "20250827103208",
        },
    }


def test_route_along_a_cycling_allowed_track_is_a_green_section() -> None:
    tracks = load_tracks(nparks_tracks(track("Y")))

    sections = find_green_sections(ROUTE_ALONG_TRACK, tracks)

    assert len(sections) == 1
    section = sections[0]
    assert section.park == "EAST COAST PK"
    assert section.cycling == "allowed"
    assert section.counts_as_green_cycling
    assert section.track_ids == ["AAA111"]
    # The 500 m track, give or take the 12 m matching distance at each end.
    assert 470 <= section.length_m <= 530


def test_track_where_cycling_is_not_allowed_never_counts() -> None:
    tracks = load_tracks(nparks_tracks(track("N")))

    sections = find_green_sections(ROUTE_ALONG_TRACK, tracks)

    assert [(s.park, s.cycling, s.counts_as_green_cycling) for s in sections] == [
        ("EAST COAST PK", "not allowed", False)
    ]


def test_track_with_no_cycling_value_stays_unknown_and_never_counts() -> None:
    tracks = load_tracks(nparks_tracks(track(None)))

    sections = find_green_sections(ROUTE_ALONG_TRACK, tracks)

    assert [(s.cycling, s.counts_as_green_cycling) for s in sections] == [("unknown", False)]


def test_route_near_a_park_but_not_on_its_track_has_no_green_section() -> None:
    tracks = load_tracks(nparks_tracks(track("Y")))
    # Parallel to the track but 0.0005 degrees (about 56 m) north of it.
    route_beside_park = [[103.7990, 1.3005], [103.8055, 1.3005]]

    assert find_green_sections(route_beside_park, tracks) == []


def test_short_brush_with_a_track_is_not_a_green_section() -> None:
    tracks = load_tracks(nparks_tracks(track("Y")))
    # Crosses the track at right angles: only a few metres are on it.
    route_crossing_track = [[103.8020, 1.2990], [103.8020, 1.3010]]

    assert find_green_sections(route_crossing_track, tracks) == []


def test_duplicate_source_records_are_loaded_once() -> None:
    tracks = load_tracks(nparks_tracks(track("Y", crc="DUP1"), track("Y", crc="DUP1")))

    assert [t.source_id for t in tracks] == ["DUP1"]


def test_duplicates_that_disagree_on_cycling_become_unknown() -> None:
    tracks = load_tracks(nparks_tracks(track("Y", crc="DUP1"), track("N", crc="DUP1")))

    assert [t.cycling for t in tracks] == ["unknown"]
