import { defineConfig, devices } from "@playwright/test";

// The frontend (Next.js static-export, ADR-0018) is auto-served by Playwright's
// webServer below. The API is NOT started here - bring it up first with
// `docker compose up` from the repo root so it is reachable at API_URL.
const WEB_URL = process.env.WEB_URL || "http://localhost:3000";
const API_URL = process.env.API_URL || "http://localhost:8000";

export default defineConfig({
  testDir: "./specs",
  // A fresh signup + RSVP + calendar download is quick, but the dev server's
  // first compile can be slow, so give each test room.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  // The happy path mutates shared state (RSVP counts); keep it serial.
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  // Serve the frontend with the API base URL injected. reuseExistingServer lets
  // you point at an already-running `npm run dev` during local iteration.
  webServer: {
    command: "npm run dev",
    cwd: "../../web",
    url: WEB_URL,
    reuseExistingServer: true,
    timeout: 120_000,
    env: { NEXT_PUBLIC_API_URL: API_URL },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
