import { expect, type Page, test } from "@playwright/test";

import { signIn } from "./sign-in";

const BLANK_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
  "base64",
);

// The recorded API answers with scripted fake models (AGENT_SCRIPT in api/tests/serve_recorded.py).
// The browser must never call a model, HeiGIT or a OneMap API.
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
  await signIn(page);
});

test("ask before confirming a start, pick one of every match, then get its loop", async ({ page }) => {
  const assistant = page.locator(".start-assistant");
  const runs: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/runs") || request.url().includes("/route-requests")) {
      runs.push(new URL(request.url()).pathname);
    }
  });
  await assistant.getByLabel("Or ask the route assistant").fill("a 5k run from Avenue South Residence");
  const asked = page.waitForResponse("**/api/agent-runs");
  await assistant.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(assistant).toContainText("Which Avenue South Residence block do you start from?");
  const matches = assistant.getByRole("list", { name: "Starts the assistant found" }).getByRole("button");
  await expect(matches).toHaveCount(7);
  await expect(page.getByText("Start confirmed")).toHaveCount(0);
  await expect(page.locator('path[stroke="#1565c0"]')).toHaveCount(0);
  expect(runs).toEqual([]);

  const firstAnswer = await (await asked).json();
  const matchId = firstAnswer.start_choices.candidates.find((candidate: { address: string }) =>
    candidate.address.startsWith("11 SILAT AVENUE"),
  ).source_id;
  const answered = page.waitForResponse("**/route-requests/*/agent-runs");
  await matches.filter({ hasText: "11 SILAT AVENUE" }).click();
  const answer = await (await answered).json();

  const confirmed = page.getByRole("status").filter({ hasText: "Start confirmed" });
  await expect(confirmed).toContainText("AVENUE SOUTH RESIDENCE for running");
  await expect(page.locator(".assistant")).toContainText(
    "Here is a 5.26 km running loop from Avenue South Residence.",
  );
  await expect(page.locator(".result")).toContainText("5.26 km loop");
  await expect(page.locator('path[stroke="#1565c0"]')).toBeVisible();
  const routeRequest = await (await page.request.get(`/api/route-requests/${answer.run.route_request_id}`)).json();
  expect(routeRequest.start.source_id).toBe(matchId);
  expect(routeRequest.start.point.coordinates).toEqual([103.8291052120283, 1.276629534107344]);
});

test("a start the assistant cannot find is asked for again, with no buttons", async ({ page }) => {
  const answer = {
    message: "No place called 'Nowhere Lane' was found. Which start do you mean?",
    run: { kind: "clarification", generation_run_id: null },
    steps: [{ name: "read_request" }, { name: "asked_clarification", reason: "missing_start" }],
    start_choices: null,
  };
  await page.route("**/api/agent-runs", (route) => route.fulfill({ status: 201, json: answer }));
  const assistant = page.locator(".start-assistant");
  await assistant.getByLabel("Or ask the route assistant").fill("a 5k run from Nowhere Lane");
  await assistant.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(assistant).toContainText("No place called 'Nowhere Lane' was found.");
  await expect(assistant.getByRole("list", { name: "Starts the assistant found" })).toHaveCount(0);
  await expect(assistant.getByLabel("Edit your message")).toHaveValue("a 5k run from Nowhere Lane");
});
