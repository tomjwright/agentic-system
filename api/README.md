# route-api

Backend for the Singapore route creator. Issue #10 resolves and confirms a route's
starting place; issue #3 generates, inspects and exports a running loop from it and
issue #4 a road-cycling loop. There are no model calls.

1. `POST /api/places/search` sends the query to OneMap and lists every match on Singapore
   land (`no_match`, `single_match` or `multiple_matches`). It never chooses one: the
   plural "Avenue South Residences" matches Grandeur Park Residences in Bedok, while the
   singular finds the Silat Avenue blocks.
2. `POST /api/route-requests` stores the activity and the confirmed start: a OneMap
   match (searched again on the server so the stored place is OneMap's, with its query,
   `source_id` and retrieval time) or a map point. Points off Singapore land are refused.
3. `GET /api/route-requests/{id}` returns a request only to its owner.
4. `POST /api/route-requests/{id}/runs` with `operation_id` (a UUID the client makes)
   and a distance generates a loop for the request's activity and returns the finished
   run (HTTP 201). The distance is `{"kind": "target", "target_km": 5}` (any loop within
   10% either side) or `{"kind": "range", "min_km": 5, "max_km": 6}` (exact, no
   tolerance added): 1 to 50 km running, 5 to 100 km road cycling (else HTTP 422
   `invalid_request`). Each run adds a new immutable revision of the request. Sending
   the same `operation_id` again returns the run already recorded (HTTP 200); with a
   different distance it is HTTP 409 `operation_conflict`.
5. `GET /api/runs/{id}` is the run: `status` (`generating`, `succeeded`, `no_route`,
   `failed`), the distance bounds, and every candidate with its seed or via points,
   requested length, measured distance and rejection reasons.
6. `GET /api/runs/{id}/route` is the selected loop: its GeoJSON `LineString`, measured
   distance and deviation from the target, the HeiGIT profile and its time (foot-walking
   time is not a running time), surfaces with the unknown share, the restricted-road
   check (`access`), limitations and attribution.
7. `GET /api/runs/{id}/route.gpx` is the same stored geometry as GPX 1.1, point for point.

## How a loop is generated

