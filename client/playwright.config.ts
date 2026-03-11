import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "frontend-integration.spec.ts",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "MOCK_BACKEND_PORT=8011 node tests/mock-backend.mjs",
      port: 8011,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "VITE_BACKEND_URL=http://127.0.0.1:8011 npm run dev -- --host 127.0.0.1 --port 4173",
      port: 4173,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
