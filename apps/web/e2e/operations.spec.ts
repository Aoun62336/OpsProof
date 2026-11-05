import {
  expect,
  test,
} from "@playwright/test";

import AxeBuilder from "@axe-core/playwright";
import { config as loadEnv } from "dotenv";

loadEnv({
  path: "../../.env",
});

async function signIn(
  page: import("@playwright/test").Page,
) {
  const key = process.env.OPSPROOF_CONTROL_API_KEY;

  test.skip(
    !key,
    "Local operator key required for authenticated browser tests",
  );

  await page.goto("/");

  await page
    .getByLabel("Operator access key")
    .fill(key ?? "");

  await page
    .getByRole("button", {
      name: "Enter workspace",
    })
    .click();

  await expect(
    page.getByRole("heading", {
      name: "Operations",
      exact: true,
    }),
  ).toBeVisible();
}

test("logout rejects invalid CSRF and returns to login", async ({ page }) => {
  await signIn(page);
  const status = await page.evaluate(async () => {
    const response = await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: { "X-OpsProof-CSRF": "invalid" },
    });
    return response.status;
  });
  expect(status).toBe(403);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Operator access key")).toBeVisible();
});

test(
  "branded login shows approved identity",
  async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", {
        name: /Every recovery deserves proof/i,
      }),
    ).toBeVisible();

    await expect(
      page.getByLabel("Operator access key"),
    ).toBeVisible();
  },
);

test(
  "login has no serious accessibility violations",
  async ({ page }) => {
    await page.goto("/");

    const result = await new AxeBuilder({
      page,
    }).analyze();

    expect(
      result.violations.filter(
        (violation) =>
          violation.impact === "serious" ||
          violation.impact === "critical",
      ),
    ).toEqual([]);
  },
);

test(
  "real dashboard and experiment navigation",
  async ({ page }) => {
    await signIn(page);

    await expect(
      page.getByText("Recent experiments"),
    ).toBeVisible();

    await page
      .getByRole("link", {
        name: "Experiments",
        exact: true,
      })
      .click();

    await expect(
      page.getByRole("heading", {
        name: "Experiments",
        exact: true,
      }),
    ).toBeVisible();
  },
);

test(
  "mobile drawer opens and closes with Escape",
  async ({ page }) => {
    await page.setViewportSize({
      width: 390,
      height: 844,
    });

    await signIn(page);

    const menu = page.getByRole("button", {
      name: "Open navigation",
    });

    await expect(menu).toBeVisible();

    await menu.click();

    await expect(
      page.getByRole("dialog", {
        name: "Workspace navigation",
      }),
    ).toBeVisible();

    await page.keyboard.press("Escape");

    await expect(
      page.getByRole("dialog", {
        name: "Workspace navigation",
      }),
    ).not.toBeVisible();

    await expect(menu).toBeFocused();
  },
);

test(
  "desktop does not show mobile navigation controls",
  async ({ page }) => {
    await page.setViewportSize({
      width: 1440,
      height: 900,
    });

    await signIn(page);

    await expect(
      page.getByRole("button", {
        name: "Open navigation",
      }),
    ).toBeHidden();
  },
);

test(
  "incident registry is accessible",
  async ({ page }) => {
    await signIn(page);

    await page
      .getByRole("link", {
        name: "Incidents",
      })
      .click();

    await expect(
      page.getByRole("heading", {
        name: "Incidents",
        exact: true,
      }),
    ).toBeVisible();

    await expect(
      page.getByText(
        /Detection is not the same as recovery/i,
      ),
    ).toBeVisible();
  },
);
