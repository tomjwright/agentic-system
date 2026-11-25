# AGENTS.md

Singapore running and road-cycling route creator (spec: issue #1). Shared standards
live in `tomjwright/home` `AGENTS.md`; this file adds the rules for this repo.

## Layout

- `feasibility/`: the issue #2 feasibility experiment (uv project). Real HeiGIT,
  OneMap and NParks data, no agent or framework. Results in `feasibility/EVIDENCE.md`.
- `api/`: FastAPI backend (uv project): OneMap place search, start confirmation,
  owner-scoped route requests, and running-loop generation through HeiGIT with GPX
  export, in PostgreSQL (SQLAlchemy, Alembic). See `api/README.md`.
- `web/`: Next.js page with a Leaflet map on the OneMap basemap. Talks only to `api/`.

## Rules

- `HEIGIT_API_KEY` stays server side: `route_feasibility/heigit.py`, `app_from_env` in
  `api/src/route_api/main.py`, the nightly `api/src/route_api/canary.py` and the manual
  `api/scripts/record_heigit.py` read it, and it is sent only as the `Authorization`
  header to the fixed `api.heigit.org` directions URL (`api/src/route_api/heigit.py`).
  Never print, log, commit or record it; recorded fixtures hold request and response
  bodies only, never headers.
- A generated route is never edited: the selected candidate's stored geometry is what the
  page draws and what the GPX contains. Invalid candidates are rejected, not repaired.
- `ONEMAP_API_TOKEN` stays server side the same way: `app_from_env` in
  `api/src/route_api/main.py` reads it and hands it to `onemap.py`, which sends it only as
  the `Authorization` header to OneMap's search endpoint. The browser
  never calls a OneMap API; it only loads OneMap basemap tiles, which need no token.
- `ANTHROPIC_API_KEY` (the route agent's model) and `GOOGLE_API_KEY` (its judge) stay server
  side the same way: only `models_from_env` in `api/src/route_api/llm.py` reads them, to build
  the chat models. Without both, only the agent endpoint is off (503); the rest of the app runs.
- Never pick a place for the user: every OneMap match is listed and the user confirms one.
- Tests never call a live provider. They replay recorded real responses through
  `httpx.MockTransport` (`feasibility/tests/test_cli.py`, `api/tests/recorded_onemap.py`,
  `api/tests/recorded_heigit.py`).
- `web/openapi.json` and `web/src/api-types.ts` are generated: after changing
  `api/src/route_api/contracts.py` or a route, regenerate both (commands in Checks).
- `api/` and `feasibility/` pin Python 3.12 (`.python-version`, which uv reads locally
  and in CI). Other versions word some HTTP statuses differently, so the generated
  `web/openapi.json` would drift.
- Live runs are manual and bounded: `feasibility/scripts/run_live_cases.sh` makes at
  most 38 HeiGIT requests and `api/scripts/record_heigit.py` at most 5 per scenario
  (free plan: 2000 directions a day, 40 a minute).
- Each deploy's staged browser test (`web/e2e-staged/`, run by `route_api.promote`) makes one
  OneMap search and at most 5 HeiGIT requests as owner `e2e`, which the API allows one run
  every 10 minutes and 3 a day.
- The only scheduled live call is `.github/workflows/provider-canary.yml`: one OneMap search
  (no token, so an expired token never fails it) and two HeiGIT directions a night.
- Downloaded datasets go in `feasibility/data/` (git-ignored).

## Checks

PostgreSQL must be running for the api and browser tests (`docker run -d -p 5432:5432
-e POSTGRES_PASSWORD=postgres postgres:17`, then create databases `routes_test`,
`routes_e2e` and `routes_render`). The render smoke needs `yq`.

```bash
cd feasibility
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
uv run mutmut run --max-children 4 && uv run mutmut results --all true | python3 ../scripts/mutation_floor.py 94

cd ../api
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest --cov    # fails below the branch-coverage floor in pyproject.toml
uv export --frozen --no-emit-project --no-emit-package route-feasibility | uv run pip-audit --strict --disable-pip -r /dev/stdin
(cd .. && api/scripts/previous_release_tests.sh origin/main)   # the release before this one, on this schema
uv run mutmut run --max-children 4 && uv run mutmut results --all true | python3 ../scripts/mutation_floor.py 94

cd ../web
npm ci
(cd ../api && uv run python -m route_api.openapi) > openapi.json && npm run types
git diff --exit-code -- openapi.json src/api-types.ts
npm run lint
npm audit --audit-level=moderate
npm run e2e        # builds the page, starts the api with recorded OneMap and HeiGIT and scripted fake models, desktop + mobile
! grep -rl -e "api.heigit.org" -e "HEIGIT_API_KEY" -e "ONEMAP_API_TOKEN" .next/static
! grep -rl -e "ANTHROPIC_API_KEY" -e "GOOGLE_API_KEY" -e "FakeModel" -e "scripted-agent" .next/static
npm run e2e:staged # the deploy's staged browser test, recorded API, from an origin it does not trust

cd ..
# render-smoke: render.yaml's exact build and start commands, failing unless /api/ready answers
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes_render \
  APP_ORIGIN=https://app.example.invalid GITHUB_CLIENT_ID=synthetic GITHUB_CLIENT_SECRET=synthetic \
  ONEMAP_API_TOKEN=synthetic HEIGIT_API_KEY=synthetic scripts/render_smoke.sh
# vercel-build: build as Vercel does (web/vercel.json), then the deploy's provider scan
npm ci --prefix ops/vercel-cli
mkdir -p .vercel && echo '{"projectId": "ci", "orgId": "ci", "settings": {"framework": "nextjs", "rootDirectory": "web"}}' > .vercel/project.json
ops/vercel-cli/node_modules/.bin/vercel build --prod --yes && scripts/no_provider_secrets.sh .vercel/output
actionlint && zizmor --offline .github/workflows
uvx --python 3.12 semgrep@1.187.0 scan --metrics=off --error --config p/python --config p/typescript --config p/react --config p/github-actions feasibility/src api/src web/src .github
```
