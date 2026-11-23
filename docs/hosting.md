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

- Generation starts no new HeiGIT request once 30 s have passed (`TIME_BUDGET_S` in
  `api/src/route_api/generation.py`). One request can take at most 30 s, plus one retry
  of 30 s, a 1 s retry wait and the 2 s gap, so a run answers in about 95 s at worst.
- The page calls `/api/auth/me` on load and search and confirm come first, so the API is
  awake before Generate is pressed.

If either limit changes so a bounded run cannot fit, generation must move to a background
job with polling; that is a design change to raise, not a reason to pay for hosting.

## Sign-in and request limits

- `/api/auth/login` sends the browser to GitHub with `state` and a PKCE challenge, both kept
  in a 10-minute `__Host-route-login` cookie. `/api/auth/callback` exchanges the code, reads
  `/user` and gives a session only to an id in `OWNER_GITHUB_IDS`.
- The session is a random token in `__Host-route-session` (HttpOnly, Secure, SameSite=Lax,
  7 days). Only its SHA-256 is stored. POSTs must send `X-CSRF-Token`, and a request whose
  `Origin` is not `APP_ORIGIN` is refused. No CORS headers are sent: the page reaches the
  API through the Vercel rewrite, so it is same-origin and any other origin is blocked by
  the browser.
- Every route, run and export query filters by the signed-in owner; another owner's id
  answers 404.
- Limits per owner: request bodies of at most 8 KiB (and a Content-Length is required),
  `REQUESTS_PER_MINUTE` (60), `RUNS_PER_DAY` (30, at most 150 HeiGIT requests a day, inside
  HeiGIT's free 2,000 a day). Answers to refused requests carry no route data.
- The smoke test signs in with a bearer token whose SHA-256 is `SMOKE_TOKEN_SHA256`. It
  owns only the `smoke` owner and may only read.

## Deploy and recovery

`.github/workflows/deploy.yml` runs `route_api.promote` after the `app` workflow passes on
`main` (tested in `api/tests/test_promote.py`). The repository is public and a fork's pull
request also runs `app` (its branch may even be called `main`), so the job runs only for a
`push` to this repository's `main`, or a manual run on `main`, and checks out that commit
without keeping the token (`api/tests/test_deploy_workflow.py`):

1. Refuse if any of `api`, `web`, `test`, `secrets-scan` is missing or not `success` on the
   commit. Nothing is deployed.
2. Stage the page with `vercel deploy --prebuilt --prod --skip-domain` (not yet live).
3. Deploy the API on Render. Its start command runs `alembic upgrade head` before uvicorn.
   If migration fails the process exits, Render never routes to it and the old API keeps
   serving; promotion stops.
4. Smoke-test the staged page: `/api/ready` is 200, an anonymous `/api/auth/me` is 401, the
   smoke token signs in, `/` is 200. On failure the API is rolled back to its previous live
   deploy.
5. Promote the staged page and smoke-test production. On failure both the page (Vercel
   rollback to the previous production deployment) and the API are rolled back.

Migrations must only add (expand): the old API has to keep working on the new schema while
it is still serving and after a rollback. Removing a column takes two releases.

## Retention

- A route request holds the confirmed start location. It and everything under it
  (revisions, runs, candidate geometry, the selection) are deleted 90 days after it was
  created (`api/src/route_api/retention.py`, run on every API start; Render Free restarts
  after each idle spell).
- Expired sessions are deleted the same way. Searches are never stored.
- Logs and spans hold no queries, coordinates or credentials; Grafana keeps them 14 days.

## Telemetry and alerts

With `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` set the API exports
spans (`generate_route` with `route.error_code`, `heigit.directions` with the HTTP status).
`ops/grafana/alerts.yaml` holds three rules: outage (a Grafana Synthetic Monitoring HTTP
check named `route-api-health` on `/api/health` failing for 10 minutes), generation errors
and HeiGIT quota. They are not yet imported or tried against a real stack.

## GitHub settings (Tom, as repository admin)

The agent token has no admin rights, so these are not applied. Run as Tom, **in this
order, before `deploy.yml` reaches `main` and before any secret is added**. A job that names
an environment which does not exist creates it with no protection, so the `production`
environment and its main-only branch policy must exist first; then add its secrets.

```bash
# A "production" environment only main may deploy to.
gh api -X PUT repos/tomjwright/agentic-system/environments/production \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/tomjwright/agentic-system/environments/production/deployment-branch-policies \
  -f name=main -f type=branch
# Required checks on main.
gh api -X PUT repos/tomjwright/agentic-system/branches/main/protection --input - <<'JSON'
{"required_status_checks": {"strict": true, "contexts": ["api", "web", "test", "secrets-scan"]},
 "enforce_admins": false, "required_pull_request_reviews": null, "restrictions": null}
JSON
```

Environment `production` secrets: `VERCEL_TOKEN`, `RENDER_API_KEY`,
`VERCEL_AUTOMATION_BYPASS_SECRET`, `SMOKE_TOKEN`. Variables: `VERCEL_ORG_ID`,
`VERCEL_PROJECT_ID`, `RENDER_SERVICE_ID`, `PRODUCTION_URL`.
