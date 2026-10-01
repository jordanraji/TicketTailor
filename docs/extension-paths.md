# Extension paths

Per-module and per-process extraction stories - the answer to the "expandable to a larger system" grading criterion. Fill this in once the module boundaries are real and the load tests have surfaced actual hot spots.

For each module/process below, write: the **trigger** condition that would justify extraction, the **mechanical steps** to extract, **what doesn't change**, and the architectural **ceiling** above which extraction itself becomes insufficient.

## Modules

- `auth` - TBD
- `users` - TBD
- `events` - TBD
- `rsvp` - TBD
- `organisers` - TBD
- `calendar` - TBD

## Processes

- `notifications` worker (already extracted) - TBD
- `outbox_relay` (already extracted; publishes outbox + runs scheduled FR5 visibility transition, see ADR-0010) - TBD
