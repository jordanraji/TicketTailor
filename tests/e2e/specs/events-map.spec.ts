// FR2: the interactive map renders (OpenStreetMap tiles via MapLibre GL JS,
// ADR-0019) and plots events returned by the geo-radius browse. Seeds a public
// event at the map's default centre (UQ St Lucia) through the API, signs the
// browser in by seeding the access token, then asserts the map canvas renders
// and at least the centre pin plus the seeded event are plotted.

import { test, expect, request, type APIRequestContext } from "@playwright/test";

const API_URL = process.env.API_URL || "http://localhost:8000";
const PASSWORD = "E2e-pass-1234";
const CENTER = { lat: -27.4975, lng: 153.0137 }; // UQ St Lucia, the map default

async function seedNearbyEvent(
  api: APIRequestContext,
): Promise<{ token: string; title: string }> {
  const stamp = Date.now();
  const email = `map-organiser-${stamp}@example.com`;

  const reg = await api.post(`${API_URL}/auth/register`, {
    data: { email, password: PASSWORD, display_name: "Map Organiser" },
  });
  expect(reg.status(), await reg.text()).toBe(201);

  const login = await api.post(`${API_URL}/auth/login`, {
    data: { email, password: PASSWORD },
  });
  const token = (await login.json()).access_token as string;
  const auth = { Authorization: `Bearer ${token}` };

  const club = await api.post(`${API_URL}/clubs`, {
    headers: auth,
    data: { name: `Map Club ${stamp}`, description: "map fixtures" },
  });
  const clubId = (await club.json()).id as string;

  const title = `Map Event ${stamp}`;
  const event = await api.post(`${API_URL}/events`, {
    headers: auth,
    data: {
      club_id: clubId,
      title,
      category: "Music",
      latitude: String(CENTER.lat),
      longitude: String(CENTER.lng),
      starts_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
      is_free: true,
      visibility: "public",
    },
  });
  expect(event.status(), await event.text()).toBe(201);
  return { token, title };
}

test("FR2 map renders and plots a nearby event", async ({ page }) => {
  const api = await request.newContext();
  const { token } = await seedNearbyEvent(api);

  // Sign the browser in by seeding the bearer token the API client reads.
  await page.addInitScript((t) => {
    localStorage.setItem("access_token", t as string);
  }, token);

  await page.goto("/events/map/");

  // The MapLibre canvas renders (WebGL via the headless shell's swiftshader).
  await expect(page.locator(".maplibregl-canvas")).toBeVisible({
    timeout: 20000,
  });

  // The result count reflects at least the seeded event.
  await expect(page.getByText(/within 5 km/)).toBeVisible();

  // Centre pin + at least one event marker. Other events seeded near UQ by
  // earlier runs may add more, so assert "at least two", not an exact count.
  await expect
    .poll(async () => page.locator(".maplibregl-marker").count(), {
      timeout: 15000,
    })
    .toBeGreaterThanOrEqual(2);

  await api.dispose();
});
