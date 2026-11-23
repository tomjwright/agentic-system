# AGENTS.md

Singapore running and road-cycling route creator (spec: issue #1). Shared standards
live in `tomjwright/home` `AGENTS.md`; this file adds the rules for this repo.

## Layout

- `feasibility/`: the issue #2 feasibility experiment (uv project). Real HeiGIT,
  OneMap and NParks data, no agent or framework. Results in `feasibility/EVIDENCE.md`.
- `api/`: FastAPI backend (uv project): OneMap place search, start confirmation and
  owner-scoped route requests in PostgreSQL (SQLAlchemy, Alembic). See `api/README.md`.
- `web/`: Next.js page with a Leaflet map on the OneMap basemap. Talks only to `api/`.

## Rules

- `HEIGIT_API_KEY` stays server side: only `route_feasibility/heigit.py` reads it, only
  as the `Authorization` header to `api.heigit.org`. Never print, log, commit or record
  it; recorded fixtures are response bodies only.
- `ONEMAP_API_TOKEN` stays server side the same way: only `api/src/route_api/onemap.py`
  reads it, only as the `Authorization` header to OneMap's search endpoint. The browser
  never calls a OneMap API; it only loads OneMap basemap tiles, which need no token.
- Never pick a place for the user: every OneMap match is listed and the user confirms one.
- Tests never call a live provider. They replay recorded real responses through
  `httpx.MockTransport` (`feasibility/tests/test_cli.py`, `api/tests/recorded_onemap.py`).
- `web/openapi.json` and `web/src/api-types.ts` are generated: after changing
  `api/src/route_api/contracts.py` or a route, regenerate both (commands in Checks).
- `api/` and `feasibility/` pin Python 3.12 (`.python-version`; CI sets the same in
  setup-uv). Other versions word some HTTP statuses differently, so the generated
  `web/openapi.json` would drift.
- Live runs are manual and bounded: `feasibility/scripts/run_live_cases.sh` makes at
  most 32 HeiGIT requests (free plan: 2000 directions a day, 40 a minute).
- Downloaded datasets go in `feasibility/data/` (git-ignored).

## Checks

PostgreSQL must be running for the api and browser tests (`docker run -d -p 5432:5432
-e POSTGRES_PASSWORD=postgres postgres:17`, then create databases `routes_test` and
`routes_e2e`).

```bash
cd feasibility
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files

cd ../api
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv export --frozen --no-hashes --no-emit-project | uv run pip-audit --strict -r /dev/stdin

cd ../web
npm ci
(cd ../api && uv run python -m route_api.openapi) > openapi.json && npm run types
git diff --exit-code -- openapi.json src/api-types.ts
npm run lint
npm audit --audit-level=moderate
npm run e2e        # builds the page, starts the api with recorded OneMap, desktop + mobile
```
