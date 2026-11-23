"""OneMap place search: the only code that talks to OneMap or reads its token.

The adapter calls one fixed endpoint and sends the token as the `Authorization`
header. It never chooses between matches: every place OneMap returns on the first page
is listed, and the user confirms one. OneMap's string coordinates become
`(longitude, latitude)` numbers.

OneMap answers some failures with HTTP 200, for example an expired token returns an
`error` message and no results. Any `error` in the body is therefore a failure, not
"no match". Errors carry a short code and never OneMap's own text.
"""

import logging
import time

import httpx
from pydantic import BaseModel, ValidationError

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
TIMEOUT = httpx.Timeout(5.0, connect=3.0)
ATTEMPTS = 3
MAX_RESPONSE_BYTES = 256_000  # one page of ten results is about 4 kB
RETRY_STATUSES = {429, 500, 502, 503, 504}

# httpx logs every request URL at INFO, which would put the user's search text in the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)


class ProviderError(Exception):
    """A OneMap failure, as a short code that is safe to show and log."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Place(BaseModel):
    source_id: str  # OneMap has no place ID, so this is its address and coordinates
    name: str
    address: str
    postal: str | None
    coordinates: tuple[float, float]  # (longitude, latitude)


class SearchResult(BaseModel):
    places: list[Place]
    more_results: bool


class OneMapResult(BaseModel):
    """One result as OneMap sends it: coordinates and postcode are strings."""

    SEARCHVAL: str
    ADDRESS: str
    POSTAL: str
    LATITUDE: float
    LONGITUDE: float


class OneMapResponse(BaseModel):
    error: str | None = None
    totalNumPages: int = 0
    results: list[OneMapResult]


class OneMap:
    def __init__(self, http: httpx.Client, token: str | None, retry_wait_seconds: float = 0.5):
        self.http = http
        self.token = token
        self.retry_wait_seconds = retry_wait_seconds

    def search(self, query: str) -> SearchResult:
        if not self.token:
            raise ProviderError("provider_not_configured", "OneMap search is not configured")
        body = self.fetch(query)
        try:
            response = OneMapResponse.model_validate_json(body)
        except ValidationError:
            raise ProviderError(
                "provider_response_invalid", "OneMap returned an unexpected response"
            ) from None
        if response.error:
            raise ProviderError(
                "provider_rejected", "OneMap refused the request; check the OneMap token"
            )
        places = []
        for result in response.results:
            postal: str | None = result.POSTAL
            if postal == "NIL":
                postal = None
            places.append(
                Place(
                    source_id=f"{result.ADDRESS} @ {result.LATITUDE},{result.LONGITUDE}",
                    name=result.SEARCHVAL,
                    address=result.ADDRESS,
                    postal=postal,
                    coordinates=(result.LONGITUDE, result.LATITUDE),
                )
            )
        return SearchResult(places=places, more_results=response.totalNumPages > 1)

    def fetch(self, query: str) -> bytes:
        """GET the first page of results, retrying timeouts and server errors twice."""
        params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": "1"}
        headers = {"Authorization": self.token or ""}
        for attempt in range(1, ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(self.retry_wait_seconds * attempt)
            try:
                with self.http.stream(
                    "GET", SEARCH_URL, params=params, headers=headers, timeout=TIMEOUT
                ) as response:
                    if response.status_code in RETRY_STATUSES:
                        continue
                    if response.status_code != 200:
                        raise ProviderError(
                            "provider_rejected", f"OneMap answered HTTP {response.status_code}"
                        )
                    return read_limited(response)
            except httpx.TransportError:
                continue
        raise ProviderError("provider_unavailable", "OneMap did not answer in time")


def read_limited(response: httpx.Response) -> bytes:
    body = b""
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > MAX_RESPONSE_BYTES:
            raise ProviderError("provider_response_invalid", "OneMap response was too large")
    return body
