# route-api

Backend for the Singapore route creator. This slice (issue #10) resolves and confirms a
route's starting place; there are no routes or model calls yet.

1. `POST /api/places/search` sends the query to OneMap and lists every match on Singapore
   land (`no_match`, `single_match` or `multiple_matches`). It never chooses one: the
   plural "Avenue South Residences" matches Grandeur Park Residences in Bedok, while the
   singular finds the Silat Avenue blocks.
2. `POST /api/route-requests` stores the activity and the confirmed start: a OneMap
   match (searched again on the server so the stored place is OneMap's, with its query,
   `source_id` and retrieval time) or a map point. Points off Singapore land are refused.
3. `GET /api/route-requests/{id}` returns a request only to its owner.

Points are GeoJSON, `coordinates` = `[longitude, latitude]`. Errors are
`{"error": {"code", "message"}}`; the codes are listed in `contracts.py`.

## Run

```bash
docker run -d --name routes-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=routes postgres:17
export DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes
uv sync
uv run alembic upgrade head
ONEMAP_API_TOKEN=... uv run uvicorn route_api.main:app_from_env --factory --port 8000 --no-access-log
cd ../web && npm ci && npm run dev    # http://localhost:3000, forwards /api to port 8000
```

Owners: there is no sign-in yet. The owner is the `X-Owner-Id` header, or
`LOCAL_OWNER_ID` (default `local-owner`). Anyone who can reach the API can claim any
owner, so keep it on localhost until managed sign-in (issue #5) lands.

Logs are one JSON object per line with the `X-Request-ID` (sent back on every response).
They never contain search text, coordinates or the token.

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

## Handoff to the next slices

- Route generation reads `route_requests`: `activity`, and the start as `start_lon`,
  `start_lat` (always on Singapore land) with its source.
- The browser types come from this API's OpenAPI document: change `contracts.py`, then
  regenerate `web/openapi.json` and `web/src/api-types.ts` (see the root `AGENTS.md`).
- `singapore_land.geojson` is data.gov.sg's planning areas (Master Plan 2019, no sea)
  merged and widened by about 50 m; rebuild it with `scripts/build_singapore_land.py`.
