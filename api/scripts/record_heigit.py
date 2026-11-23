"""Record real HeiGIT responses for one generation scenario, for the tests to replay.

Run from api/ with HEIGIT_API_KEY set:
    uv run python scripts/record_heigit.py NAME LON LAT DISTANCE_JSON
e.g. uv run python scripts/record_heigit.py avenue_south_5km 103.8291052120283 \
    1.276629534107344 '{"kind": "target", "target_km": 5}'

Requests already recorded are replayed, not repeated. Each live request is 2 s after the
last, and a scenario makes at most 5 (MAX_ATTEMPTS). Only response bodies are saved;
the key is only ever in the request header.
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
from route_api.route_selection import distance_bounds

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
RECORDINGS = FIXTURES / "heigit_recordings.json"


class RecordingTransport(httpx.BaseTransport):
    def __init__(self, name: str):
        self.name = name
        self.live = httpx.HTTPTransport()
        self.recordings = json.loads(RECORDINGS.read_text())
        self.live_requests = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        for recording in self.recordings:
            if recording["request"] == body and recording["file"] is not None:
                content = (FIXTURES / recording["file"]).read_bytes()
                return httpx.Response(recording["status"], content=content)
        response = self.live.handle_request(request)
        content = response.read()
        self.live_requests += 1
        file = None
        if response.status_code == 200:
            file = f"heigit_{self.name}_{self.live_requests}.json"
            (FIXTURES / file).write_bytes(content)
        self.recordings.append({"request": body, "status": response.status_code, "file": file})
        RECORDINGS.write_text(json.dumps(self.recordings, indent=1) + "\n")
        print(f"live request {self.live_requests}: HTTP {response.status_code}")
        return httpx.Response(response.status_code, content=content)


def main() -> None:
    name, lon, lat, distance_json = sys.argv[1:5]
    distance = TypeAdapter(Distance).validate_json(distance_json)
    transport = RecordingTransport(name)
    heigit = Heigit(httpx.Client(transport=transport), api_key=os.environ["HEIGIT_API_KEY"])
    generation = generate(heigit, (float(lon), float(lat)), distance_bounds(distance))
    for attempt, reasons in zip(
        generation.attempts,
        generation.selection.reasons if generation.selection else [],
        strict=False,
    ):
        print(attempt.method, attempt.parameters["length_m"], reasons)
    if generation.selection:
        print("chosen:", generation.selection.chosen)
    print("error:", generation.error_code, "live requests:", transport.live_requests)


if __name__ == "__main__":
    main()
