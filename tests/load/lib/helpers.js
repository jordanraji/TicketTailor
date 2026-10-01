// Shared helpers for the QA1 k6 load scenarios.
//
// Every scenario targets a single base URL via the BASE_URL env var:
//   k6 run -e BASE_URL=http://<alb-dns> tests/load/scenarios/<scenario>.js
// The scripts run against any reachable stack, but the QA1 numbers are only
// meaningful against the deployed AWS stack (autoscaling, read replica,
// SNS/SQS/Lambda). See tests/load/README.md.

import http from "k6/http";
import { check, fail, sleep } from "k6";

export const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) {
  throw new Error("BASE_URL env var is required, e.g. -e BASE_URL=http://<alb-dns>");
}

const PASSWORD = "LoadTest-pass-123";

// Monotonic-ish unique suffix. setup() runs single-threaded so the counter is
// safe there; the timestamp keeps it unique across separate runs.
let _seq = 0;
export function uniqueEmail(prefix) {
  _seq += 1;
  // example.com (RFC 2606 reserved) - the API's email validator rejects the
  // .local reserved TLD, so test addresses must use a real, non-special TLD.
  return `${prefix}-${Date.now()}-${_seq}@loadtest.example.com`;
}

export function jsonHeaders() {
  return { "Content-Type": "application/json" };
}

export function authHeaders(token) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

// Register a user and return { id, email, token }. Fails fast on a bad setup
// so a misconfigured stack does not silently produce empty load.
export function registerAndLogin(prefix) {
  const email = uniqueEmail(prefix);
  const reg = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, password: PASSWORD, display_name: "Load User" }),
    { headers: jsonHeaders() },
  );
  if (!check(reg, { "register 201": (r) => r.status === 201 })) {
    fail(`register failed (${reg.status}): ${reg.body}`);
  }
  const id = reg.json("id");

  // The just-registered user may not be visible to an immediate login: the API
  // commits after the response (app_services.get_db_session) and, on the
  // deployed stack, login reads the replica which lags the primary write
  // (ADR-0008). Both are short read-your-writes windows, so retry the login a
  // few times before giving up - otherwise one racing 401 aborts the whole run.
  let login;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    login = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email, password: PASSWORD }),
      { headers: jsonHeaders() },
    );
    if (login.status === 200) {
      break;
    }
    sleep(0.25);
  }
  if (!check(login, { "login 200": (r) => r.status === 200 })) {
    fail(`login failed after retries (${login.status}): ${login.body}`);
  }
  return { id, email, token: login.json("access_token") };
}

export function createClub(token, name) {
  const res = http.post(
    `${BASE_URL}/clubs`,
    JSON.stringify({ name, description: "Load test club" }),
    { headers: authHeaders(token) },
  );
  if (!check(res, { "create club 201": (r) => r.status === 201 })) {
    fail(`create club failed (${res.status}): ${res.body}`);
  }
  return res.json("id");
}

export function followClub(token, clubId) {
  // Follow is POST /users/follow/{club_id} (club in path, no body).
  return http.post(`${BASE_URL}/users/follow/${clubId}`, null, {
    headers: authHeaders(token),
  });
}

// Create an event. transitionAtIso null => no scheduled flip. Pass a future ISO
// string with visibility "club_only" to schedule an FR5 visibility flip.
export function createEvent(token, { clubId, lat, lng, visibility, transitionAtIso, category }) {
  const body = {
    club_id: clubId,
    title: "Load Test Event",
    category: category || null,
    latitude: lat,
    longitude: lng,
    starts_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    is_free: true,
    price: null,
    visibility: visibility || "public",
    transition_at: transitionAtIso || null,
  };
  const res = http.post(`${BASE_URL}/events`, JSON.stringify(body), {
    headers: authHeaders(token),
  });
  if (!check(res, { "create event 201": (r) => r.status === 201 })) {
    fail(`create event failed (${res.status}): ${res.body}`);
  }
  return res.json("id");
}

export function placeRsvp(token, eventId) {
  const res = http.post(`${BASE_URL}/events/${eventId}/rsvp`, null, {
    headers: authHeaders(token),
  });
  if (!check(res, { "place rsvp 201": (r) => r.status === 201 })) {
    fail(`place rsvp failed (${res.status}): ${res.body}`);
  }
  return res;
}

// PATCH an event with a partial body (e.g. { title: "New title" }). Used by the
// FR7 organiser-edit scenario to trigger the event_updated fan-out.
export function updateEvent(token, eventId, patch) {
  const res = http.patch(`${BASE_URL}/events/${eventId}`, JSON.stringify(patch), {
    headers: authHeaders(token),
  });
  if (!check(res, { "update event 200": (r) => r.status === 200 })) {
    fail(`update event failed (${res.status}): ${res.body}`);
  }
  return res;
}

// Reference point for seeded events / map queries: UQ St Lucia.
export const CENTER = { lat: -27.4975, lng: 153.0137 };

// Small deterministic jitter so concurrent map queries spread across cache keys
// (the geo cache has a 30s TTL) and actually exercise the replica, not just one
// hot cache entry.
export function jitter(base, spreadDeg) {
  return base + (Math.random() - 0.5) * 2 * spreadDeg;
}
