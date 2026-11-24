"""Record real HeiGIT responses for one generation scenario, for the tests to replay.

Run from api/ with HEIGIT_API_KEY set:
    uv run python scripts/record_heigit.py NAME ACTIVITY LON LAT DISTANCE_JSON
e.g. uv run python scripts/record_heigit.py avenue_south_5km running 103.8291052120283 \
    1.276629534107344 '{"kind": "target", "target_km": 5}'

Requests already recorded, failures included, are replayed, not repeated. Each live
request is 2 s after the last, and a scenario makes at most 5 (MAX_ATTEMPTS). Only
response bodies are saved; the key is only ever in the request header.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from pydantic import TypeAdapter

from route_api.contracts import Distance
from route_api.generation import generate
from route_api.heigit import Heigit
from route_api.restrictions import load_restricted_ways
from route_api.route_selection import distance_bounds

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
RECORDINGS = FIXTURES / "heigit_recordings.json"
STAND_IN_ERROR = b'{"error": {"code": 2099, "message": "recorded failure"}}'


class RecordingTransport(httpx.BaseTransport):
    def __init__(self, name: str):
        self.name = name
        self.live = httpx.HTTPTransport()
        self.recordings = json.loads(RECORDINGS.read_text())
        self.live_requests = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        profile = request.url.path.split("/")[-2]
        for recording in self.recordings:
            same_profile = recording.get("profile", "foot-walking") == profile
            if recording["request"] != body or not same_profile:
                continue
            content = STAND_IN_ERROR
            if recording["file"] is not None:
                content = (FIXTURES / recording["file"]).read_bytes()
            return httpx.Response(recording["status"], content=content)
        response = self.live.handle_request(request)
        content = response.read()
        self.live_requests += 1
        file = None
        if response.status_code == 200:
            number = self.live_requests
            while (FIXTURES / f"heigit_{self.name}_{number}.json").exists():
                number += 1
            file = f"heigit_{self.name}_{number}.json"
            (FIXTURES / file).write_bytes(content)
        recording = {"request": body, "profile": profile, "status": response.status_code}
        recording["file"] = file
        self.recordings.append(recording)
        RECORDINGS.write_text(json.dumps(self.recordings, indent=1) + "\n")
        print(f"live request {self.live_requests}: HTTP {response.status_code}")
        return httpx.Response(response.status_code, content=content)


def main() -> None:
    name, activity, lon, lat, distance_json = sys.argv[1:6]
    distance = TypeAdapter(Distance).validate_json(distance_json)
    transport = RecordingTransport(name)
    heigit = Heigit(httpx.Client(transport=transport), api_key=os.environ["HEIGIT_API_KEY"])
    start = (float(lon), float(lat))
    ways = load_restricted_ways()
    generation = generate(heigit, activity, start, distance_bounds(distance), ways)
    for attempt, reasons in zip(
        generation.attempts,
        generation.selection.reasons if generation.selection else [],
        strict=False,
    ):
        print(attempt.method, attempt.parameters["length_m"], reasons)
        for road in attempt.restricted_roads or []:
            print("   ", road.outcome, road.kind, road.name, road.near_m, road.on_m)
    if generation.selection:
        print("chosen:", generation.selection.chosen)
    print("error:", generation.error_code, "live requests:", transport.live_requests)


if __name__ == "__main__":
    main()
