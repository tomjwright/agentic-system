"""Green-section evidence from NParks Tracks (data.gov.sg d_306cc1018cb733346681883ee6d73054).

A route has a green section where it runs along NParks track segments for at least
MIN_SECTION_M. Only segments with ALLOW_CYCLING == "Y" count as green cycling:
"N" means cycling is not allowed, and a missing value stays unknown. Being near a
park is not evidence: the route must run on (within MATCH_DISTANCE_M of) the track.
"""

from typing import Any, Literal

from pydantic import BaseModel

from route_feasibility.geo import LineIndex, distance_m, sample_route

MATCH_DISTANCE_M = 12.0
SAMPLE_SPACING_M = 10.0
MIN_SECTION_M = 100.0
MAX_BRIDGED_GAP_M = 50.0

Cycling = Literal["allowed", "not allowed", "unknown"]


class Track(BaseModel):
    source_id: str
    park: str
    path_type: str | None
    cycling: Cycling
    updated: str | None
    lines: list[list[list[float]]]


class GreenSection(BaseModel):
    park: str
    cycling: Cycling
    length_m: float
    track_ids: list[str]
    start: list[float]
    end: list[float]

    @property
    def counts_as_green_cycling(self) -> bool:
        return self.cycling == "allowed"


def cycling_permission(value: str | None) -> Cycling:
    if value == "Y":
        return "allowed"
    if value == "N":
        return "not allowed"
    return "unknown"


def load_tracks(geojson: dict[str, Any]) -> list[Track]:
    """Normalize NParks Tracks features, keeping one track per source ID (INC_CRC).

    Duplicate records that disagree about cycling are marked unknown.
    """
    tracks_by_id: dict[str, Track] = {}
    for feature in geojson["features"]:
        properties = feature["properties"]
        geometry = feature["geometry"]
        source_id = properties["INC_CRC"]
        cycling = cycling_permission(properties.get("ALLOW_CYCLING"))
        if source_id in tracks_by_id:
            kept = tracks_by_id[source_id]
            if kept.cycling != cycling:
                kept.cycling = "unknown"
            continue
        if geometry["type"] == "LineString":
            lines = [geometry["coordinates"]]
        else:
            lines = geometry["coordinates"]
        tracks_by_id[source_id] = Track(
            source_id=source_id,
            park=properties.get("PARK") or "unnamed",
            path_type=properties.get("TYPE"),
            cycling=cycling,
            updated=properties.get("FMEL_UPD_D"),
            lines=lines,
        )
    return list(tracks_by_id.values())


def track_index(tracks: list[Track]) -> LineIndex[Track]:
    index: LineIndex[Track] = LineIndex()
    for each_track in tracks:
        for line in each_track.lines:
            index.add_line(each_track, line)
    return index


def find_green_sections(coordinates: list[list[float]], tracks: list[Track]) -> list[GreenSection]:
    """Stretches of the route that run along NParks tracks, grouped by park and permission."""
    index = track_index(tracks)
    sections: list[GreenSection] = []
    current: GreenSection | None = None
    previous_point = coordinates[0]
    for point, _ in sample_route(coordinates, SAMPLE_SPACING_M):
        track = index.nearest(point, MATCH_DISTANCE_M)
        step_m = distance_m(previous_point, point)
        previous_point = point
        same_stretch = (
            current is not None
            and track is not None
            and track.park == current.park
            and track.cycling == current.cycling
        )
        if current is not None and track is not None and same_stretch:
            current.length_m += step_m
            current.end = point
            if track.source_id not in current.track_ids:
                current.track_ids.append(track.source_id)
            continue
        if current is not None and current.length_m >= MIN_SECTION_M:
            sections.append(current)
        current = None
        if track is not None:
            current = GreenSection(
                park=track.park,
                cycling=track.cycling,
                length_m=0.0,
                track_ids=[track.source_id],
                start=point,
                end=point,
            )
    if current is not None and current.length_m >= MIN_SECTION_M:
        sections.append(current)
    return sections


class GreenRun(BaseModel):
    """One unbroken stretch of the route on NParks tracks where cycling is allowed."""

    parks: list[str]
    length_m: float
    bridged_m: float
    track_ids: list[str]


def contiguous_allowed_runs(coordinates: list[list[float]], tracks: list[Track]) -> list[GreenRun]:
    """Stretches of the route on cycling-allowed tracks, joined across park names.

    NParks names one long path by area (East Coast Park Area A, B, ...), so one ride along
    it is several green sections. A run carries on across a gap of up to MAX_BRIDGED_GAP_M
    (a junction, or a crossing where a not-allowed path lies nearer) and counts that gap
    as bridged_m, not as length. A longer gap ends the run.
    """
    index = track_index(tracks)
    runs: list[GreenRun] = []
    current: GreenRun | None = None
    gap_m = 0.0
    previous_point = coordinates[0]
    for point, _ in sample_route(coordinates, SAMPLE_SPACING_M):
        step_m = distance_m(previous_point, point)
        previous_point = point
        track = index.nearest(point, MATCH_DISTANCE_M)
        on_allowed_track = track is not None and track.cycling == "allowed"
        if not on_allowed_track:
            if current is not None:
                gap_m += step_m
                if gap_m > MAX_BRIDGED_GAP_M:
                    current = None
                    gap_m = 0.0
            continue
        assert track is not None
        if current is None:
            current = GreenRun(parks=[], length_m=0.0, bridged_m=0.0, track_ids=[])
            runs.append(current)
        else:
            current.bridged_m += gap_m
            current.length_m += step_m
            gap_m = 0.0
        if track.park not in current.parks:
            current.parks.append(track.park)
        if track.source_id not in current.track_ids:
            current.track_ids.append(track.source_id)
    long_runs = []
    for run in runs:
        if run.length_m >= MIN_SECTION_M:
            long_runs.append(run)
    return long_runs
