// AR3: the end-to-end happy path - signup -> RSVP -> calendar -> push.
//
// The flow is driven through the real browser against the static-export
// frontend, with one exception noted at step 5. An organiser + public event is
// seeded via the API first (fast and deterministic), then the test acts purely
// as a fresh attendee through the UI.

import { test, expect, request, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";

const API_URL = process.env.API_URL || "http://localhost:8000";
const PASSWORD = "E2e-pass-1234";

// Seed an organiser, a club, and a public event straight through the API and
// return the event id so the browser flow has something to RSVP to.
async function seedPublicEvent(
  api: APIRequestContext,
): Promise<{ eventId: string; title: string }> {
  // The API's email validator rejects reserved TLDs (.local), so use example.com.
  const stamp = Date.now();
  const email = `e2e-organiser-${stamp}@example.com`;

  const reg = await api.post(`${API_URL}/auth/register`, {
    data: { email, password: PASSWORD, display_name: "E2E Organiser" },
  });
  expect(reg.status(), await reg.text()).toBe(201);

  const login = await api.post(`${API_URL}/auth/login`, {
    data: { email, password: PASSWORD },
  });
  expect(login.ok(), await login.text()).toBeTruthy();
  const token = (await login.json()).access_token as string;
  const auth = { Authorization: `Bearer ${token}` };

  const club = await api.post(`${API_URL}/clubs`, {
    headers: auth,
    data: { name: `E2E Club ${stamp}`, description: "e2e fixtures" },
  });
  expect(club.status(), await club.text()).toBe(201);
  const clubId = (await club.json()).id as string;

  const title = `E2E Happy Path Event ${stamp}`;
  const event = await api.post(`${API_URL}/events`, {
    headers: auth,
    data: {
      club_id: clubId,
      title,
      latitude: "-27.4975",
      longitude: "153.0137",
      starts_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
      is_free: true,
      visibility: "public",
    },
  });
  expect(event.status(), await event.text()).toBe(201);
  return { eventId: (await event.json()).id as string, title };
}

test("AR3 happy path: signup -> RSVP -> calendar -> push recipient", async ({
  page,
}) => {
  const api = await request.newContext();
  const { eventId } = await seedPublicEvent(api);

  // The auth pages confirm with window.alert(); auto-accept so the flow runs.
  page.on("dialog", (dialog) => dialog.accept());

  const stamp = Date.now();
  const email = `e2e-attendee-${stamp}@example.com`;

  // 1. Sign up.
  await page.goto("/sign-up");
  await page.fill("#username", `e2e-attendee-${stamp}`);
  await page.fill("#email", email);
  await page.fill("#password", PASSWORD);
  await page.fill("#confirmPassword", PASSWORD);
  await page.click('button[type="submit"]');
  // register() redirects here on success. trailingSlash:true (ADR-0018) means
  // the URL is /sign-in/, so match with an optional trailing slash.
  await page.waitForURL(/\/sign-in\/?$/);

  // 2. Sign in (stores the bearer token in localStorage, lib/auth.js).
  await page.fill("#email", email);
  await page.fill("#password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/events\/?$/);

  // 3. Open the seeded event and RSVP (FR3). The counter must tick 0 -> 1 and
  //    the button must flip to the cancel affordance.
  await page.goto(`/events/detail/?id=${eventId}`);
  const count = page.getByTestId("attendee-count");
  await expect(count).toHaveText(/^0 attending$/);
  await page.getByTestId("rsvp-button").click();
  await expect(count).toHaveText(/^1 attending$/);
  await expect(page.getByTestId("rsvp-button")).toHaveText(/Cancel RSVP/);

  // 4. Add to calendar (FR6): the button fetches the authed iCal endpoint and
  //    triggers a blob download. Assert it is a well-formed VCALENDAR.
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("add-to-calendar").click(),
  ]);
  const icsPath = await download.path();
  const ics = fs.readFileSync(icsPath, "utf8");
  expect(ics).toContain("BEGIN:VCALENDAR");
  expect(ics).toContain("BEGIN:VEVENT");

  // 5. Push leg. Real web-push delivery needs a service worker, VAPID keys and
  //    a push service - out of scope for a headless functional run. What the
  //    happy path proves here is the PRECONDITION for FR7: this user is now an
  //    RSVP'd attendee, i.e. a member of the notification recipient set an
  //    organiser edit fans out to. Delivery itself is covered by
  //    worker/tests/test_organiser_edit_push.py (correctness) and
  //    tests/load/scenarios/organiser_edit.js (push-ack latency SLO).
  await page.reload();
  await expect(page.getByTestId("attendee-count")).toHaveText(/^1 attending$/);

  await api.dispose();
});
