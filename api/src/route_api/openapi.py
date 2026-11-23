"""Print the API's OpenAPI document. The browser types in web/ are generated from it.

Run: uv run python -m route_api.openapi > ../web/openapi.json
"""

import json

import httpx
from sqlalchemy import create_engine

from route_api.main import create_app
from route_api.onemap import OneMap


def main() -> None:
    # The document only depends on the routes, so the app needs no token or database.
    app = create_app(OneMap(httpx.Client(), token=None), create_engine("sqlite://"), "unused")
    print(json.dumps(app.openapi(), indent=2))


if __name__ == "__main__":
    main()
