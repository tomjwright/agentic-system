import { expect, type Page } from "@playwright/test";

// The recorded API's fake GitHub signs Tom in straight away (api/tests/serve_recorded.py).
export async function signIn(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in with GitHub" }).click();
  await expect(page.getByLabel("Search for a place, or tap the map")).toBeVisible();
}
