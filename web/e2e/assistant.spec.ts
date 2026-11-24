import { readFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

import { signIn } from "./sign-in";

const BLANK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
  "base64",
);

// The recorded API answers with scripted fake models (AGENT_SCRIPT in api/tests/serve_recorded.py)
// and recorded HeiGIT. The browser must never call a model, HeiGIT or a OneMap API.
async function stubUpstreams(page: Page) {
  await page.route("https://www.onemap.gov.sg/**", async (route) => {
    expect(route.request().url()).not.toContain("/api/");
    await route.fulfill({ contentType: "image/png", body: BLANK_TILE });
  });
  await page.route("https://api.heigit.org/**", async () => {
    throw new Error("the browser called HeiGIT");
  });
}

function agentError(status: number, code: string, message: string) {
  return { status, contentType: "application/json", body: JSON.stringify({ error: { code, message } }) };
}

test.beforeEach(async ({ page }) => {
  await stubUpstreams(page);
  await signIn(page);
  await page.getByLabel("Search for a place, or tap the map").fill("avenue south residence");
  const matches = page.getByRole("list", { name: "Matching places" }).getByRole("button");
  await matches.filter({ hasText: "11 SILAT AVENUE" }).click();
  await page.getByRole("button", { name: "Confirm start" }).click();
  await expect(page.getByText("Start confirmed")).toBeVisible();
});

test("answer the assistant's question, then get its judged loop as the stored GPX", async ({
  page,
}) => {
  const assistant = page.locator(".assistant");
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/agent-runs",
    async (route) => {
      await held;
      await route.continue();
    },
    { times: 1 },
  );
  await assistant.getByLabel("Ask the route assistant").fill("a 10k run");
  await assistant.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(assistant.getByRole("status")).toContainText("Asking the route assistant");
  await expect(assistant.getByRole("button", { name: "Ask", exact: true })).toBeDisabled();
  release();
  await expect(assistant).toContainText(
    "Your form says 5 km but your message says 10 km. Which would you like?",
  );
  await expect(assistant.getByRole("list", { name: "Assistant steps" }).getByRole("listitem")).toHaveText([
    "Read your message",
    "Asked you to clarify: conflict",
    "Drafted an answer",
    "Judge approved it",
  ]);
  await expect(page.getByRole("link", { name: "Download GPX" })).toHaveCount(0);

  await assistant.getByLabel("Your reply").fill("5k is fine");
  const answered = page.waitForResponse("**/agent-runs");
  await assistant.getByRole("button", { name: "Send reply" }).click();
  const answer = await (await answered).json();

  await expect(assistant).toContainText("Here is a 5.26 km running loop from Avenue South Residence.");
  await expect(assistant.getByRole("list", { name: "Assistant steps" }).getByRole("listitem")).toHaveText([
    "Read your message",
    "Generated a loop: 2 tries",
    "Drafted an answer",
    "Judge approved it",
  ]);
  const result = page.locator(".result");
  await expect(result).toContainText("5.26 km loop (+255 m from 5.00 km; accepted 4.50 km to 5.50 km)");
  await expect(page.locator('path[stroke="#1565c0"]')).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await result.getByRole("link", { name: "Download GPX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`running-loop-${answer.run.generation_run_id}.gpx`);
  const gpx = await readFile(await download.path(), "utf8");
  const route = await (await page.request.get(`/api/runs/${answer.run.generation_run_id}/route`)).json();
  const points = [...gpx.matchAll(/<trkpt lat="([^"]+)" lon="([^"]+)"/g)].map((match) => [
    Number(match[2]),
    Number(match[1]),
  ]);
  expect(points).toEqual(route.geometry.coordinates);
});

test("without model keys the assistant says it is not set up and the form still works", async ({
  page,
}) => {
  await page.route("**/agent-runs", (route) =>
    route.fulfill(agentError(503, "agent_not_configured", "The route assistant is not configured")),
  );
  const assistant = page.locator(".assistant");
  await assistant.getByLabel("Ask the route assistant").fill("a 5k run");
  await assistant.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(assistant).toContainText("The route assistant is not set up here.");
  await expect(assistant.getByLabel("Ask the route assistant")).toHaveCount(0);
  await page.getByRole("button", { name: "Generate loop" }).click();
  await expect(page.locator(".result")).toContainText("5.26 km loop");
});

test("a failed assistant run is shown as an error", async ({ page }) => {
  await page.route("**/agent-runs", (route) =>
    route.fulfill(agentError(500, "agent_failed", "The route assistant failed; try again")),
  );
  const assistant = page.locator(".assistant");
  await assistant.getByLabel("Ask the route assistant").fill("a 5k run");
  await assistant.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(assistant.getByRole("alert")).toHaveText("The route assistant failed; try again");
});
