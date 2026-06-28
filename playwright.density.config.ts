import { defineConfig, devices } from "@playwright/test";

const useLocalChrome = process.env.PLAYWRIGHT_BROWSER_CHANNEL ?? (process.platform === "darwin" ? "chrome" : undefined);

export default defineConfig({
  testDir: "./tests/ui",
  testMatch: ["density-ui.spec.ts"],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.DENSITY_QA_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    ...(useLocalChrome ? { channel: useLocalChrome } : {}),
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
    url: "http://127.0.0.1:3000/density",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    {
      name: "density-ui",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
