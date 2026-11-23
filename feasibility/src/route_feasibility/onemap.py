"""OneMap search for a named start, with an explicit confirmation step.

A start resolves on its own only when every result is the same building and that
building's name is what was asked for. Anything else needs the user to confirm one
of the listed places (here, the --confirm option).
"""

import re

import httpx
from pydantic import BaseModel

ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
TIMEOUT_SECONDS = 30


class Place(BaseModel):
    name: str
    address: str
    postal: str
    lon: float
    lat: float


class StartResolution(BaseModel):
    query: str
    status: str  # "resolved", "needs confirmation" or "not found"
    place: Place | None
    candidates: list[Place]
    provider_notice: str | None
    reason: str


def simplified(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def search(http: httpx.Client, query: str) -> tuple[list[Place], str | None]:
    params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": "1"}
    response = http.get(ONEMAP_SEARCH_URL, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    places = []
    for result in data.get("results", []):
        places.append(
            Place(
                name=result["SEARCHVAL"],
                address=result["ADDRESS"],
                postal=result["POSTAL"],
                lon=float(result["LONGITUDE"]),
                lat=float(result["LATITUDE"]),
            )
        )
    return places, data.get("error")


def resolve_start(http: httpx.Client, query: str, confirm: str | None) -> StartResolution:
    places, notice = search(http, query)
    names = []
    for place in places:
        if place.name not in names:
            names.append(place.name)

    def result(status: str, place: Place | None, reason: str) -> StartResolution:
        return StartResolution(
            query=query, status=status, place=place, candidates=places,
            provider_notice=notice, reason=reason,
        )  # fmt: skip

    if not places:
        return result("not found", None, "OneMap returned no places")
    if confirm is not None:
        for place in places:
            if place.name == confirm:
                return result("resolved", place, f"confirmed by the user as {confirm}")
        return result("needs confirmation", None, f"{confirm} is not among the results")
    if len(names) == 1 and simplified(names[0]) == simplified(query):
        return result("resolved", places[0], "single building whose name matches the query")
    if len(names) == 1:
        return result(
            "needs confirmation", None, f"the only match, {names[0]}, has a different name"
        )
    return result("needs confirmation", None, f"{len(names)} different places match")
