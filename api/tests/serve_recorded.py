"""Run the API with OneMap replaced by recorded responses, for the browser tests.

Run: uv run python -m tests.serve_recorded (needs DATABASE_URL, migrated)
"""

import os

import httpx
import uvicorn
from sqlalchemy import create_engine

from route_api.logs import configure_logging
from route_api.main import create_app
from route_api.onemap import OneMap
from tests.recorded_onemap import recorded_response


def main() -> None:
    configure_logging()
    recorded = httpx.Client(transport=httpx.MockTransport(recorded_response))
    onemap = OneMap(recorded, token="recorded-responses")
    engine = create_engine(os.environ["DATABASE_URL"])
    app = create_app(onemap, engine, local_owner="e2e-owner")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")), access_log=False)


if __name__ == "__main__":
    main()
