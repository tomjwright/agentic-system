# Hosting (issue #5)

The route creator is hosted privately on free tiers only. Nothing here may be upgraded or
given payment details. Limits below were read from the official pages on 2026-11-23.

| Part | Provider (free tier) | What it runs |
| --- | --- | --- |
| Page | Vercel Hobby | `web/` (Next.js). `/api/*` is rewritten to the API, so the browser only sees one origin. |
| API | Render free web service (native Python) | `render.yaml`: migrations, then uvicorn; the app purges expired records on start. |
| Database | Neon free Postgres | Direct (non-pooled) connection string. |
| Sign-in | GitHub OAuth app | Only allowlisted numeric GitHub user ids get a session. |
| Telemetry | Grafana Cloud free (OTLP) | Traces over OTLP/HTTP; alert rules in `ops/grafana/alerts.yaml`. |

## Free-tier limits that shape the design

### Vercel Hobby

- Personal or non-commercial use only ([terms, section 4](https://vercel.com/legal/terms)).
  This app is Tom's personal tool. The same terms let Vercel use Hobby "Your Content" to
  train AI models; the page holds no secrets or personal data, and route data stays in Neon.
- Proxied request timeout (rewrites to an external origin) is **120 s** on every plan; after
  that Vercel answers `ROUTER_EXTERNAL_TARGET_ERROR`
  ([limits](https://vercel.com/docs/limits#proxied-request-timeout)). Every API call,
  including loop generation, goes through this rewrite, so generation must finish well
  inside 120 s (see "Bounded generation" below).
- Function maximum duration 300 s, 100 deployments a day, 1,000,000 function invocations
  and 100 GB fast data transfer a month; over a limit, the feature pauses for 30 days
  ([Hobby plan](https://vercel.com/docs/plans/hobby)). The page uses no API routes.
- Instant Rollback on Hobby goes back to the **immediately previous** production deployment
  only ([instant rollback](https://vercel.com/docs/instant-rollback)). The promotion script
  rolls back only one step, so this is enough.
- Deployment Protection "Standard Protection" (all deployments except the production
  domain) is available on all plans; Password Protection is not on Hobby
  ([deployment protection](https://vercel.com/docs/deployment-protection)). Protection
  Bypass for Automation is on all plans
  ([bypass](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation)).
- REST endpoints used: `POST /v10/projects/{projectId}/promote/{deploymentId}`,
  `POST /v1/projects/{projectId}/rollback/{deploymentId}`, `GET /v13/deployments/{idOrUrl}`
  ([OpenAPI](https://openapi.vercel.sh/)).

### Render free web service

- Spins down after **15 minutes** without inbound traffic; the next request waits **about
  one minute** while it spins up ([free instances](https://render.com/docs/free)). Render
  may restart a free service at any time; 750 free instance hours a month per workspace;
  ephemeral filesystem; single instance; no one-off jobs or shell.
- Rollbacks on free: only to the **two most recent previous deploys**.
- **No pre-deploy command on free** ([deploy steps](https://render.com/docs/deploys)), so
  migrations run in the start command before uvicorn. Start command timeout is 15 minutes.
- Zero-downtime deploys: the old instance keeps all traffic until the new one passes its
  health check; if the new one never becomes healthy within 15 minutes Render cancels the
  deploy and keeps the old one ([deploys](https://render.com/docs/deploys),
  [health checks](https://render.com/docs/health-checks)). A failed start command (for
  example a failed migration) therefore leaves the previous release serving.
- Render's own free Postgres expires after 30 days, which is why the database is on Neon.
- API used: `POST /v1/services/{id}/deploys` (`commitId`), `GET /v1/services/{id}/deploys`,
  `GET /v1/services/{id}/deploys/{deployId}`, `POST /v1/services/{id}/rollback`
  (`deployId`); deploy statuses `created`, `queued`, `build_in_progress`,
  `update_in_progress`, `live`, `deactivated`, `build_failed`, `update_failed`,
  `canceled`, `pre_deploy_in_progress`, `pre_deploy_failed`
  ([API reference](https://api-docs.render.com/reference/create-deploy)).

### Neon free Postgres

- 100 CU-hours per project a month, autoscaling up to 2 CU, **scale to zero after 5
  minutes, which cannot be disabled** on free; 1 GB storage per project; 6 h restore
  history; 1 day of monitoring metrics ([plans](https://neon.com/docs/introduction/plans)).
- A suspended compute reactivates "within a few hundred milliseconds"
  ([scale to zero](https://neon.com/docs/introduction/scale-to-zero)). The API uses
  `pool_pre_ping` so a connection dropped during suspension is replaced, not reported.
- Pooled connections (PgBouncer, `-pooler` host) allow 10,000 clients; a direct connection
  on 0.25 CU allows about 112 ([pooling](https://neon.com/docs/connect/connection-pooling)).
  One Render instance with SQLAlchemy's default pool (5 + 10 overflow) needs far fewer, so
  the API and migrations both use the **direct** string (no PgBouncer transaction-mode
  caveats for Alembic).

### Grafana Cloud free

- Always free, no card: **14 days retention** for metrics, logs, traces and profiles; 10k
  active metric series, 50 GB logs and 50 GB traces ingested a month
  ([pricing](https://grafana.com/pricing/)).
- OTLP: the stack's OpenTelemetry tile gives `OTEL_EXPORTER_OTLP_ENDPOINT` and
  `OTEL_EXPORTER_OTLP_HEADERS`; for Python write `Basic%20` instead of `Basic `
  ([send OTLP](https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/)).

### GitHub OAuth

- Authorize with `state` (unguessable, checked on return) and PKCE (`code_challenge`,
  `code_verifier`); the code expires after 10 minutes
  ([authorizing OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)).
- The allowlist holds numeric user ids (Tom is `119127762`), never logins, because a login
  can be renamed and re-registered.

## Bounded generation

Vercel cuts any proxied request at 120 s and a cold Render instance takes about 60 s to
wake. So:

- Generation starts no new HeiGIT request once 45 s have passed (`TIME_BUDGET_S` in
  `api/src/route_api/generation.py`). One request can take at most 30 s, plus one retry
  of 30 s, a 1 s retry wait and the 2 s gap, so a run answers in about 108 s at worst.
- The page calls `/api/auth/me` on load and search and confirm come first, so the API is
  awake before Generate is pressed.

If either limit changes so a bounded run cannot fit, generation must move to a background
job with polling; that is a design change to raise, not a reason to pay for hosting.

## Sign-in and request limits

- `/api/auth/login` sends the browser to GitHub with `state` and a PKCE challenge, both kept
  in a 10-minute `__Host-route-login` cookie. `/api/auth/callback` exchanges the code, reads
  `/user` and gives a session only to an id in `OWNER_GITHUB_IDS`. The allowlist is checked
  again on every request, so removing an id signs that owner out everywhere.
- The session is a random token in `__Host-route-session` (HttpOnly, Secure, SameSite=Lax,
  7 days). Only its SHA-256 is stored. POSTs must send `X-CSRF-Token`, and a cookie request
  whose `Origin` is not `APP_ORIGIN` is refused. No CORS headers are sent.
- Every route, run and export query filters by the signed-in owner; another owner's id
  answers 404.
- Limits per owner: request bodies of at most 8 KiB, `REQUESTS_PER_MINUTE` (60),
  `RUNS_PER_DAY` (30, at most 150 HeiGIT requests a day, inside HeiGIT's free 2,000 a day).
- Two bearer tokens belong to the deploy workflow, not to people. A browser never attaches
  a bearer token by itself, so these requests skip the Origin and CSRF checks:
  - `SMOKE_TOKEN` (SHA-256 in `SMOKE_TOKEN_SHA256`) is owner `smoke` and may only read.
  - `E2E_TOKEN` (SHA-256 in `E2E_TOKEN_SHA256`) is owner `e2e` and may write, so the staged
    browser test can run the whole flow from the staged page's one-off origin. It may start
    one run every 10 minutes and 3 a day (at most 15 HeiGIT requests and a few OneMap
    searches a day), and its route requests are deleted after a day.

## Deploy and recovery

`.github/workflows/deploy.yml` runs `route_api.promote` (tested in `api/tests/test_promote.py`)
when the `ci` workflow finishes on `main`. The repository is public and a fork's pull request
also runs `ci` (its branch may even be called `main`), so the job runs only for a passing
`push` to this repository's `main`, or a manual run on `main`, in the `production`
environment, and checks out that commit without keeping the token. Each of these conditions
has a test in `api/tests/test_deploy_workflow.py`.

1. Build the page with `vercel build --prod` (no token in the build's environment) and
   refuse if a provider key or URL is in `.vercel/output` (`scripts/no_provider_secrets.sh`,
   the same scan the `vercel-build` CI job runs on every PR).
2. Stage it with `vercel deploy --prebuilt --prod --skip-domain` (not yet live).
3. Wait up to 60 minutes for every required check run from GitHub Actions on the commit:
   `secrets-scan`, `feasibility`, `actionlint`, `zizmor`, `codeql (python)`,
   `codeql (actions)`, `api`, `web`, `codeql (javascript-typescript)`, `migration-compat`,
   `mutation-api`, `mutation-feasibility`, `render-smoke`, `vercel-build`. Refuse if any is
   missing, unfinished or not `success`. Nothing is deployed.
4. Deploy the API on Render. Its start command runs `python -m route_api.migrate` before
   uvicorn: `alembic upgrade head`, unless a newer release has already migrated further (a
   rollback), when it leaves the schema as it is.
   If migration fails the process exits, Render never routes to it and the old API keeps
   serving; promotion stops.
5. Smoke-test the staged page: `/api/ready` is 200, an anonymous `/api/auth/me` is 401, the
   smoke token signs in, `/` is 200. Then run the staged browser test
   (`web/playwright.staged.config.ts`) against it as owner `e2e`: search "avenue south
   residence", confirm it, generate a 5 km loop and check the GPX holds the stored path.
   This is one OneMap search and at most 5 HeiGIT requests. On failure the API is rolled
   back to its previous live deploy and the page is never promoted.
6. Promote the staged page and smoke-test production. On failure both the page (Vercel
   rollback to the previous production deployment) and the API are rolled back.

Migrations must only add (expand): the old API has to keep working on the new schema while
it is still serving and after a rollback (`migration-compat` checks this). Removing a column
takes two releases.

## Checks before anything deploys

Besides the existing jobs, `ci.yml` runs on every PR:

- `render-smoke`: `render.yaml`'s build and start commands, exactly as written
  (`scripts/render_smoke.sh`), against PostgreSQL 17, failing unless `/api/ready` answers.
- `vercel-build`: `vercel build` with `web/vercel.json`, then the deploy's provider scan.
- `mutation-api` also mutates `promote.py` and `retention.py`, at the 94% floor.
- `web` also runs the staged browser test against the recorded API from an origin the API
  does not trust, as the staged page is.

## Retention

- A route request holds the confirmed start location. It and everything under it
  (revisions, runs, candidate geometry, the selection) are deleted 90 days after it was
  created, and the `e2e` owner's after a day (`api/src/route_api/retention.py`, run on
  every API start; Render Free restarts after each idle spell).
- Expired sessions are deleted the same way. Searches are never stored.
- Logs and spans hold no queries, coordinates or credentials; Grafana keeps them 14 days.

## Telemetry and alerts

With `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` set the API exports
spans (`generate_route` with `route.error_code`, `heigit.directions` with the HTTP status).
`ops/grafana/alerts.yaml` holds three rules: outage (a Grafana Synthetic Monitoring HTTP
check named `route-api-health` on `/api/health` from Singapore every 5 minutes, failing for
10 minutes), generation errors and HeiGIT quota. Give the check a 10 s timeout: at the
default 3 s every probe timed out on the free instance while it answered other clients in
under a second. Each rule's queries evaluate on the real stack (`POST /api/v1/eval`), and
the imported rules report healthy in Grafana; `ops/grafana/import_alerts.py` imports them.
The outage rule alerts on no data too, so it fires if the Synthetic Monitoring check is gone.
Alerts reach someone only once the stack has a contact point and the notification policy
sends to it.

## GitHub settings (Tom, as repository admin)

The agent token has no admin rights, so nothing here is applied by an agent. The
`production` environment with its main-only branch policy already exists. Before
`deploy.yml` reaches `main`:

- Environment `production` secrets: `VERCEL_TOKEN`, `RENDER_API_KEY`,
  `VERCEL_AUTOMATION_BYPASS_SECRET`, `SMOKE_TOKEN`, `E2E_TOKEN`. Variables:
  `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `RENDER_SERVICE_ID`, `PRODUCTION_URL`.
- On Render, set `SMOKE_TOKEN_SHA256` and `E2E_TOKEN_SHA256` to the SHA-256 (hex) of the
  two tokens.
