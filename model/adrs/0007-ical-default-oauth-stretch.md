---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# iCal export by default; OAuth two-way sync as stretch

## Context and Problem Statement

FR6 requires that users can save events to their calendar. The interoperability ASR (QA2) requires event metadata to round-trip correctly into Google Calendar, Outlook, and Apple Calendar. We need an interoperability strategy that satisfies the ASR without consuming the time budget for the higher-weight ASRs (scalability, reliability).

## Decision Drivers

* Interoperability ASR - title, geographic coordinates, start/end timestamps, and description must be parsed accurately by all three target calendars.
* Time budget - the time spent on calendar interop is time not spent on testing the scalability and reliability ASRs.
* Auth surface - OAuth integrations bring third-party consent flows, refresh tokens, and per-vendor setup.
* Standard-vs-vendor - a standards-based answer is generally a stronger interoperability claim than a vendor integration.

## Considered Options

* (a) iCal (RFC 5545) export only - download an `.ics` file or subscribe to a `webcal://` URL.
* (b) OAuth-based two-way sync with Google Calendar (and optionally Outlook) - the system can write events directly into the user's calendar.
* (c) Both - iCal as the default, OAuth as an optional stretch goal.

## Decision Outcome

Chosen option: **(c) iCal by default, OAuth two-way sync as a stretch goal**. The interoperability ASR is satisfied via standards conformance, which is a stronger claim than a single-vendor integration. OAuth two-way sync remains documented as a stretch goal but is not promised.

### Consequences

* Good - RFC 5545 conformance is testable directly: validate the generated feed against an iCal validator, then round-trip through each target calendar in a manual test.
* Good - no OAuth flows, no per-vendor cloud project setup, no refresh-token plumbing.
* Good - the report's interoperability story is "we conform to the standard," which generalises to any future calendar.
* Bad - one-way only: changes in the calendar don't propagate back to TicketTailor.
* Bad - webcal subscription URLs are public; URL must include an unguessable token to act as the auth credential. Documented as a privacy concern in the security ADR.

### Confirmation

* `tests/api/calendar/test_ical_conformance.py` validates output against an RFC 5545 validator.
* Manual round-trip test through Google/Outlook/Apple Calendar documented in `docs/test-reports/calendar-roundtrip.md`.
* Webcal subscription URLs are token-bearing; tokens are revocable.

## Pros and Cons of the Options

### (a) iCal only

* Good - standards-based, testable, no auth surface.
* Bad - one-way only.

### (b) OAuth only

* Good - two-way sync, richer UX.
* Bad - doubles the auth surface; per-vendor setup; refresh-token plumbing.
* Bad - vendor-specific. Doesn't satisfy interoperability with all three target calendars unless we integrate three OAuth providers.

### (c) iCal default, OAuth stretch

* Good - meets the ASR with the minimal-surface answer; OAuth is upside if time permits.
* Bad - OAuth stretch goal must not consume time the headline ASRs need.

## More Information

* RFC 5545: https://datatracker.ietf.org/doc/html/rfc5545
* The OAuth stretch goal, if reached, lives in a follow-up ADR (0010 or later).
