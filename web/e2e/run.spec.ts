import { readFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

const BLANK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
  "base64",
);

// HeiGIT is replaced by recorded responses inside the API (api/tests/serve_recorded.py).
// The browser must only ever talk to the route API, never to HeiGIT or a OneMap API.
async function stubUpstreams(page: Page) {
  await page.route("https://www.onemap.gov.sg/**", async (route) => {
    expect(route.request().url()).not.toContain("/api/");
    await route.fulfill({ contentType: "image/png", body: BLANK_TILE });
  });
  await page.route("https://api.heigit.org/**", async () => {
    throw new Error("the browser called HeiGIT");
  });
}

async function confirmAvenueSouth(page: Page) {
  await page.getByLabel("Search for a place, or tap the map").fill("avenue south residence");
  const matches = page.getByRole("list", { name: "Matching places" }).getByRole("button");
  await matches.filter({ hasText: "11 SILAT AVENUE" }).click();
  await page.getByRole("button", { name: "Confirm start" }).click();
  await expect(page.getByText("Start confirmed")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await stubUpstreams(page);
  await page.goto("/");
  await confirmAvenueSouth(page);
});

test("generate a 5 km loop, inspect it and download the same path as GPX", async ({ page }) => {
  await page.getByLabel("Target km").fill("5");
  await page.getByRole("button", { name: "Generate loop" }).click();

  const result = page.locator(".result");
  await expect(result).toContainText("5.26 km loop (+255 m from 5.00 km; accepted 4.50 km to 5.50 km)");
  await expect(result).toContainText("not a running time");
  await expect(result.getByRole("list", { name: "Limitations" })).toContainText("surface is unknown");
  await expect(page.locator("path.leaflet-interactive").first()).toBeVisible();
  await result.getByText("2 tries").click();
  await expect(result).toContainText("Seed 1: 6.496 km is outside 4.500-5.500 km");
  await expect(result).toContainText("Seed 2: accepted");

  const downloadPromise = page.waitForEvent("download");
  await result.getByRole("link", { name: "Download GPX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^running-loop-.*\.gpx$/);
  const gpx = await readFile(await download.path(), "utf8");
  const runId = download.suggestedFilename().slice("running-loop-".length, -".gpx".length);
  const route = await (await page.request.get(`/api/runs/${runId}/route`)).json();
  const points = [...gpx.matchAll(/<trkpt lat="([^"]+)" lon="([^"]+)"/g)].map((match) => [
    Number(match[2]),
    Number(match[1]),
  ]);
  expect(points).toEqual(route.geometry.coordinates);
});

test("an exact range no loop fits is reported with each rejection", async ({ page }) => {
  await page.getByLabel("Exact range").check();
  await page.getByLabel("From km").fill("5");
  await page.getByLabel("To km").fill("5.05");
  await page.getByRole("button", { name: "Generate loop" }).click();

  const error = page.locator(".run").getByRole("alert");
  await expect(error).toContainText("No acceptable loop between 5.00 km and 5.05 km after 5 tries.");
  await expect(error.getByRole("listitem")).toHaveCount(5);
  await expect(page.getByRole("link", { name: "Download GPX" })).toHaveCount(0);
});

test("an inverted range is refused before anything is generated", async ({ page }) => {
  await page.getByLabel("Exact range").check();
  await page.getByLabel("From km").fill("8");
  await page.getByLabel("To km").fill("6");
  await page.getByRole("button", { name: "Generate loop" }).click();

  await expect(page.locator(".run").getByRole("alert")).toContainText(
    "The lower end of the range must be below the upper end.",
  );
});
