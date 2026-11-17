import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";

test("private cloud profile preserves palette, auth and read-only cards at five widths", async ({ page }) => {
  test.skip(process.env.OPSPROOF_E2E_CLOUD_PROFILE !== "true", "Requires owned SQL/API fixture runner");
  test.setTimeout(120_000);
  const output = process.env.OPSPROOF_E2E_CLOUD_OUTPUT!;
  await mkdir(output, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/workloads");
  expect((await page.request.get("/api/v1/kubernetes/workloads")).status()).toBe(401);
  await page.getByLabel("Operator access key").fill(process.env.OPSPROOF_E2E_OPERATOR_KEY!);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(page.getByRole("heading", { name: "Workloads", exact: true })).toBeVisible();
  const capabilities = await (await page.request.get("/api/v1/capabilities")).json();
  expect(capabilities.environment).toBe("temporary-eks");
  expect(capabilities.ai_enabled).toBe(false);
  const state = await (await page.request.get("/api/v1/kubernetes/workloads")).json();
  expect(state.recovery_enabled).toBe(false);
  expect(state.observations[0].resource.metadata.uid).toBe("isolated-ui-fixture");
  // Authenticated mutation remains denied even with the genuine session CSRF value.
  const session = await (await page.request.get("/api/v1/auth/session")).json();
  expect(session.authenticated).toBe(true);
  const denied = await page.request.post("/api/v1/kubernetes/recoveries", {
    headers: { "X-OpsProof-CSRF": session.csrf_token, "Idempotency-Key": "cloud-ui-fixture-only" },
    data: { action: "restore_demo_worker", incident_fingerprint: "fixture-incident-12345", run_id: "00000000-0000-0000-0000-000000000001" },
  });
  expect(denied.status()).toBe(403);
  expect((await denied.json()).detail).toBe("Kubernetes recovery is disabled");
  for (const width of [1440, 1280, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, title] of [["workloads", "Workloads"], ["deployments", "Deployments"], ["capacity", "Capacity"], ["runbooks", "Runbooks"]]) {
      await page.goto(`/${route}`);
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: "demo-worker", exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      const palette = await page.evaluate(() => {
        const styles = getComputedStyle(document.documentElement);
        return [styles.getPropertyValue("--forest").trim(), styles.getPropertyValue("--porcelain").trim()];
      });
      expect(palette).toEqual(["#121d19", "#f2f0e9"]);
      if (route === "runbooks") {
        await expect(page.getByRole("heading", { name: "Recovery actions are disabled" })).toBeVisible();
        await expect(page.getByLabel("Incident fingerprint")).toHaveCount(0);
        await expect(page.getByRole("button", { name: /Approve restoring/ })).toHaveCount(0);
      }
      const audit = await new AxeBuilder({ page }).analyze();
      expect(audit.violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
      await page.screenshot({ path: `${output}/${route}-${width}.png`, fullPage: true });
    }
  }
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "Capacity", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(errors).toEqual([]);
  // This is an explicitly synthetic local observation, never AWS screenshot proof.
});
