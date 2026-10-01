---
status: "accepted"
date: 2026-06-06
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Map tile source: OpenStreetMap raster tiles

## Context and Problem Statement

FR2 is an interactive, geo-filtered map. The map library is settled - MapLibre GL JS ([ADR-0004](0004-spa-frontend.md), retained by [ADR-0018](0018-frontend-nextjs-static-export.md)) - but MapLibre renders nothing without a *style/tile source*, which ADR-0004 left open. The source is a new runtime dependency the browser loads directly, so it is architecturally significant: it adds an external system to the C4 system context and interacts with the security posture of a public static bundle ([ADR-0009](0009-security-tactics.md)).

## Decision Drivers

* Deadline - the map is the last large functional gap; a working demo beats a perfect one.
* No secrets in the static bundle - the frontend is a public S3/CloudFront export (ADR-0017/0018); any tile API key ships in clear.
* Cost - tiles must not introduce a metered per-render bill. (Note: the k6 QA1 load tests hit the *API* geo-search, not the tile provider, so tile cost is not exercised under load - only by real browsers.)
* Faithfulness to the existing decision - ADR-0004 favoured vector tiles for smoother panning.

## Considered Options

* OpenStreetMap raster tiles (keyless)
* MapTiler vector tiles (free tier, public API key)
* Self-hosted Protomaps `.pmtiles` (keyless vector, static asset)

## Decision Outcome

Chosen option: **OpenStreetMap raster tiles**, because it is the only option that needs no account and no API key while giving real street-level detail - the fastest path to a demonstrable FR2 that keeps the public bundle secret-free.

### Consequences

* Good - zero setup and no key to leak from the static export; works in dev, CI, and the deployed bundle identically.
* Good - no metered per-render cost; the OSM standard tile layer is free under its usage policy.
* Bad - raster, not vector, so panning/zoom is slightly less smooth than ADR-0004's vector preference, and there is no client-side restyling. Acceptable for the MVP map.
* Bad - depends on the OSM community tile servers, whose [usage policy](https://operations.osmfoundation.org/policies/tiles/) is fine for a low-volume capstone demo but not for production scale. If TicketTailor grew, we would move to a hosted vector provider or self-hosted Protomaps - the MapLibre style is the only thing that changes.

### Confirmation

* `web/package.json` pins `maplibre-gl`; the map style declares the OSM raster source with the required attribution.
* OpenStreetMap appears as an external system in the C4 L1/L2 diagrams and the "External systems" list in [`../../docs/architecture-overview.md`](../../docs/architecture-overview.md).
* No tile API key in `web/` (nothing to find in code review of the static bundle).

## Pros and Cons of the Options

### OpenStreetMap raster (keyless)

* Good - no account, no key, immediate; real detail; free.
* Bad - raster only; bound by the OSM tile usage policy; community-hosted availability.

### MapTiler vector (free tier)

* Good - vector tiles, matches ADR-0004's smoothness rationale.
* Bad - requires an account and a public API key embedded in the static export; free tier is request-capped.

### Self-hosted Protomaps `.pmtiles`

* Good - keyless vector, served as a static asset beside the frontend (no new external system), no third-party runtime dependency.
* Bad - most setup: generate and host a Brisbane tile extract; larger asset. Out of scope for the deadline.

## More Information

Revisit if the map moves beyond a demo (production traffic, offline restyling, or branded basemap) - the swap target is MapTiler or self-hosted Protomaps, changing only the MapLibre style URL. Related: [ADR-0004](0004-spa-frontend.md), [ADR-0018](0018-frontend-nextjs-static-export.md), [ADR-0009](0009-security-tactics.md).
