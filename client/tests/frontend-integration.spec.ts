import { expect, test } from "@playwright/test";

test("protected route redirects to login", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByTestId("login-submit")).toBeVisible();
});

test("login and render evaluation response with evidence", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-username").fill("testuser");
  await page.getByTestId("login-password").fill("testpass");
  await page.getByTestId("login-submit").click();

  await expect(page.getByText("Authenticated Decision Support")).toBeVisible();
  await page.getByTestId("chat-input").fill("Should we greenlight Neon Shore?");
  await page.getByTestId("chat-submit").click();

  await expect(page.getByTestId("assistant-answer")).toContainText("conditional greenlight");
  await expect(page.getByTestId("scorecard-panel")).toContainText("Neon Shore Original Series");
  await expect(page.getByTestId("evidence-panel")).toContainText("Neon Shore Pilot Script");
});

test("follow-up and comparison flows render in same session context", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("login-submit").click();

  await page.getByTestId("chat-input").fill("Should we greenlight Neon Shore?");
  await page.getByTestId("chat-submit").click();
  await expect(page.getByTestId("assistant-answer")).toContainText("conditional greenlight");

  await page.getByLabel("Query Type").click();
  await page.getByRole("option", { name: "Follow-up: ROI" }).click();
  await page.getByTestId("chat-input").fill("Why is ROI near breakeven?");
  await page.getByTestId("chat-submit").click();
  await expect(page.getByTestId("assistant-answer")).toContainText("breakeven");
  await expect(page.getByTestId("scorecard-panel")).toContainText(
    "Follow-up answer is based on cached ROI outputs.",
  );

  await page.getByLabel("Query Type").click();
  await page.getByRole("option", { name: "Comparison" }).click();
  await page.getByTestId("chat-input").fill("Compare Neon Shore and Midnight Courts");
  await page.getByTestId("chat-submit").click();
  await expect(page.getByTestId("comparison-view")).toContainText("Midnight Courts");
  await expect(page.getByTestId("comparison-view")).toContainText("Neon Shore");
});
