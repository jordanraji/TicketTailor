// QA1-scale: sustained RSVP toggle load on the atomic-counter path.
// ASR: RSVP p99 <= 200 ms and error rate < 1 % at M = 50 RPS.
//
//   k6 run -e BASE_URL=http://<alb-dns> tests/load/scenarios/sustained_rsvp.js
//
// Tunables: RATE (default 50), DURATION (default 2m), USER_POOL (default 200).
// Each iteration uses a distinct pre-registered user and alternates
// place / cancel so both INCR and DECR are exercised.

import http from "k6/http";
import { check } from "k6";
import {
  authHeaders,
  registerAndLogin,
  createClub,
  createEvent,
  CENTER,
  BASE_URL,
} from "../lib/helpers.js";

const RATE = Number(__ENV.RATE || 50);
const DURATION = __ENV.DURATION || "2m";
// One user per VU so each VU toggles its own RSVP in order (no cross-VU
// contention, no cancel-before-place). Must be >= maxVUs (RATE * 4 below).
const USER_POOL = Number(__ENV.USER_POOL || RATE * 4);
// Client-observed RSVP-toggle p99 budget (ms). Defaults to the QA1-scale SLO;
// override (RSVP_P99_MS) when the harness runs outside the deployment region so
// the trans-region RTT floor does not mask the error-rate (correctness) gate.
const RSVP_P99_MS = Number(__ENV.RSVP_P99_MS || 200);
// Bounds the seeding phase (registers USER_POOL users). The default suits an
// in-region harness; raise SETUP_TIMEOUT when seeding over a high-RTT link.
const SETUP_TIMEOUT = __ENV.SETUP_TIMEOUT || "5m";

export const options = {
  setupTimeout: SETUP_TIMEOUT,
  scenarios: {
    rsvp: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.ceil(RATE * 1.5),
      maxVUs: RATE * 4,
    },
  },
  thresholds: {
    // Scope the SLO to the RSVP toggles, so setup register/login requests (which
    // may retry through the read-your-writes window) do not skew the error rate.
    "http_req_duration{name:rsvp_toggle}": [`p(99)<${RSVP_P99_MS}`],
    "http_req_failed{name:rsvp_toggle}": ["rate<0.01"],
  },
};

// Create one public event and a pool of users that will RSVP to it.
export function setup() {
  const organiser = registerAndLogin("rsvp-organiser");
  const clubId = createClub(organiser.token, `RSVP Club ${Date.now()}`);
  const eventId = createEvent(organiser.token, {
    clubId,
    lat: CENTER.lat,
    lng: CENTER.lng,
    visibility: "public",
  });

  const tokens = [];
  for (let i = 0; i < USER_POOL; i += 1) {
    tokens.push(registerAndLogin(`rsvp-user-${i}`).token);
  }
  return { eventId, tokens };
}

export default function (data) {
  // Each VU owns one user and toggles it in iteration order, so place/cancel
  // always alternate validly: even iterations place (201), odd iterations cancel
  // (200). No cancel-before-place 404 and no duplicate 409, so the error rate
  // reflects real failures only. One request per iteration keeps the arrival
  // rate equal to the RSVP op rate the SLO is stated in (M = 50 RPS).
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const url = `${BASE_URL}/events/${data.eventId}/rsvp`;
  const params = { headers: authHeaders(token), tags: { name: "rsvp_toggle" } };

  const res =
    __ITER % 2 === 0
      ? http.post(url, null, params)
      : http.del(url, null, params);
  check(res, { "rsvp ok (200/201)": (r) => r.status === 200 || r.status === 201 });
}
