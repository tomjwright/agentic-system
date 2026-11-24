import { createHash } from "node:crypto";

import { defineConfig, devices, type PlaywrightTestConfig } from "@playwright/test";

// The staged browser test (e2e-staged). The deploy workflow runs it against STAGED_URL, the
// staged page in front of the newly deployed API, before promoting (api/src/route_api/promote.py).
// Without STAGED_URL, CI runs it against the recorded API (api/tests/serve_recorded.py) with a
// page origin the API does not trust, as the staged page's one-off origin is not.
const stagedUrl = process.env.STAGED_URL;
const recordedToken = "synthetic-e2e-token";
const databaseUrl =
  process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes_e2e";

const recordedServers: PlaywrightTestConfig["webServer"] = [
  {
    command: "uv run alembic upgrade head && uv run python -m tests.serve_recorded",
    cwd: "../api",
    env: {
      DATABASE_URL: databaseUrl,
      PORT: "8002",
      APP_ORIGIN: "https://app.example.invalid",
      E2E_TOKEN_SHA256: createHash("sha256").update(recordedToken).digest("hex"),
    },
    url: "http://127.0.0.1:8002/api/health",
    reuseExistingServer: false,
  },
  {
    command: "npm run build && npm run start -- --port 3002",
    env: { API_URL: "http://127.0.0.1:8002" },
    url: "http://127.0.0.1:3002",
    timeout: 180_000,
    reuseExistingServer: false,
  },
];

if (!stagedUrl) {
  process.env.E2E_TOKEN = recordedToken;
}

export default defineConfig({
  testDir: "e2e-staged",
  forbidOnly: !!process.env.CI,
  // A retry would start a second live run, which the API refuses within 10 minutes anyway.
  retries: 0,
  workers: 1,
  timeout: 120_000,
  reporter: "list",
  // No trace against the staged page: it would hold the e2e token and the bypass secret.
  use: { baseURL: stagedUrl ?? "http://127.0.0.1:3002", trace: stagedUrl ? "off" : "retain-on-failure" },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"] } }],
  webServer: stagedUrl ? undefined : recordedServers,
});
