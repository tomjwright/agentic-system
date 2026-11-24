import { expect, type Page, test } from "@playwright/test";

import { signIn } from "./sign-in";

const BLANK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
  "base64",
);

// Map tiles and the OneMap logo come from OneMap. Serve a blank image instead, and fail
// the test if the browser ever calls a OneMap API itself: only the route API may.
async function stubOneMap(page: Page) {
  await page.route("https://www.onemap.gov.sg/**", async (route) => {
    const url = route.request().url();
    expect(url).not.toContain("/api/");
    await route.fulfill({ contentType: "image/png", body: BLANK_TILE });
  });
}

test.beforeEach(async ({ page }) => {
  await stubOneMap(page);
  await signIn(page);
});

test("plural name shows the Bedok mismatch rather than choosing it", async ({ page }) => {
  await page.getByLabel("Search for a place, or tap the map").fill("avenue south residences");

  const matches = page.getByRole("list", { name: "Matching places" }).getByRole("button");
  await expect(matches).toHaveCount(6);
  await expect(matches.first()).toContainText("GRANDEUR PARK RESIDENCES");
  await expect(page.getByText("Start", { exact: true })).toHaveCount(0);
});

test("named search to confirmed start", async ({ page }) => {
  await page.getByLabel("Search for a place, or tap the map").fill("avenue south residence");

  const matches = page.getByRole("list", { name: "Matching places" }).getByRole("button");
  await expect(page.getByText("7 matches. Choose the right one.")).toBeVisible();
  await matches.filter({ hasText: "11 SILAT AVENUE" }).click();
  await page.getByLabel("Road cycling").check();
  await page.getByRole("button", { name: "Confirm start" }).click();

  const confirmed = page.getByRole("status");
  await expect(confirmed).toContainText("Start confirmed");
  await expect(confirmed).toContainText("AVENUE SOUTH RESIDENCE for road cycling");
  await expect(confirmed).toContainText("Source: OneMap");
});

test("map point to confirmed start", async ({ page }) => {
  await page.locator(".leaflet-container").click();

  await expect(page.getByText("Selected map point")).toBeVisible();
  await page.getByRole("button", { name: "Confirm start" }).click();

  const confirmed = page.getByRole("status");
  await expect(confirmed).toContainText("Map point for running");
  await expect(confirmed).toContainText("Source: map selection");
});

test("no match is stated", async ({ page }) => {
  await page.getByLabel("Search for a place, or tap the map").fill("qzxv nowhere");

  await expect(page.getByText("No place in Singapore matches “qzxv nowhere”.")).toBeVisible();
});
