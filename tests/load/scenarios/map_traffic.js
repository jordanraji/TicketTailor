// QA1-replica: sustained map (geo-radius) traffic on the read-replica path.
// ASR: map-query p99 <= 500 ms and error rate < 1 % at M = 50 RPS.
//
//   k6 run -e BASE_URL=http://<alb-dns> tests/load/scenarios/map_traffic.js
//
// Tunables: RATE (req/s, default 50), DURATION (default 2m), SEED_EVENTS.

import http from "k6/http";
import { check } from "k6";
import {
  authHeaders,
  registerAndLogin,
  createClub,
  createEvent,
  CENTER,
  jitter,
  BASE_URL,
} from "../lib/helpers.js";

const RATE = Number(__ENV.RATE || 50);
const DURATION = __ENV.DURATION || "2m";
const SEED_EVENTS = Number(__ENV.SEED_EVENTS || 50);
// Client-observed map-query p99 budget (ms). Defaults to the QA1-replica SLO;
// override (GEO_P99_MS) when the harness runs outside the deployment region so
// the trans-region RTT floor does not mask the error-rate (correctness) gate.
const GEO_P99_MS = Number(__ENV.GEO_P99_MS || 500);

export const options = {
  scenarios: {
    map: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.ceil(RATE * 1.5),
      maxVUs: RATE * 4,
    },
  },
  thresholds: {
    // Scope the SLO to the map queries only, so the seed/register/login requests
    // in setup() do not skew the p99 or the error rate.
    "http_req_duration{name:geo_search}": [`p(99)<${GEO_P99_MS}`],
    "http_req_failed{name:geo_search}": ["rate<0.01"],
  },
};

// Seed a pool of public events near CENTER and return a browse token (the geo
// list endpoint requires auth).
export function setup() {
  const organiser = registerAndLogin("map-organiser");
  const clubId = createClub(organiser.token, `Map Club ${Date.now()}`);
  for (let i = 0; i < SEED_EVENTS; i += 1) {
    createEvent(organiser.token, {
      clubId,
      lat: jitter(CENTER.lat, 0.02),
      lng: jitter(CENTER.lng, 0.02),
      visibility: "public",
    });
  }
  const browser = registerAndLogin("map-browser");
  return { token: browser.token };
}

export default function (data) {
  // Jitter the query centre so requests spread across cache keys and hit the
  // replica, not a single hot cache entry.
  const lat = jitter(CENTER.lat, 0.01).toFixed(6);
  const lng = jitter(CENTER.lng, 0.01).toFixed(6);
  const res = http.get(
    `${BASE_URL}/events?lat=${lat}&lng=${lng}&radius_m=2000&limit=100`,
    { headers: authHeaders(data.token), tags: { name: "geo_search" } },
  );
  check(res, { "map 200": (r) => r.status === 200 });
}
