"""Seam 3: which parts of a route are a green section where cycling is allowed."""

from typing import Any

from route_feasibility.green import contiguous_allowed_runs, find_green_sections, load_tracks

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


# Paths that carry straight on east from TRACK_LINE: one 30 m, one 500 m after it.
SHORT_TRACK_LINE = [[103.8045, 1.3000], [103.80477, 1.3000]]
NEXT_TRACK_LINE = [[103.8045, 1.3000], [103.8090, 1.3000]]
LAST_TRACK_LINE = [[103.80477, 1.3000], [103.80927, 1.3000]]
ROUTE_ALONG_ALL_TRACKS = [[103.7990, 1.30001], [103.8100, 1.30001]]


def track_on(line: list[list[float]], allow_cycling: str, crc: str, park: str) -> dict[str, Any]:
    feature = track(allow_cycling, crc=crc, park=park)
    feature["geometry"] = {"type": "LineString", "coordinates": line}
    return feature


def test_allowed_tracks_that_join_end_to_end_are_one_contiguous_run() -> None:
    tracks = load_tracks(
        nparks_tracks(
            track("Y", crc="AREA_A", park="EAST COAST PARK AREA A"),
            track_on(NEXT_TRACK_LINE, "Y", crc="AREA_B", park="EAST COAST PARK AREA B"),
        )
    )

    runs = contiguous_allowed_runs(ROUTE_ALONG_ALL_TRACKS, tracks)

    assert len(runs) == 1
    run = runs[0]
    assert run.parks == ["EAST COAST PARK AREA A", "EAST COAST PARK AREA B"]
    assert run.track_ids == ["AREA_A", "AREA_B"]
    assert run.bridged_m == 0
    # Two 500 m tracks, give or take the 12 m matching distance at each end.
    assert 970 <= run.length_m <= 1030


def test_a_short_crossing_where_cycling_is_not_allowed_is_bridged() -> None:
    tracks = load_tracks(
        nparks_tracks(
            track("Y", crc="AREA_A", park="EAST COAST PARK AREA A"),
            track_on(SHORT_TRACK_LINE, "N", crc="NO_BIKES", park="EAST COAST PARK AREA A"),
            track_on(LAST_TRACK_LINE, "Y", crc="AREA_B", park="EAST COAST PARK AREA B"),
        )
    )

    runs = contiguous_allowed_runs(ROUTE_ALONG_ALL_TRACKS, tracks)

    assert len(runs) == 1
    run = runs[0]
    assert run.track_ids == ["AREA_A", "AREA_B"]
    # The 30 m path, less the ends that match the allowed tracks on either side.
    assert 10 <= run.bridged_m <= 50


def test_a_long_stretch_where_cycling_is_not_allowed_ends_the_run() -> None:
    tracks = load_tracks(
        nparks_tracks(
            track("Y", crc="AREA_A", park="EAST COAST PARK AREA A"),
            track_on(NEXT_TRACK_LINE, "N", crc="NO_BIKES", park="EAST COAST PARK AREA B"),
        )
    )

    runs = contiguous_allowed_runs(ROUTE_ALONG_ALL_TRACKS, tracks)

    assert [(r.parks, r.track_ids) for r in runs] == [(["EAST COAST PARK AREA A"], ["AREA_A"])]


# A second allowed track that starts 66 m after TRACK_LINE ends. Between the last route
# point matched to one track and the first matched to the other, the route covers more
# than the 50 m bridging limit, counting the step back onto the track.
TRACK_AFTER_GAP = [[103.805093, 1.3000], [103.809593, 1.3000]]
ROUTE_ACROSS_GAP = [[103.7990, 1.30001], [103.8107, 1.30001]]


def test_a_gap_just_over_the_bridging_limit_ends_the_run() -> None:
    tracks = load_tracks(
        nparks_tracks(
            track("Y", crc="AREA_A", park="EAST COAST PARK AREA A"),
            track_on(TRACK_AFTER_GAP, "Y", crc="AREA_B", park="EAST COAST PARK AREA B"),
        )
    )

    runs = contiguous_allowed_runs(ROUTE_ACROSS_GAP, tracks)

    assert [r.track_ids for r in runs] == [["AREA_A"], ["AREA_B"]]
