import { expect, test } from "@playwright/test";

import { signIn } from "./sign-in";

test("signed out, the page offers only GitHub sign-in", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Sign in with GitHub" })).toBeVisible();
  await expect(page.getByLabel("Search for a place, or tap the map")).toHaveCount(0);
});

test("sign in, then sign out ends the session", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("link", { name: "Sign in with GitHub" })).toBeVisible();
  const me = await page.request.get("/api/auth/me");
  expect(me.status()).toBe(401);
});

test("a refused sign-out keeps the session and says so", async ({ page }) => {
  await signIn(page);
  await page.route("/api/auth/logout", (route) =>
    route.fulfill({
      status: 429,
      json: { error: { code: "rate_limited", message: "Too many requests; wait a minute" } },
    }),
  );
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByText("Sign-out failed: Too many requests; wait a minute"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
});
