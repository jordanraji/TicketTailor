// FR7: an organiser edits an event and every RSVP'd attendee is pushed a
// notification. With N attendees this is a fan-out spike on the same
// relay -> SNS -> SQS -> Lambda path as the visibility flip, but triggered by a
// PATCH /events/{id} instead of a scheduled visibility transition.
//
// ASR: push ack at the push service p95 <= 5 s, p99 <= 10 s (ADR-0011);
// concurrent map-query p99 <= 500 ms; error rate < 1 %.
//
//   k6 run -e BASE_URL=http://<alb-dns> tests/load/scenarios/organiser_edit.js
//
// IMPORTANT measurement boundary (same as visibility_spike.js): push-ack
// latency is an ASYNCHRONOUS pipeline terminating at the worker, NOT an HTTP
// response k6 can time. So k6 owns only:
//   1. seeding the N RSVP'd attendees and firing the edit at a known instant,
//      and
//   2. generating + asserting the concurrent map load (p99, error rate).
// The push-ack p95/p99 is computed from worker CloudWatch logs against the
// edit timestamp this script prints. The Logs Insights query is in
// tests/load/README.md.
//
// Two scenarios run concurrently: background_browse generates the map load;
// trigger_edit is a single one-shot iteration that fires the edit WARMUP_S into
// the run (via startTime), once the map load has ramped.
//
// Tunables: ATTENDEES (default 1000), RATE (map req/s, default 50),
// DURATION (default 2m), WARMUP_S (seconds after start before the edit fires).

import http from "k6/http";
import { check } from "k6";
import {
  authHeaders,
  registerAndLogin,
  createClub,
  createEvent,
  placeRsvp,
  updateEvent,
  CENTER,
  jitter,
  BASE_URL,
} from "../lib/helpers.js";

const ATTENDEES = Number(__ENV.ATTENDEES || 1000);
const RATE = Number(__ENV.RATE || 50);
const DURATION = __ENV.DURATION || "2m";
const WARMUP_S = Number(__ENV.WARMUP_S || 45);
// Concurrent map-query p99 budget (ms); defaults to the QA1 SLO, overridable
// (GEO_P99_MS) for an out-of-region harness. SETUP_TIMEOUT bounds the seeding
// phase (raise it when seeding many attendees over a high-RTT link).
const GEO_P99_MS = Number(__ENV.GEO_P99_MS || 500);
const SETUP_TIMEOUT = __ENV.SETUP_TIMEOUT || "20m";

export const options = {
  setupTimeout: SETUP_TIMEOUT, // seeding attendees (register + RSVP) is sequential.
  scenarios: {
    background_browse: {
      executor: "constant-arrival-rate",
      exec: "browse",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.ceil(RATE * 1.5),
      maxVUs: RATE * 4,
    },
    trigger_edit: {
      executor: "per-vu-iterations",
      exec: "triggerEdit",
      vus: 1,
      iterations: 1,
      startTime: `${WARMUP_S}s`,
    },
  },
  thresholds: {
    "http_req_duration{name:geo_search}": [`p(99)<${GEO_P99_MS}`],
    // The one-shot PATCH must not count against the map-load error budget.
    "http_req_failed{name:geo_search}": ["rate<0.01"],
  },
};

export function setup() {
  const organiser = registerAndLogin("edit-organiser");
  const clubId = createClub(organiser.token, `Edit Club ${Date.now()}`);

  // A public event so attendees can RSVP without club membership.
  const eventId = createEvent(organiser.token, {
    clubId,
    lat: CENTER.lat,
    lng: CENTER.lng,
    visibility: "public",
  });

  // Seed N attendees who each RSVP. Sequential and the slow part of setup; tune
  // ATTENDEES down for a smaller smoke run.
  for (let i = 0; i < ATTENDEES; i += 1) {
    const attendee = registerAndLogin(`edit-attendee-${i}`);
    placeRsvp(attendee.token, eventId);
  }

  const browser = registerAndLogin("edit-browser");

  return {
    organiserToken: organiser.token,
    eventId,
    token: browser.token,
  };
}

// background_browse: concurrent map traffic so the edit fans out under load.
export function browse(data) {
  const lat = jitter(CENTER.lat, 0.01).toFixed(6);
  const lng = jitter(CENTER.lng, 0.01).toFixed(6);
  const res = http.get(
    `${BASE_URL}/events?lat=${lat}&lng=${lng}&radius_m=2000&limit=100`,
    { headers: authHeaders(data.token), tags: { name: "geo_search" } },
  );
  check(res, { "map 200 during edit": (r) => r.status === 200 });
}

// trigger_edit: fire the single organiser edit and print the markers needed to
// correlate worker delivery logs back to this exact edit.
export function triggerEdit(data) {
  const editAt = new Date();
  updateEvent(data.organiserToken, data.eventId, {
    title: `Rescheduled Event ${editAt.getTime()}`,
  });
  console.log(`[FR7-load] event_id=${data.eventId}`);
  console.log(`[FR7-load] attendees=${ATTENDEES}`);
  console.log(`[FR7-load] edit_at=${editAt.toISOString()}`);
}

export function teardown() {
  console.log(
    "[FR7-load] Map-load thresholds (p99, error rate) are asserted by k6 above.",
  );
  console.log(
    "[FR7-load] Compute push-ack p95/p99 from worker CloudWatch logs vs edit_at - see tests/load/README.md.",
  );
}
