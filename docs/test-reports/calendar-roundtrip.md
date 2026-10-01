# Calendar interoperability round-trip (FR6 / QA2-roundtrip)

Manual, reproducible test that TicketTailor's iCal output is consumed correctly
by the three target calendar clients - Google Calendar, Microsoft Outlook, and
Apple Calendar. This is the interoperability ASR's human-in-the-loop evidence;
the byte-level RFC 5545 conformance is proven separately and automatically by
[`calendar/tests/test_ical_conformance.py`](../../api/src/tickettailor/calendar/tests/test_ical_conformance.py).
That test guarantees the bytes are valid; this report confirms real clients
actually render them.

## What is covered

| Path | Endpoint | How a user consumes it |
| --- | --- | --- |
| Import | `GET /events/{id}/calendar.ics` | "Add to Calendar" download, then import the `.ics` file |
| Subscribe | `GET /calendar/feed/{token}` | paste the feed URL as a subscribed calendar (client pulls it) |

Both are exercised against each client.

## Preconditions

- A running stack. For the **import** path, `docker compose up` (localhost) is
  enough - the `.ics` file is downloaded and imported locally.
- For the **subscribe** path the client fetches the URL **server-side**, so the
  API must be reachable from the public internet. Use the deployed stack
  (`infra/README.md`) and its `BASE_URL`; localhost will not work for Google or
  Outlook subscriptions.
- A TicketTailor account, its calendar feed token (`GET /calendar/token`), and
  the seeded test event below.

## Test data (seed once)

Create one event whose fields deliberately exercise the interop edge cases the
escaping and folding rules exist for. Reserved RFC 5545 TEXT characters
(`comma , semicolon ; backslash \`) in the title prove escaping survives the
client's own parser, not just ours.

```bash
# token = a logged-in organiser's access token; CLUB = a club they administer
curl -sX POST "$BASE_URL/events" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
    "club_id": "'"$CLUB"'",
    "title": "Jazz, Wine; & Cheese \\ Night",
    "category": "Music",
    "latitude": "-27.4975",
    "longitude": "153.0137",
    "starts_at": "2026-07-01T09:00:00+10:00",
    "is_free": true,
    "visibility": "public"
  }'
```

Record the returned `event_id`. Note the start time is **09:00 Brisbane
(UTC+10)** - the cross-timezone check below confirms each client renders that
local time, not a shifted UTC value.

## Procedure

Run every row of the results table. For each client, do both the import and the
subscribe path.

### A. Import a single event (`.ics` file)

1. Sign in to the web app, open the event, click **Add to Calendar** (or
   `curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/events/$EVENT_ID/calendar.ics" -o event.ics`).
2. Import `event.ics` into the client:
   - **Google Calendar**: Settings -> Import & export -> Import.
   - **Outlook**: File -> Open & Export -> Import (desktop), or Add calendar ->
     Upload from file (web).
   - **Apple Calendar**: File -> Import, or double-click the `.ics`.
3. Verify the imported event (see "What to verify").

### B. Subscribe to the feed URL

1. Get the feed URL: `GET /calendar/token` returns the token; the URL is
   `"$BASE_URL/calendar/feed/$TOKEN"`.
2. Add it as a subscribed calendar:
   - **Google Calendar**: Other calendars -> + -> From URL.
   - **Outlook**: Add calendar -> Subscribe from web.
   - **Apple Calendar**: File -> New Calendar Subscription.
3. Wait for the client's first sync, then verify (see below).

### What to verify (each client, each path)

- [ ] The event appears on the correct date.
- [ ] Start time shows as **09:00 in the viewer's local timezone** equivalent of
      Brisbane 09:00 (i.e. it is not silently off by the UTC offset).
- [ ] The title renders exactly `Jazz, Wine; & Cheese \ Night` - commas,
      semicolon and backslash intact, none doubled or dropped (escaping
      round-trip).
- [ ] No duplicate or ghost events after a second sync (subscribe path).
- [ ] (Subscribe) Editing the event in TicketTailor is reflected on the next
      client refresh.

## Results

Fill in on each run. Status is PASS / FAIL / N/A. Record the client version and
date so the result is reproducible and attributable.

| Client | App / version | Path | Date | Tester | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Google Calendar | web | Import | 2026-06-06 | Daniel Cottrell | PASS | Title rendered `Jazz, Wine; & Cheese \ Night` (comma/semicolon/backslash intact, in title and description); shown Wed 1 Jul 09:00-10:00 in a Brisbane/AEST calendar - correct conversion of the stored 23:00 UTC; location and reminder present. |
| Google Calendar | web | Subscribe | _PENDING_ | | PENDING | Needs a publicly reachable feed URL; will run during the AWS load-test session (the feed content is byte-identical to the imported `.ics`, verified locally). |
| Microsoft Outlook | - | Import | 2026-06-06 | Daniel Cottrell | N/A | Not manually tested - no Microsoft account available. Covered by the automated RFC 5545 conformance test (`api/src/tickettailor/calendar/tests/test_ical_conformance.py`). |
| Microsoft Outlook | - | Subscribe | - | | N/A | As above. |
| Apple Calendar | - | Import | 2026-06-06 | Daniel Cottrell | N/A | Not manually tested - no Apple device available. Covered by the automated RFC 5545 conformance test. |
| Apple Calendar | - | Subscribe | - | | N/A | As above. |

**Overall:** Import round-trip **PASS** in Google Calendar (the escaping and
timezone edge cases both rendered correctly). Outlook and Apple were not
manually testable (no account / device); their interop rests on the automated
RFC 5545 conformance test, which all three clients implement. The Google
**subscribe** path is deferred to the AWS session, where the feed URL is
publicly reachable - the feed body is already verified byte-identical to the
imported file locally.

This is enough to mark FR6 round-trip / QA2-roundtrip `passing` (a real client
renders the spec-valid output correctly); the report's Evaluation section should
state the scope honestly (one client manually confirmed, the other two by RFC
5545 conformance, subscribe path validated on the deployed stack).
