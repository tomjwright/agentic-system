"""Print the API's OpenAPI document. The browser types in web/ are generated from it.

Run: uv run python -m route_api.openapi > ../web/openapi.json
"""

import json

import httpx
from sqlalchemy import create_engine

from route_api.heigit import Heigit
from route_api.main import create_app
from route_api.onemap import OneMap
from route_api.restrictions import RestrictedWays


def main() -> None:
    # The document only depends on the routes, so the app needs no token, key or database.
    onemap = OneMap(httpx.Client(), token=None)
    heigit = Heigit(httpx.Client(), api_key=None)
    unused_ways = RestrictedWays(source="unused", ways=[])
    app = create_app(
        onemap, create_engine("sqlite://"), "unused", heigit=heigit, restricted_ways=unused_ways
    )
    print(json.dumps(app.openapi(), indent=2))


if __name__ == "__main__":
    main()
