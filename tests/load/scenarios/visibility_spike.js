// QA1-load: the headline spike. A club-only event with N=1,000 followers flips
// to public; the relay fans out one notification per follower via SNS -> SQS ->
// Lambda worker, while the platform serves concurrent map traffic.
//
// ASR: fan-out ack at the worker p95 <= 30 s, p99 <= 60 s; concurrent map-query
// p99 <= 500 ms; error rate < 1 %.
//
//   k6 run -e BASE_URL=http://<alb-dns> tests/load/scenarios/visibility_spike.js
//
// IMPORTANT measurement boundary: fan-out ack latency is an ASYNCHRONOUS
// pipeline that terminates at the worker, NOT an HTTP response k6 can time. So
// k6 owns only:
//   1. seeding the N followers and the scheduled flip, and
//   2. generating + asserting the concurrent map load (p99, error rate).
// The fan-out p95/p99 is computed from worker CloudWatch logs against the flip
// timestamp this script prints. The Logs Insights query is in
// tests/load/README.md.
//
// Tunables: FOLLOWERS (default 1000), RATE (map req/s, default 50),
// DURATION (default 2m), WARMUP_S (seconds after setup before the flip fires).

import http from "k6/http";
import { check } from "k6";
import {
  authHeaders,
  registerAndLogin,
  createClub,
  createEvent,
  followClub,
  CENTER,
  jitter,
  BASE_URL,
} from "../lib/helpers.js";

const FOLLOWERS = Number(__ENV.FOLLOWERS || 1000);
const RATE = Number(__ENV.RATE || 50);
const DURATION = __ENV.DURATION || "2m";
const WARMUP_S = Number(__ENV.WARMUP_S || 45);
// Concurrent map-query p99 budget (ms); defaults to the QA1 SLO, overridable
// (GEO_P99_MS) for an out-of-region harness. SETUP_TIMEOUT bounds the seeding
// phase (raise it when seeding many followers over a high-RTT link).
const GEO_P99_MS = Number(__ENV.GEO_P99_MS || 500);
const SETUP_TIMEOUT = __ENV.SETUP_TIMEOUT || "20m";

export const options = {
  setupTimeout: SETUP_TIMEOUT, // seeding followers is sequential; give it room.
  scenarios: {
    background_browse: {
      executor: "constant-arrival-rate",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.ceil(RATE * 1.5),
      maxVUs: RATE * 4,
    },
  },
  thresholds: {
    // Scope the SLO to the concurrent map queries, so seeding the followers in
    // setup() (and any login retries) does not skew the p99 or the error rate.
    "http_req_duration{name:geo_search}": [`p(99)<${GEO_P99_MS}`],
    "http_req_failed{name:geo_search}": ["rate<0.01"],
  },
};

export function setup() {
  const organiser = registerAndLogin("spike-organiser");
  const clubId = createClub(organiser.token, `Spike Club ${Date.now()}`);

  // Seed N followers of the club. Sequential and the slow part of setup; tune
  // FOLLOWERS down for a smaller smoke run.
  for (let i = 0; i < FOLLOWERS; i += 1) {
    const follower = registerAndLogin(`spike-follower-${i}`);
    followClub(follower.token, clubId);
  }

  // Schedule the flip for WARMUP_S from now so it lands mid-test, once the
  // background map load has ramped.
  const flipAt = new Date(Date.now() + WARMUP_S * 1000);
  const eventId = createEvent(organiser.token, {
    clubId,
    lat: CENTER.lat,
    lng: CENTER.lng,
    visibility: "club_only",
    transitionAtIso: flipAt.toISOString(),
  });

  const browser = registerAndLogin("spike-browser");

  // Printed for CloudWatch correlation - copy these into the Logs Insights
  // query in the runbook to compute fan-out p95/p99.
  console.log(`[QA1-load] event_id=${eventId}`);
  console.log(`[QA1-load] followers=${FOLLOWERS}`);
  console.log(`[QA1-load] flip_at=${flipAt.toISOString()}`);

  return { token: browser.token };
}

export default function (data) {
  const lat = jitter(CENTER.lat, 0.01).toFixed(6);
  const lng = jitter(CENTER.lng, 0.01).toFixed(6);
  const res = http.get(
    `${BASE_URL}/events?lat=${lat}&lng=${lng}&radius_m=2000&limit=100`,
    { headers: authHeaders(data.token), tags: { name: "geo_search" } },
  );
  check(res, { "map 200 during spike": (r) => r.status === 200 });
}

export function teardown(data) {
  console.log(
    "[QA1-load] Map-load thresholds (p99, error rate) are asserted by k6 above.",
  );
  console.log(
    "[QA1-load] Compute fan-out p95/p99 from worker CloudWatch logs vs flip_at - see tests/load/README.md.",
  );
}