`generation.py` asks HeiGIT (`foot-walking` for running, `cycling-road` for road
cycling, both avoiding ferries, cycling also steps) for at most 5 candidates, one at a
time, 2 s apart: round trips with seeds 1, 2, 3, ... and the requested length corrected
by the last measured length (never over HeiGIT's 100 km round-trip limit); after 2
failed round trips it switches to a loop through two via points placed inland of the
start (round trips from the coast can cross the sea); a via loop that returns keeps its
bearing for the corrected length, one that fails turns. Cycling via points may snap up
to 1 km to a road. `route_selection.py` rejects any candidate that is not closed (30 m),
starts more than 200 m from the confirmed start, leaves Singapore (50 m), disagrees with
HeiGIT's own distance by over 10%, or whose measured length is outside the bounds. A
cycling candidate is also rejected if it rides along an expressway, expressway slip
road, road tunnel or `bicycle=no` way (see below). The accepted one closest to the
target wins; if none, the run is `no_route` with every reason. Nothing is ever moved,
trimmed or rerouted to pass.

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

The route agent (`POST /api/route-requests/{id}/agent-runs`, `route_api/agent.py`) also needs
`ANTHROPIC_API_KEY` (its model, `anthropic:claude-haiku-4-5`) and `GOOGLE_API_KEY` (its judge,
`google_genai:gemini-3.5-flash`). Without both it answers 503 `agent_not_configured`; the rest
of the API is unaffected. It stores how each answer was made and judged, never the brief or
the answer, and a route it makes is an ordinary stored run.
Its answer lists the `steps` the run took (read the request, asked a clarification, generated a
route with its tries, drafted, judged, repaired, fell back), rebuilt from what code recorded,
never model text. The page shows them and draws the route from `generation_run_id`.

Owners: there is no sign-in yet. The owner is the `X-Owner-Id` header, or
`LOCAL_OWNER_ID` (default `local-owner`). Anyone who can reach the API can claim any
owner, so keep it on localhost until managed sign-in (issue #5) lands.

Logs are one JSON object per line with the `X-Request-ID` (sent back on every response).
They never contain search text, coordinates, the token or the key. Set
`OTEL_EXPORTER_OTLP_ENDPOINT` to export spans for each HeiGIT call, generation and
database write (no coordinates in their attributes).

## Evals

`uv run python -m route_api.evals` runs the labelled cases in `evals/` with the real models,
one at a time, on recorded OneMap and HeiGIT responses only. It needs both models' keys and
fails (exit 2) without them. `--agent-model` and `--judge-model` take any `provider:model`
spec (`anthropic` or `google_genai`) to compare candidates on the same cases.

- Judge cases (`judge_cases.yaml`): fixed `RouteFacts`, a draft and the right verdict. It
  reports false approvals (a bad draft approved) and false rejections (an honest one rejected).
- Agent cases (`agent_cases.yaml`): a brief and form values through the whole graph, scored
  on the result's kind, clarification reason and message source.
- Every published message is checked by code against its facts (`contradictions` in
  `eval_scoring.py`: measurements not in the facts, the other activity, unsupported safety, shade,
  surface or greenery claims, a left-out trunk-road, tunnel or unknown-surface disclosure,
  words aimed at the checker), so the judge is never its own only evaluator.

The run fails on any published contradiction, on any approved draft that invents a
measurement, makes an unsupported claim, ignores a constraint or tries a bypass, and when a
rate is worse than `evals/baseline.json`. A missed disclosure only counts towards the
false-approval rate.

Candidates on 2026-11-25 (same 23 judge and 13 agent cases):

| Agent / judge | False approvals | False rejections | Agent cases |
| --- | --- | --- | --- |
| `gemini-3.5-flash-lite` / `gemini-3.5-flash-lite` | 3/17: wrong tries, trunk roads, tunnel | 0/6 | 7/13, then 10/13 |
| `gemini-3.1-flash-lite` judge only | 2/17: trunk roads, tunnel | 4/6 | not run |

The flash-lite agent cases fail on published replies that leave out the unknown surface (the
judge approved them) and on honest drafts the judge rejected twice (fallback). The baseline is
the better candidate's measured rates; it is provisional until the default pair has run. The
default judge `gemini-3.5-flash` allows 20 free requests a day and one run needs about 40, so it
cannot finish a run on the free tier.

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

## Restricted roads (cycling)

HeiGIT has no usable Singapore road access data, so cycling loops are checked against
`src/route_api/restricted_ways.geojson.gz`: the OpenStreetMap expressways, slip roads,
road tunnels, `bicycle=no` ways and trunk roads, with the extract name, OSM timestamp
and licence (© OpenStreetMap contributors, ODbL 1.0) in its `source`. `restrictions.py`
reuses the #2 feasibility check (`route_feasibility.restrictions`, a path dependency):
a stretch counts as riding on a road only when both ends and the midpoint of a route
edge are within 1.5 m of it; anything else within 8 m is a crossing or passing beside,
which is allowed. Trunk roads and tunnels on minor roads (tertiary, residential,
unclassified and slip roads) are legal and are disclosed in the limitations, never
rejected; car park and other service tunnels are ignored. Access and surface everywhere
else stay unknown, never "verified".

Refresh it from a newer Geofabrik/BBBike Singapore `.osm.pbf` (from `feasibility/`):

```bash
uv run --with osmium python scripts/extract_restricted_ways.py Singapore.osm.pbf data/
gzip -9n -c data/restricted_ways.geojson > ../api/src/route_api/restricted_ways.geojson.gz
```

then rerun the API tests; route fixtures near changed roads may need re-recording.

## Recording HeiGIT responses

`scripts/record_heigit.py` runs one scenario against live HeiGIT (at most 5 requests,
2 s apart), saves each successful response body under `tests/fixtures/` and lists the
request and profile in `tests/fixtures/heigit_recordings.json`. Failure bodies are not
saved. Requests already listed, failures included, are replayed instead of sent.

```bash
HEIGIT_API_KEY=... uv run python scripts/record_heigit.py NAME ACTIVITY LON LAT DISTANCE_JSON
```

## Handoff to the next slices

- Both activities share runs, candidates, selection, the GPX export and the page's run
  panel; per-activity values are `PROFILES` and `AVOID_FEATURES` in `heigit.py` and
  `DISTANCE_LIMITS_KM` in `route_selection.py` (mirrored in the page's `LIMITS_KM`).
- Live cycling demos from Avenue South Residence (OSM snapshot 2026-11-21): 20 km,
  50 km and 60-70 km are recorded as the `avenue_south_ride_*` fixtures.

- Route generation reads `route_requests`: `activity`, and the start as `start_lon`,
  `start_lat` (always on Singapore land) with its source.
- The browser types come from this API's OpenAPI document: change `contracts.py`, then
  regenerate `web/openapi.json` and `web/src/api-types.ts` (see the root `AGENTS.md`).
- `singapore_land.geojson` is data.gov.sg's planning areas (Master Plan 2019, no sea)
  merged and widened by about 50 m; rebuild it with `scripts/build_singapore_land.py`.
