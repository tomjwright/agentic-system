"""Provider canary: one real OneMap search and two real HeiGIT directions requests.

Run nightly by .github/workflows/provider-canary.yml with HEIGIT_API_KEY set:
    uv run python -m route_api.canary
It goes through the API's own clients and response models, so a provider that changes
its answer fails here before users see it. Three requests normally, at most seven if
every retry fires, well inside HeiGIT's 40 a minute.

OneMap is searched without a token. Its answer then carries an `error` saying the token
is missing, next to the same results a signed request gets, so the canary checks the
results parse and ignores that `error`. An expired ONEMAP_API_TOKEN therefore never
turns the canary red; the token is renewed by hand.

Output is a line per check with distances and counts only: no key, token or coordinates.
"""

import os
import sys

import httpx
from pydantic import ValidationError

from route_api.heigit import PROFILES, Heigit, HeigitError, via_loop_body
from route_api.onemap import OneMap, OneMapResponse, ProviderError

QUERY = "east coast park"
# The same loops as tests/fixtures/heigit_pasir_ris_15km_via_1.json and
# heigit_avenue_south_ride_50km_1.json, so the tests replay their recorded answers.
LOOPS = {
    "running": (
        (103.9471253158095, 1.380999388858507),
        [(103.933381, 1.359011), (103.911387, 1.372751), (103.925131, 1.394739)],
    ),
    "road_cycling": (
        (103.8291052120283, 1.276629534107344),
        [(103.760983, 1.329838), (103.814206, 1.397942), (103.882329, 1.344734)],
    ),
}


class CanaryFailure(Exception):
    pass


def check_onemap(onemap: OneMap) -> str:
    response = OneMapResponse.model_validate_json(onemap.fetch(QUERY))
    if not response.results:
        raise CanaryFailure(f"OneMap found nothing for {QUERY!r}")
    return f"OneMap search parsed {len(response.results)} places"


def check_heigit(heigit: Heigit, activity: str) -> str:
    start, via = LOOPS[activity]
    route = heigit.route(activity, via_loop_body(activity, start, via))
    if route.distance_m <= 0 or not route.surfaces_m:
        raise CanaryFailure(f"HeiGIT {PROFILES[activity]} returned an empty route")
    return (
        f"HeiGIT {PROFILES[activity]} parsed a {route.distance_m / 1000:.1f} km loop"
        f" of {len(route.coordinates)} points"
    )


def run(onemap: OneMap, heigit: Heigit) -> int:
    """Run every check, print one line each, and return how many failed."""
    failures = 0
    for name in ["onemap", "running", "road_cycling"]:
        try:
            result = check_onemap(onemap) if name == "onemap" else check_heigit(heigit, name)
            print(f"ok   {name}: {result}")
        except ValidationError as error:
            fields = []
            for each in error.errors():
                fields.append(".".join(str(part) for part in each["loc"]))
            print(f"FAIL {name}: response no longer parses at {', '.join(fields)}")
            failures += 1
        except (ProviderError, HeigitError) as error:
            print(f"FAIL {name}: {error.code}: {error}")
            failures += 1
        except CanaryFailure as error:
            print(f"FAIL {name}: {error}")
            failures += 1
    return failures


def main() -> None:
    onemap = OneMap(httpx.Client(), token=None)
    heigit = Heigit(httpx.Client(), api_key=os.environ.get("HEIGIT_API_KEY"))
    if run(onemap, heigit):
        sys.exit(1)


if __name__ == "__main__":
    main()
