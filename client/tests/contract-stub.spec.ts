import { test, expect } from "@playwright/test";

test("route protection redirects unauthenticated users to login", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByTestId("login-submit")).toBeVisible();
});

test("fixture-backed workspace renders chat, scorecard, evidence, and comparison", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByTestId("login-submit").click();

  await expect(page.getByTestId("route-guard-shell")).toBeVisible();
  await expect(page.getByTestId("chat-timeline")).toContainText("Chat Timeline");
  await expect(page.getByTestId("scorecard-panel")).toContainText("Scorecard");
  await expect(page.getByTestId("evidence-panel")).toContainText("Evidence");

  await page.getByTestId("fixture-tab-comparison").click();
  await expect(page.getByTestId("comparison-view")).toContainText("Comparison Stub");
  await expect(page.getByTestId("comparison-view")).toContainText("Midnight Courts");
});
