import { defineConfig, devices } from "@playwright/test";

// Browser tests run the real API and page, with OneMap search replaced by recorded
// responses (api/tests/serve_recorded.py) and map tiles stubbed in the test itself.
const databaseUrl =
  process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/routes_e2e";

export default defineConfig({
  testDir: "e2e",
  forbidOnly: !!process.env.CI,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3001", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "uv run alembic upgrade head && uv run python -m tests.serve_recorded",
      cwd: "../api",
      env: { DATABASE_URL: databaseUrl, PORT: "8001" },
      url: "http://127.0.0.1:8001/docs",
      reuseExistingServer: false,
    },
    {
      command: "npm run build && npm run start -- --port 3001",
      env: { API_URL: "http://127.0.0.1:8001" },
      url: "http://127.0.0.1:3001",
      timeout: 180_000,
      reuseExistingServer: false,
    },
  ],
});
