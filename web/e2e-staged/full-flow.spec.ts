import { expect, type Page, test } from "@playwright/test";

// One full run as the deploy workflow's e2e owner (api/src/route_api/auth.py): search,
// confirm, generate 5 km and download the same path as GPX. Against the staged page this is
// one OneMap search and at most 5 HeiGIT requests, and the API lets the e2e owner start only
// one run every 10 minutes and 3 a day.
const e2eToken = process.env.E2E_TOKEN ?? "";
const bypassSecret = process.env.VERCEL_AUTOMATION_BYPASS_SECRET;

function ownOriginHeaders(): Record<string, string> {
  const headers: Record<string, string> = { Authorization: `Bearer ${e2eToken}` };
  if (bypassSecret) {
    headers["x-vercel-protection-bypass"] = bypassSecret;
  }
  return headers;
}

// The token and the bypass secret go only to the page's own origin, never to map tiles.
async function signInAsE2eOwner(page: Page, baseURL: string) {
  await page.route(`${new URL(baseURL).origin}/**`, async (route) => {
    await route.continue({ headers: { ...route.request().headers(), ...ownOriginHeaders() } });
  });
  await page.route("https://api.heigit.org/**", async () => {
    throw new Error("the browser called HeiGIT");
  });
  await page.route("https://www.onemap.gov.sg/api/**", async () => {
    throw new Error("the browser called a OneMap API");
  });
  await page.goto("/");
  await expect(page.getByLabel("Search for a place, or tap the map")).toBeVisible();
}

test("generate a 5 km loop and download the same path as GPX", async ({ page, baseURL }) => {
  expect(e2eToken, "E2E_TOKEN must be set").not.toBe("");
  await signInAsE2eOwner(page, baseURL ?? "");

  await page.getByLabel("Search for a place, or tap the map").fill("avenue south residence");
  const matches = page.getByRole("list", { name: "Matching places" }).getByRole("button");
  await matches.filter({ hasText: "11 SILAT AVENUE" }).first().click();
  await page.getByRole("button", { name: "Confirm start" }).click();
  await expect(page.getByText("Start confirmed")).toBeVisible();

  await page.getByLabel("Target km").fill("5");
  await page.getByRole("button", { name: "Generate loop" }).click();
  const result = page.locator(".result");
  await expect(result).toContainText(" km loop (", { timeout: 90_000 });
  await expect(page.locator("path.leaflet-interactive").first()).toBeVisible();

  // A routed download is cancelled by the browser, so the link's file is fetched directly,
  // with the same headers the page sends.
  const gpxPath = await result.getByRole("link", { name: "Download GPX" }).getAttribute("href");
  expect(gpxPath).toMatch(/^\/api\/runs\/[0-9a-f-]+\/route\.gpx$/);
  const gpxAnswer = await page.request.get(gpxPath ?? "", { headers: ownOriginHeaders() });
  expect(gpxAnswer.status()).toBe(200);
  const gpx = await gpxAnswer.text();
  const routePath = (gpxPath ?? "").replace(/\.gpx$/, "");
  const answer = await page.request.get(routePath, { headers: ownOriginHeaders() });
  expect(answer.status()).toBe(200);
  const route = await answer.json();
  const points = [...gpx.matchAll(/<trkpt lat="([^"]+)" lon="([^"]+)"/g)].map((match) => [
    Number(match[2]),
    Number(match[1]),
  ]);
  expect(points.length).toBeGreaterThan(1);
  expect(points).toEqual(route.geometry.coordinates);
});
