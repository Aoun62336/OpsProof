import { defineConfig, devices } from "@playwright/test";

const cloudProfile = process.env.OPSPROOF_E2E_CLOUD_PROFILE === "true";
const localUrl = cloudProfile ? "http://127.0.0.1:8081" : "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.OPSPROOF_E2E_BASE_URL ?? localUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.OPSPROOF_E2E_BASE_URL ? undefined : {
    command: cloudProfile ? "npm run preview -- --host 127.0.0.1 --port 8081 --strictPort" : "npm run dev",
    url: localUrl,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
