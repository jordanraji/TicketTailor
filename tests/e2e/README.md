# End-to-end tests

Browser-driven flows (Playwright). Two specs:

- `specs/happy-path.spec.ts` - **AR3**: signup -> RSVP -> calendar -> push.
- `specs/events-map.spec.ts` - **FR2**: the map renders (OpenStreetMap tiles via
  MapLibre GL JS, ADR-0019) and plots geo-radius results.

## What `happy-path.spec.ts` asserts

1. **Signup** through the UI, redirect to sign-in.
2. **Sign in**, redirect to the events page (bearer token stored client-side).
3. **RSVP** (FR3) on a seeded public event: the attendee counter ticks 0 -> 1
   and the button flips to "Cancel RSVP".
4. **Add to calendar** (FR6): the download is a well-formed `VCALENDAR` /
   `VEVENT`.
5. **Push** (FR7): the headless run asserts the *precondition* - the user is now
   an RSVP'd attendee, i.e. in the notification recipient set. Actual push
   delivery needs a service worker + VAPID + a push service and is out of scope
   for a functional e2e; it is covered by
   [`worker/tests/test_organiser_edit_push.py`](../../worker/tests/test_organiser_edit_push.py)
   (correctness) and
   [`scenarios/organiser_edit.js`](../load/scenarios/organiser_edit.js)
   (push-ack latency SLO).

The organiser, club and public event are seeded directly via the API before the
browser flow, so the test acts purely as a fresh attendee.

## Prerequisites

- **API running** at `API_URL` (default `http://localhost:8000`). From the repo
  root: `docker compose up --build`.
- **Node + Playwright** installed:
  ```bash
  cd tests/e2e
  npm install
  npm run install-browsers   # one-time: downloads the Chromium runtime
  ```

The frontend dev server is started automatically by Playwright's `webServer`
(see `playwright.config.ts`); it injects `NEXT_PUBLIC_API_URL=$API_URL`. If you
are already running `npm run dev` in `web/`, it is reused.

## Run

```bash
cd tests/e2e
npm test                                   # against localhost defaults
API_URL=http://<host>:8000 npm test        # against another API
WEB_URL=http://localhost:3000 npm test     # against an already-running frontend
```

A clean exit = pass. On failure, see `playwright-report/` (HTML) and the
captured trace/screenshot.

## Status

Passing. First green run on 2026-06-05 against the local `docker compose` stack
(API at :8000) with the frontend served by Playwright's `webServer`. The AR3 row
in [`../../docs/traceability.md`](../../docs/traceability.md) is `passing`.

Note: the API's email validator rejects reserved TLDs (`.local`), so test
accounts use `@example.com`.
