import { expect, test } from "@playwright/test";

async function login(page, username: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-username").fill(username);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
}

test("IADE can sign in and see the live waveform monitor", async ({ page }) => {
  await login(page, "iade1", "charles2026");

  await page.waitForURL(/\/$/);
  await expect(page.getByTestId("status-rooms")).toContainText("salle");
  await expect(page.getByTestId("transport-metrics")).toContainText("ws");
  await expect(page.getByTestId("room-monitor")).toBeVisible();
});

test("Admin can inspect live metrics and launch a synthetic scenario", async ({ page }) => {
  await login(page, "admin", "admin2026");

  await page.waitForURL(/\/admin$/);
  await page.getByTestId("admin-tab-system").click();
  await expect(page.getByTestId("admin-metrics-card")).toContainText("Wave chunks");

  await page.getByTestId("admin-tab-simulator").click();
  await expect(page.getByTestId("scenario-panel")).toBeVisible();
  await page.getByTestId("scenario-category-scenarios_synthetiques").click();
  await page.getByTestId("scenario-target-room").selectOption("salle_1");
  await expect(page.getByTestId("launch-synthetic-hypotension")).toBeVisible();
  await page.getByTestId("launch-synthetic-hypotension").click();

  await page.goto("/");
  await expect(page.getByTestId("room-monitor")).toBeVisible();
});
