# QA1 load tests (k6)

Load tests for the scalability ASR (QA1). They target a **deployed AWS stack**
via the `BASE_URL` env var; the scripts run against any reachable URL, but the
numbers are only meaningful against the deployed stack (autoscaling, read
replica, SNS -> SQS -> Lambda fan-out). Running against local docker-compose is
useful only to smoke-test the script logic before spending an AWS deploy.

## Scenarios and thresholds

| Script | Traceability | ASR thresholds (asserted by k6 unless noted) |
| --- | --- | --- |
| `scenarios/map_traffic.js` | QA1-replica | map-query p99 <= 500 ms, errors < 1 % @ 50 RPS |
| `scenarios/sustained_rsvp.js` | QA1-scale | RSVP p99 <= 200 ms, errors < 1 % @ 50 RPS |
| `scenarios/visibility_spike.js` | QA1-load | concurrent map p99 <= 500 ms + errors < 1 % (k6); **fan-out ack p95 <= 30 s / p99 <= 60 s measured from worker logs, not k6** |
| `scenarios/organiser_edit.js` | FR7 | concurrent map p99 <= 500 ms + errors < 1 % (k6); **push ack p95 <= 5 s / p99 <= 10 s measured from worker logs, not k6** |

k6 exits non-zero if any threshold is breached, so a clean exit = pass for the
HTTP-measurable rows.

## Prerequisites

- Install k6: https://grafana.com/docs/k6/latest/set-up/install-k6/
- Deploy the stack (see [`../../infra/README.md`](../../infra/README.md)). The
  worker Lambda validates its image at creation time, so the ECR repos and
  images must exist BEFORE the full apply - create the repos first, push images,
  then apply everything else (a bare `make apply` first would fail on the
  worker Lambda):
  ```bash
  cd infra
  make init ENV=dev          # first time only
  make repos ENV=dev         # create ONLY the ECR repos
  make images TAG=latest     # build + push api/relay/worker into them
  make apply ENV=dev         # create everything else
  # api_url already includes the http:// scheme.
  export BASE_URL="$(terraform output -raw api_url)"
  ```

## Run all three in one stack session (cost discipline)

The stack bills while it exists, so apply once, run everything, destroy once
(ADR-0017).

```bash
# fast HTTP-measurable rows first
k6 run -e BASE_URL="$BASE_URL" tests/load/scenarios/map_traffic.js
k6 run -e BASE_URL="$BASE_URL" tests/load/scenarios/sustained_rsvp.js

# the spike: note the flip_at / event_id it prints, then measure fan-out below
k6 run -e BASE_URL="$BASE_URL" tests/load/scenarios/visibility_spike.js

# the FR7 edit fan-out: note the edit_at / event_id it prints, measure as below
k6 run -e BASE_URL="$BASE_URL" tests/load/scenarios/organiser_edit.js
```

Tunables (env vars): `RATE` (req/s, default 50), `DURATION` (default `2m`),
`USER_POOL` (sustained_rsvp, default 200), `FOLLOWERS` (visibility_spike,
default 1000), `ATTENDEES` (organiser_edit, default 1000), `WARMUP_S`
(visibility_spike + organiser_edit, default 45).

Smoke-test the logic locally first (cheap, validates payloads only):
```bash
k6 run -e BASE_URL=http://localhost:8000 -e FOLLOWERS=20 -e DURATION=20s \
  tests/load/scenarios/visibility_spike.js
```

## Measuring the fan-out latency (QA1-load)

k6 cannot time the async fan-out (relay -> SNS -> SQS -> Lambda). `visibility_spike.js`
prints `event_id`, `followers`, and `flip_at`. Compute the fan-out spread from
the worker's CloudWatch logs.

> **Prerequisite (already in place):** the worker emits one ack line per
> delivery containing the event id - `Notification ack: event_id=<id> msg_id=...
> type=...` (worker/src/worker/lambda_handler.py). That is the line the query
> below filters on.

```bash
WORKER_FN=$(cd infra && terraform output -raw worker_function)
# Log group for a container-image Lambda: /aws/lambda/<function-name>
```

CloudWatch Logs Insights query (set `<EVENT_ID>` from the run):
```
filter @message like /<EVENT_ID>/
| stats count() as delivered,
        pct(@timestamp, 95) as p95_ms,
        pct(@timestamp, 99) as p99_ms,
        max(@timestamp)     as last_ms
```
Then, with `flip_ms = Date.parse(flip_at)`:
- fan-out p95 (s) = `(p95_ms - flip_ms) / 1000`  -> assert <= 30
- fan-out p99 (s) = `(p99_ms - flip_ms) / 1000`  -> assert <= 60
- `delivered` should equal `followers` (no lost messages -> ties to QA3).

The FR7 `organiser_edit.js` scenario is measured the same way: it prints
`event_id` and `edit_at` instead of `flip_at`, and the SLO is tighter -
push-ack p95 <= 5 s, p99 <= 10 s (`delivered` should equal `attendees`).

## Record results

Put the measured numbers (k6 summary + fan-out) into a short report under
`docs/test-reports/` and flip the QA1-* rows in
[`../../docs/traceability.md`](../../docs/traceability.md) from `planned` to
`passing`.

## Teardown (every run)

```bash
cd infra && make destroy ENV=dev
```
