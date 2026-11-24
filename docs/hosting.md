# Hosting (issue #5)

The route creator is hosted privately on free tiers only. Nothing here may be upgraded or
given payment details. Limits below were read from the official pages on 2026-11-23.

| Part | Provider (free tier) | What it runs |
| --- | --- | --- |
| Page | Vercel Hobby | `web/` (Next.js). `/api/*` is rewritten to the API, so the browser only sees one origin. |
| API | Render free web service (Docker) | `api/Dockerfile`: migrations, retention purge, then uvicorn. |
| Database | Neon free Postgres | Direct (non-pooled) connection string. |
| Sign-in | GitHub OAuth app | Only allowlisted numeric GitHub user ids get a session. |
| Telemetry | Grafana Cloud free (OTLP) | Traces and logs over OTLP/HTTP, alert rules in `ops/grafana/`. |

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

- Generation stops starting new HeiGIT requests once 90 s have passed (see
  `api/src/route_api/generation.py`), so a run returns inside the 120 s rewrite limit.
- The page checks `/api/health` on load, so the API is awake before the owner reaches
  Generate (search and confirm already need it).

If either limit changes so a bounded run cannot fit, generation must move to a background
job with polling; that is a design change to raise, not a reason to pay for hosting.
