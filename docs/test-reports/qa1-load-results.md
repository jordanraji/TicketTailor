# QA1 load-test results (scalability) + FR7 push-ack

Records the QA1 scalability run and the FR7 push-ack run against the **deployed
AWS stack**. The k6 scripts live in [`../../tests/load/`](../../tests/load/); the
runbook (deploy, run order, CloudWatch measurement, teardown) is
[`tests/load/README.md`](../../tests/load/README.md). Fill this in during the run
and then flip the matching rows in [`../traceability.md`](../traceability.md)
from `planned` to `passing`.

All four scripts were smoke-tested green against the local stack on 2026-06-06;
the numbers below must come from the **deployed** stack to be meaningful
(autoscaling, read replica, SNS -> SQS -> Lambda fan-out).

## Run metadata

| Field | Value |
| --- | --- |
| Date | _PENDING_ |
| Git commit | _PENDING_ |
| `BASE_URL` | _PENDING_ |
| API task size / desired / max count | _PENDING_ |
| RDS instance class (primary / replica) | _PENDING_ |
| Redis node type | _PENDING_ |
| Worker memory / batch size | _PENDING_ |
| k6 version | _PENDING_ |

## HTTP-measured SLOs (asserted by k6)

k6 exits non-zero if a threshold is breached, so a clean exit is the PASS. Paste
the relevant lines from the k6 summary.

| Scenario | Traceability | SLO | Measured p99 | Measured error rate | Verdict |
| --- | --- | --- | --- | --- | --- |
| `map_traffic.js` | QA1-replica | map p99 <= 500 ms, err < 1 % @ 50 RPS | _PENDING_ | _PENDING_ | _PENDING_ |
| `sustained_rsvp.js` | QA1-scale | RSVP p99 <= 200 ms, err < 1 % @ 50 RPS | _PENDING_ | _PENDING_ | _PENDING_ |
| `visibility_spike.js` | QA1-load | concurrent map p99 <= 500 ms, err < 1 % | _PENDING_ | _PENDING_ | _PENDING_ |
| `organiser_edit.js` | FR7 | concurrent map p99 <= 500 ms, err < 1 % | _PENDING_ | _PENDING_ | _PENDING_ |

## Async fan-out SLOs (measured from worker CloudWatch logs)

k6 cannot time the relay -> SNS -> SQS -> Lambda fan-out. Each spike script prints
`event_id` and a `flip_at` / `edit_at`; run the Logs Insights query in the
runbook over the worker log group filtered to that `event_id` (the worker emits
one `Notification ack: event_id=<id> ...` line per delivery).

| Scenario | Traceability | SLO | N (followers/attendees) | delivered | fan-out p95 (s) | fan-out p99 (s) | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `visibility_spike.js` | QA1-load | p95 <= 30 s, p99 <= 60 s; delivered == N | _PENDING_ | _PENDING_ | _PENDING_ | _PENDING_ | _PENDING_ |
| `organiser_edit.js` | FR7 | p95 <= 5 s, p99 <= 10 s; delivered == N | _PENDING_ | _PENDING_ | _PENDING_ | _PENDING_ | _PENDING_ |

`delivered == N` ties the fan-out back to QA3 (no lost messages).

## Raw k6 summaries

Paste the full `k6 run` summary blocks here for the record (one per scenario).

```
PENDING
```

## Teardown

- [ ] `cd infra && make destroy ENV=dev` run, stack confirmed gone (no lingering
      ECS service, RDS instance, or NAT gateway billing).

## Overall

**PENDING** - not yet run against deployed infra. When every verdict is PASS,
flip QA1-load / QA1-scale / QA1-replica and FR7 in
[`../traceability.md`](../traceability.md) to `passing` and cite this report
(with the run date) in the report's Evaluation section. A breached SLO is
evidence to record and discuss, not to hide (matrix rule).
