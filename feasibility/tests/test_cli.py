"""Seam 1: the experiment CLI, run against recorded real HeiGIT, OneMap and NParks responses."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx
import pytest

from route_feasibility.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_KEY = "fake-heigit-key-for-tests"
GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}


class RecordedProviders:
    """Answers HTTP requests with recorded responses and remembers what was sent."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "www.onemap.gov.sg":
            query = request.url.params["searchVal"].replace(" ", "_")
            return self.fixture(f"onemap_{query}.json")
        if request.url.host == "api.heigit.org":
            body = json.loads(request.content)
            seed = body["options"]["round_trip"]["seed"]
            return self.fixture(f"heigit_foot_round_trip_5km_seed{seed}.json")
        return httpx.Response(404)

    def fixture(self, name: str) -> httpx.Response:
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    def heigit_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == "api.heigit.org"]


@pytest.fixture
def providers() -> RecordedProviders:
    return RecordedProviders()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "data"
    folder.mkdir()
    tracks = (FIXTURES / "nparks_tracks_near_avenue_south.geojson").read_text()
    (folder / "nparks_tracks.geojson").write_text(tracks)
    restricted = (FIXTURES / "osm_restricted_ways_near_avenue_south.geojson").read_text()
    (folder / "restricted_ways.geojson").write_text(restricted)
    singapore_box = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[103.6, 1.2], [104.1, 1.2], [104.1, 1.48], [103.6, 1.48], [103.6, 1.2]]
                    ],
                },
            }
        ],
    }
    (folder / "singapore_boundary.geojson").write_text(json.dumps(singapore_box))
    return folder


def run_route(
    providers: RecordedProviders,
    data_dir: Path,
    out_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_args: list[str],
) -> int:
    monkeypatch.setenv("HEIGIT_API_KEY", FAKE_KEY)
    args = [
        "route",
        "--name",
        "test-run",
        "--activity",
        "run",
        "--data-dir",
        str(data_dir),
        "--out",
        str(out_dir),
        "--round-trip",
        "--seeds",
        "1,2",
        "--pause-seconds",
        "0",
        *extra_args,
    ]
    return main(args, transport=httpx.MockTransport(providers.handle))


def gpx_points(path: Path) -> list[list[float]]:
    root = ET.parse(path).getroot()  # noqa: S314 - our own file
    points = []
    for point in root.iterfind(".//gpx:trkpt", GPX_NS):
        points.append([float(point.attrib["lon"]), float(point.attrib["lat"])])
    return points


def route_geojson(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def test_run_within_target_is_reported_with_matching_gpx(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residence", "--distance", "6"]

    exit_code = run_route(providers, data_dir, out, monkeypatch, start)

    report = (out / "test-run.md").read_text()
    assert exit_code == 0
    assert "AVENUE SOUTH RESIDENCE, 11 SILAT AVENUE" in report
    assert "Target: 6 km (accepts 5.40-6.60 km)" in report
    assert "Selected: attempt 1, 6.50 km" in report
    assert len(providers.heigit_requests()) == 1
    route = route_geojson(out / "test-run.geojson")
    coordinates = route["features"][0]["geometry"]["coordinates"]
    assert len(coordinates) == 270
    assert gpx_points(out / "test-run.gpx") == coordinates


def test_missed_target_is_disclosed_and_no_gpx_is_written(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residence", "--distance", "5"]

    exit_code = run_route(providers, data_dir, out, monkeypatch, start)

    report = (out / "test-run.md").read_text()
    assert exit_code == 1
    assert "Target not met after 2 attempts" in report
    assert "| 1 | seed 1 | 6.50 | outside target |" in report
    assert "| 2 | seed 2 | 5.53 | outside target |" in report
    assert not (out / "test-run.gpx").exists()


def test_ambiguous_start_stops_before_any_routing(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residences", "--distance", "6"]

    exit_code = run_route(providers, data_dir, out, monkeypatch, start)

    report = (out / "test-run.md").read_text()
    assert exit_code == 3
    assert "Start needs confirmation" in report
    assert "GRANDEUR PARK RESIDENCES" in report
    assert providers.heigit_requests() == []


def test_confirming_a_listed_place_resolves_the_start(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residences", "--confirm", "GRANDEUR PARK RESIDENCES"]

    run_route(providers, data_dir, out, monkeypatch, [*start, "--distance", "6"])

    report = (out / "test-run.md").read_text()
    assert "Start: GRANDEUR PARK RESIDENCES, 1 BEDOK SOUTH AVENUE 3" in report


def test_green_sections_report_cycling_permission_from_nparks(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residence", "--distance", "5.5", "--require-green"]

    exit_code = run_route(providers, data_dir, out, monkeypatch, start)

    report = (out / "test-run.md").read_text()
    assert exit_code == 0
    assert "no green section where NParks allows cycling" in report
    assert "Selected: attempt 2, 5.53 km" in report
    assert "| AYE (ALEXANDRA RD TO SOUTH BUONA VISTA RD) | allowed | 333 | yes |" in report


def test_restricted_roads_separate_running_beside_from_running_on(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residence", "--distance", "6"]

    exit_code = run_route(providers, data_dir, out, monkeypatch, start)

    report = (out / "test-run.md").read_text()
    assert exit_code == 0
    assert "| expressway | Ayer Rajah Expressway | 2 | 74 | 0 |" in report
    assert "| bicycle=no | Kampong Bahru Road | 3 | 132 | 87 |" in report


def test_api_key_is_sent_only_to_heigit_and_never_written(
    providers: RecordedProviders,
    data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    start = ["--start", "avenue south residence", "--distance", "6"]

    run_route(providers, data_dir, out, monkeypatch, start)

    for request in providers.requests:
        sent_key = request.headers.get("Authorization")
        if request.url.host == "api.heigit.org":
            assert sent_key == FAKE_KEY
        else:
            assert sent_key is None
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out + captured.err
    for written in out.iterdir():
        assert FAKE_KEY not in written.read_text()


def test_missing_api_key_fails_before_any_request(
    providers: RecordedProviders, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HEIGIT_API_KEY", raising=False)
    args = ["route", "--name", "x", "--activity", "run", "--start", "avenue south residence"]
    args += ["--distance", "6", "--data-dir", str(data_dir), "--out", str(tmp_path / "out")]

    exit_code = main(args, transport=httpx.MockTransport(providers.handle))

    assert exit_code == 2
    assert providers.requests == []
