import { readFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

const BLANK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
  "base64",
);

// HeiGIT is replaced by recorded cycling-road responses inside the API (api/tests/serve_recorded.py).
async function stubUpstreams(page: Page) {
  await page.route("https://www.onemap.gov.sg/**", async (route) => {
    expect(route.request().url()).not.toContain("/api/");
    await route.fulfill({ contentType: "image/png", body: BLANK_TILE });
  });
  await page.route("https://api.heigit.org/**", async () => {
    throw new Error("the browser called HeiGIT");
  });
}

test.beforeEach(async ({ page }) => {
  await stubUpstreams(page);
  await page.goto("/");
  await page
    .getByLabel("Search for a place, or tap the map")
    .fill("avenue south residence");
  const matches = page
    .getByRole("list", { name: "Matching places" })
    .getByRole("button");
  await matches.filter({ hasText: "11 SILAT AVENUE" }).click();
  await page.getByLabel("Road cycling").check();
  await page.getByRole("button", { name: "Confirm start" }).click();
  await expect(page.getByText("Start confirmed")).toBeVisible();
});

test("switch to road cycling, generate a 20 km loop and download the same path", async ({
  page,
}) => {
  await expect(
    page.getByRole("heading", { name: "Road-cycling loop" }),
  ).toBeVisible();
  await expect(page.getByLabel("Target km")).toHaveValue("20");
  await page.getByRole("button", { name: "Generate loop" }).click();

  const result = page.locator(".result");
  await expect(result).toContainText(
    /\d+\.\d\d km loop .* accepted 18\.00 km to 22\.00 km/,
  );
  await expect(result).toContainText("HeiGIT cycling-road estimate");
  const limitations = result.getByRole("list", { name: "Limitations" });
  await expect(limitations).toContainText(
    "Access everywhere else is unknown, not verified.",
  );
  await expect(limitations).toContainText("surface is unknown");
  await expect(limitations).toContainText(
    "on trunk roads (West Coast Highway)",
  );
  await expect(page.locator("path.leaflet-interactive").first()).toBeVisible();
  await result.getByText(/Restricted roads checked/).click();
  await expect(
    result.getByRole("list", { name: "Restricted roads" }),
  ).toContainText(
    "Central Expressway (expressway): crosses or passes beside it",
  );

  const downloadPromise = page.waitForEvent("download");
  await result.getByRole("link", { name: "Download GPX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^road-cycling-loop-.*\.gpx$/);
  const gpx = await readFile(await download.path(), "utf8");
  const runId = download
    .suggestedFilename()
    .slice("road-cycling-loop-".length, -".gpx".length);
  const route = await (
    await page.request.get(`/api/runs/${runId}/route`)
  ).json();
  const points = [...gpx.matchAll(/<trkpt lat="([^"]+)" lon="([^"]+)"/g)].map(
    (match) => [Number(match[2]), Number(match[1])],
  );
  expect(points).toEqual(route.geometry.coordinates);
});

test("a ride shorter than 5 km is refused before anything is generated", async ({
  page,
}) => {
  await page.getByLabel("Target km").fill("3");
  await page.getByRole("button", { name: "Generate loop" }).click();

  await expect(page.locator(".run").getByRole("alert")).toHaveText(
    "Enter a distance from 5 to 100 km.",
  );
});
