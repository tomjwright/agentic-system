# route-api

Backend for the Singapore route creator. Issue #10 resolves and confirms a route's
starting place; issue #3 generates, inspects and exports a running loop from it. There
are no cycling routes or model calls yet.

1. `POST /api/places/search` sends the query to OneMap and lists every match on Singapore
   land (`no_match`, `single_match` or `multiple_matches`). It never chooses one: the
   plural "Avenue South Residences" matches Grandeur Park Residences in Bedok, while the
   singular finds the Silat Avenue blocks.
2. `POST /api/route-requests` stores the activity and the confirmed start: a OneMap
   match (searched again on the server so the stored place is OneMap's, with its query,
   `source_id` and retrieval time) or a map point. Points off Singapore land are refused.
3. `GET /api/route-requests/{id}` returns a request only to its owner.
4. `POST /api/route-requests/{id}/runs` with `operation_id` (a UUID the client makes) and
   a distance generates a running loop and returns the finished run (HTTP 201). The
   distance is `{"kind": "target", "target_km": 5}` (any loop within 10% either side)
   or `{"kind": "range", "min_km": 5, "max_km": 6}` (exact, no tolerance added), 1 to
   50 km. Each run adds a new immutable revision of the request. Sending the same
   `operation_id` again returns the run already recorded (HTTP 200); with a different
   distance it is HTTP 409 `operation_conflict`. Road cycling is HTTP 422
   `activity_not_supported` for now.
5. `GET /api/runs/{id}` is the run: `status` (`generating`, `succeeded`, `no_route`,
   `failed`), the distance bounds, and every candidate with its seed or via points,
   requested length, measured distance and rejection reasons.
6. `GET /api/runs/{id}/route` is the selected loop: its GeoJSON `LineString`, measured
   distance and deviation from the target, HeiGIT's foot-walking time (not a running
   time), surfaces with the unknown share, limitations and attribution.
7. `GET /api/runs/{id}/route.gpx` is the same stored geometry as GPX 1.1, point for point.

## How a loop is generated

`generation.py` asks HeiGIT `foot-walking` for at most 5 candidates, one at a time,
2 s apart: round trips with seeds 1, 2, 3, ... and the requested length corrected by
the last measured length; after 2 failed round trips it switches to a loop through
two via points placed inland of the start (round trips from the coast can cross the
sea). `route_selection.py` rejects any candidate that is not closed (30 m), starts more
than 200 m from the confirmed start, leaves Singapore (50 m), disagrees with HeiGIT's
own distance by over 10%, or whose measured length is outside the bounds. The accepted
one closest to the target wins; if none, the run is `no_route` with every reason.
Nothing is ever moved, trimmed or rerouted to pass.

Generation runs inside the POST (at most about 2 minutes with 5 slow HeiGIT calls);
it is not a durable background job. A run left `generating` for 10 minutes (the
process died) reads as `failed` with `generation_interrupted`.

HeiGIT failures: HTTP 429 is `provider_quota_exhausted` and 401/403
`provider_rejected` (the run fails, no further tries); a timeout or 502-504 is retried
once, then `provider_unavailable`; 404/500 (no route between the points) rejects that
candidate only; a body that is not one closed GeoJSON `LineString` with metre units is
`provider_response_invalid`. HeiGIT's error bodies echo coordinates, so they are never
returned, stored or logged.

Points are GeoJSON, `coordinates` = `[longitude, latitude]`. Errors are
`{"error": {"code", "message"}}`; the codes are listed in `contracts.py`.

## Run

```bash
docker run -d --name routes-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=routes postgres:17
export DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes
uv sync
uv run alembic upgrade head
ONEMAP_API_TOKEN=... HEIGIT_API_KEY=... uv run uvicorn route_api.main:app_from_env --factory --port 8000 --no-access-log
cd ../web && npm ci && npm run dev    # http://localhost:3000, forwards /api to port 8000
```

Owners: there is no sign-in yet. The owner is the `X-Owner-Id` header, or
`LOCAL_OWNER_ID` (default `local-owner`). Anyone who can reach the API can claim any
owner, so keep it on localhost until managed sign-in (issue #5) lands.

Logs are one JSON object per line with the `X-Request-ID` (sent back on every response).
They never contain search text, coordinates, the token or the key. Set
`OTEL_EXPORTER_OTLP_ENDPOINT` to export spans for each HeiGIT call, generation and
database write (no coordinates in their attributes).

## OneMap token

OneMap's terms require a registered account. `ONEMAP_API_TOKEN` is the access token
from OneMap's `POST https://www.onemap.gov.sg/api/auth/post/getToken` with the account's
email and password. Tokens last 3 days (the JWT's `exp` claim), and OneMap does not
refresh them: get a new one with `getToken` and replace the secret. Only Tom has the
account, so renewal is his.

An expired or wrong token makes OneMap answer HTTP 200 with an `error` field. The API
turns that into HTTP 502 `provider_rejected` ("check the OneMap token"); a missing
token is HTTP 503 `provider_not_configured`. Neither crashes the API.

To check when the current token expires without printing it:

```bash
python3 -c "import base64,json,os,datetime; p=os.environ['ONEMAP_API_TOKEN'].split('.')[1]; print(datetime.datetime.fromtimestamp(json.loads(base64.urlsafe_b64decode(p+'==')).get('exp'), datetime.UTC))"
```

## Recording HeiGIT responses

`scripts/record_heigit.py` runs one scenario against live HeiGIT (at most 5 requests,
2 s apart), saves each successful response body under `tests/fixtures/` and lists the
request in `tests/fixtures/heigit_recordings.json`. Failure bodies are not saved.

```bash
HEIGIT_API_KEY=... uv run python scripts/record_heigit.py NAME LON LAT DISTANCE_JSON
```

## Handoff to the next slices

- Cycling (#4): add the `cycling-road` profile in `heigit.py` and its own limits in
  `route_selection.py`; runs, candidates, selection, the GPX export and the page's run
  panel are activity-neutral apart from the `activity_not_supported` check in `main.py`
  and the walking-time wording.

- Route generation reads `route_requests`: `activity`, and the start as `start_lon`,
  `start_lat` (always on Singapore land) with its source.
- The browser types come from this API's OpenAPI document: change `contracts.py`, then
  regenerate `web/openapi.json` and `web/src/api-types.ts` (see the root `AGENTS.md`).
- `singapore_land.geojson` is data.gov.sg's planning areas (Master Plan 2019, no sea)
  merged and widened by about 50 m; rebuild it with `scripts/build_singapore_land.py`.
