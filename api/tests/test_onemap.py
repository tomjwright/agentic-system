"""Seam 2: the OneMap geocoder adapter, against recorded real OneMap responses."""

import json

import httpx
import pytest

from route_api.onemap import OneMap, ProviderError
from tests.recorded_onemap import FIXTURES, recorded_response

FAKE_TOKEN = "fake-onemap-token-for-tests"


def onemap_with(handler: httpx.MockTransport) -> OneMap:
    return OneMap(httpx.Client(transport=handler), token=FAKE_TOKEN, retry_wait_seconds=0)


def test_string_coordinates_become_lon_lat_numbers() -> None:
    onemap = onemap_with(httpx.MockTransport(recorded_response))

    result = onemap.search("avenue south residence")

    first = result.places[0]
    assert first.name == "AVENUE SOUTH RESIDENCE"
    assert first.address == "11 SILAT AVENUE AVENUE SOUTH RESIDENCE SINGAPORE 168877"
    assert first.postal == "168877"
    assert first.coordinates == (103.8291052120283, 1.276629534107344)
    assert len(result.places) == 7


def test_every_match_is_listed_and_none_is_chosen() -> None:
    onemap = onemap_with(httpx.MockTransport(recorded_response))

    result = onemap.search("avenue south residences")

    names = {place.name for place in result.places}
    assert names == {"GRANDEUR PARK RESIDENCES"}
    assert len(result.places) == 6


def test_missing_postcode_is_none_and_extra_pages_are_flagged() -> None:
    onemap = onemap_with(httpx.MockTransport(recorded_response))

    result = onemap.search("east coast park")

    area_a = result.places[2]
    assert area_a.name == "EAST COAST PARK AREA A"
    assert area_a.postal is None
    assert result.more_results is True


def test_token_goes_only_to_the_fixed_endpoint_as_a_header() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return recorded_response(request)

    onemap_with(httpx.MockTransport(handler)).search("https://evil.example/steal")

    request = sent[0]
    assert str(request.url).startswith("https://www.onemap.gov.sg/api/common/elastic/search?")
    assert request.url.params["searchVal"] == "https://evil.example/steal"
    assert request.headers["Authorization"] == FAKE_TOKEN
    assert FAKE_TOKEN not in str(request.url)


def test_requests_have_bounded_timeouts() -> None:
    timeouts: list[dict[str, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions["timeout"])
        return recorded_response(request)

    onemap_with(httpx.MockTransport(handler)).search("avenue south residence")

    for seconds in timeouts[0].values():
        assert 0 < seconds <= 10


def test_no_token_means_no_request() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return recorded_response(request)

    onemap = OneMap(httpx.Client(transport=httpx.MockTransport(handler)), token=None)

    with pytest.raises(ProviderError) as error:
        onemap.search("avenue south residence")

    assert error.value.code == "provider_not_configured"
    assert sent == []


def test_expired_token_is_a_provider_error_not_an_empty_result() -> None:
    # OneMap's documented reply to an expired token: HTTP 200 with an error and no results.
    expired = {
        "error": "Authentication token expired. Tokens is valid for 3 days.",
        "found": 0,
        "totalNumPages": 0,
        "pageNum": 0,
        "results": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=expired)

    with pytest.raises(ProviderError) as error:
        onemap_with(httpx.MockTransport(handler)).search("avenue south residence")

    assert error.value.code == "provider_rejected"
    assert "expired" not in str(error.value)


def test_timeouts_are_retried_a_bounded_number_of_times() -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ProviderError) as error:
        onemap_with(httpx.MockTransport(handler)).search("avenue south residence")

    assert error.value.code == "provider_unavailable"
    assert len(attempts) == 3


def test_a_server_error_then_success_returns_the_places() -> None:
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(503)
        return recorded_response(request)

    result = onemap_with(httpx.MockTransport(handler)).search("avenue south residence")

    assert len(result.places) == 7


def test_oversized_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"results": [' + b" " * 300_000 + b"]}")

    with pytest.raises(ProviderError) as error:
        onemap_with(httpx.MockTransport(handler)).search("avenue south residence")

    assert error.value.code == "provider_response_invalid"


def test_malformed_coordinates_are_rejected() -> None:
    body = json.loads((FIXTURES / "onemap_avenue_south_residence.json").read_text())
    body["results"][0]["LATITUDE"] = "not a number"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(ProviderError) as error:
        onemap_with(httpx.MockTransport(handler)).search("avenue south residence")

    assert error.value.code == "provider_response_invalid"
