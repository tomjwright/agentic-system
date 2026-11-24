"""The provider canary, replayed against recorded OneMap and HeiGIT answers."""

import json

import httpx
import pytest

from route_api.canary import run
from route_api.heigit import Heigit
from route_api.onemap import OneMap
from tests import recorded_heigit, recorded_onemap
from tests.conftest import FAKE_HEIGIT_KEY


def clients(
    onemap_handler: httpx.MockTransport, heigit_handler: httpx.MockTransport
) -> tuple[OneMap, Heigit]:
    onemap = OneMap(httpx.Client(transport=onemap_handler), token=None, retry_wait_seconds=0)
    heigit = Heigit(
        httpx.Client(transport=heigit_handler),
        FAKE_HEIGIT_KEY,
        request_gap_seconds=0,
        retry_wait_seconds=0,
    )
    return onemap, heigit


def tokenless_onemap(request: httpx.Request) -> httpx.Response:
    """OneMap's answer to a search without a token: an error beside the usual results."""
    assert request.headers["Authorization"] == ""
    body = json.loads(recorded_onemap.recorded_response(request).content)
    body["error"] = "Authentication token missing."
    return httpx.Response(200, json=body)


def test_recorded_answers_pass_without_a_onemap_token(capsys: pytest.CaptureFixture[str]) -> None:
    onemap, heigit = clients(
        httpx.MockTransport(tokenless_onemap),
        httpx.MockTransport(recorded_heigit.recorded_response),
    )

    assert run(onemap, heigit) == 0
    assert capsys.readouterr().out.splitlines() == [
        "ok   onemap: OneMap search parsed 10 places",
        "ok   running: HeiGIT foot-walking parsed a 17.4 km loop of 482 points",
        "ok   road_cycling: HeiGIT cycling-road parsed a 56.7 km loop of 1622 points",
    ]


def test_a_changed_onemap_answer_fails_naming_the_field(capsys: pytest.CaptureFixture[str]) -> None:
    def renamed_field(request: httpx.Request) -> httpx.Response:
        body = json.loads(recorded_onemap.recorded_response(request).content)
        for result in body["results"]:
            result["LAT"] = result.pop("LATITUDE")
        return httpx.Response(200, json=body)

    onemap, heigit = clients(
        httpx.MockTransport(renamed_field), httpx.MockTransport(recorded_heigit.recorded_response)
    )

    assert run(onemap, heigit) == 1
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line.startswith("FAIL onemap: response no longer parses at results.0.LATITUDE")


def test_a_changed_heigit_answer_fails_without_the_key(capsys: pytest.CaptureFixture[str]) -> None:
    def no_geometry(request: httpx.Request) -> httpx.Response:
        body = json.loads(recorded_heigit.recorded_response(request).content)
        del body["features"][0]["geometry"]
        return httpx.Response(200, json=body)

    onemap, heigit = clients(
        httpx.MockTransport(tokenless_onemap), httpx.MockTransport(no_geometry)
    )

    assert run(onemap, heigit) == 2
    output = capsys.readouterr().out
    assert "FAIL running: provider_response_invalid: HeiGIT returned a route in an" in output
    assert "FAIL road_cycling: provider_response_invalid" in output
    assert FAKE_HEIGIT_KEY not in output


def test_a_refused_key_fails(capsys: pytest.CaptureFixture[str]) -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "Access to this API has been disallowed"})

    onemap, heigit = clients(httpx.MockTransport(tokenless_onemap), httpx.MockTransport(refused))

    assert run(onemap, heigit) == 2
    assert "FAIL running: provider_rejected" in capsys.readouterr().out
