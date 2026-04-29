import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT ?? process.env.VITE_PORT ?? "5174");
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${port}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./tests/e2e/recordings",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL,
    video: "on",
    screenshot: "on",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `VITE_USE_FIXTURES=true VITE_PORT=${port} npm run dev`,
    url: baseURL,
    reuseExistingServer,
    stdout: "pipe",
    stderr: "pipe",
    timeout: 60_000,
  },
});
