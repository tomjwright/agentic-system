"""Replays recorded real OneMap search responses in place of the live service."""

from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
RECORDED_QUERIES = {
    "avenue south residence": "onemap_avenue_south_residence.json",
    "avenue south residences": "onemap_avenue_south_residences.json",
    "east coast park": "onemap_east_coast_park.json",
}
NO_MATCH = "onemap_no_match.json"


def recorded_response(request: httpx.Request) -> httpx.Response:
    query = request.url.params["searchVal"].lower()
    fixture = RECORDED_QUERIES.get(query, NO_MATCH)
    return httpx.Response(200, content=(FIXTURES / fixture).read_bytes())
