import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("isolated M6 ledger has real database records, CSRF and accessible navigation", async ({ page }) => {
  test.skip(process.env.OPSPROOF_E2E_M6_ISOLATED !== "true", "Requires the isolated M6 SQL/API runner");
  const key = process.env.OPSPROOF_E2E_OPERATOR_KEY!;
  const trial = process.env.OPSPROOF_E2E_TRIAL_ID!;
  await page.goto("/trials");
  await expect(page.getByLabel("Operator access key")).toBeVisible();
  const anonymous = await page.request.get("/api/v1/m6/trials");
  expect(anonymous.status()).toBe(401);
  await page.getByLabel("Operator access key").fill(key);
  const login = page.waitForResponse(r => r.url().endsWith("/api/v1/auth/login"));
  await page.getByRole("button", {name: "Enter workspace"}).click();
  expect((await login).status()).toBe(200);
  await expect(page.getByRole("heading", {name: "Trial ledger"})).toBeVisible();
  await expect(page.getByText(trial, {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "misleading evidence"}).click();
  await expect(page.getByText(/phase:aborted/)).toBeVisible();
  await expect(page.getByText("No evidence has been attached.")).toBeVisible();
  await expect(page.getByText("No independent verification has been recorded.")).toBeVisible();
  expect(await page.evaluate(async (id) => (await fetch(`/api/v1/m6/trials/${id}/abort`, {
    method: "POST", headers: {"Content-Type": "application/json"},
  })).status, trial)).toBe(403);
  for (const width of [1280, 390]) {
    await page.setViewportSize({width, height: 844});
    const audit = await new AxeBuilder({page}).analyze();
    expect(audit.violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByRole("button", {name: "Open navigation"}).click();
  await page.getByRole("dialog").getByRole("link", {name: "Trials", exact: true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByRole("heading", {name: "Trial ledger"})).toBeVisible();
  await page.screenshot({path: process.env.OPSPROOF_E2E_M6_SCREENSHOT, fullPage: true});
});
