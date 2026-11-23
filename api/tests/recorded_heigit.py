"""Replays recorded real HeiGIT directions responses in place of the live service.

`fixtures/heigit_recordings.json` lists each recorded request body with HeiGIT's status
and the file holding its response. Failure bodies are not kept (they echo coordinates),
so a recorded failure replays with a stand-in body. scripts/record_heigit.py records them.
"""

import json
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
RECORDINGS = FIXTURES / "heigit_recordings.json"
STAND_IN_ERROR = b'{"error": {"code": 2099, "message": "recorded failure"}}'


def recorded_response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    for recording in json.loads(RECORDINGS.read_text()):
        if recording["request"] != body:
            continue
        if recording["file"] is None:
            return httpx.Response(recording["status"], content=STAND_IN_ERROR)
        content = (FIXTURES / recording["file"]).read_bytes()
        return httpx.Response(recording["status"], content=content)
    raise LookupError(f"no recorded HeiGIT response for {request.url.path}")
