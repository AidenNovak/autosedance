import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3612",
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: "node e2e/start-servers.mjs",
    url: "http://127.0.0.1:3612/new",
    timeout: 120_000,
    reuseExistingServer: process.env.PW_REUSE_SERVER === "1"
  }
});
