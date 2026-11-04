import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { config as loadEnv } from "dotenv";


loadEnv({
  path: "../../.env",
});


test("shows the OpsProof login identity", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByText("OpsProof", { exact: true }),
  ).toBeVisible();

  await expect(
    page.getByRole("heading", {
      name: /Evidence over assumptions/i,
    }),
  ).toBeVisible();

  await expect(
    page.getByLabel("Operator access key"),
  ).toBeVisible();
});


test("login screen has no serious accessibility violations", async ({
  page,
}) => {
  await page.goto("/");

  const results = await new AxeBuilder({
    page,
  }).analyze();

  const serious = results.violations.filter(
    (violation) =>
      violation.impact === "serious" ||
      violation.impact === "critical",
  );

  expect(serious).toEqual([]);
});


test("authenticates and shows real dashboard records", async ({
  page,
}) => {
  const accessKey = process.env.OPSPROOF_CONTROL_API_KEY;

  test.skip(
    !accessKey,
    "Local operator key is required for this integration test.",
  );

  await page.goto("/");

  await page
    .getByLabel("Operator access key")
    .fill(accessKey ?? "");

  await page
    .getByRole("button", {
      name: "Enter workspace",
    })
    .click();

  await expect(
    page.getByRole("heading", {
      name: "Know what failed. Prove what recovered.",
    }),
  ).toBeVisible();

  await expect(
    page.getByText("Recorded experiments"),
  ).toBeVisible();

  await page
    .getByRole("link", {
      name: "Experiments",
    })
    .click();

  await expect(
    page.getByRole("heading", {
      name: "Controlled tests. Verifiable outcomes.",
    }),
  ).toBeVisible();
});
