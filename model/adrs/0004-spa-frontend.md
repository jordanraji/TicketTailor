---
status: "superseded by ADR-0018"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
superseded-by: [ADR-0018]
---

# Frontend: SPA over JSON, framework TBD

> **Superseded by [ADR-0018](0018-frontend-nextjs-static-export.md).** The
> framework (React + Vite -> Next.js with static export) and the build tooling
> (`tsc --strict` deferred while the app is JavaScript) have changed. The
> SPA-over-JSON principle, the MapLibre GL JS map choice, and the
> "static bundle behind a CDN" shape below are retained.

## Context and Problem Statement

The frontend must render an interactive, geo-filtered map; submit forms (signup, RSVP, event create); and receive real-time push notifications. It is *not* server-rendered: the API speaks JSON and the frontend is a static bundle delivered from object storage behind a CDN. The team needs a frontend framework, a map library, and a push-receipt strategy.

## Decision Drivers

* Map performance - the scalability ASR includes "sustained map-marker render" under spike load.
* Token cost - the load tests will hit the map heavily; per-render token costs become real money.
* Type safety - the API surface is OpenAPI-typed (ADR-0003); the frontend should reuse those types.
* Team familiarity.
* Push notification support - service workers, web push.
* Build tooling - Vite or equivalent; fast dev loop.

## Considered Options

* React 18 + Vite + TypeScript + Tailwind, MapLibre GL JS for the map.
* Vue 3 + Vite + TypeScript, Leaflet for the map.
* SvelteKit + TypeScript, MapLibre GL JS or Leaflet.

## Decision Outcome

Chosen option: **React + Vite + TypeScript + Tailwind, with MapLibre GL JS**, because React is the most common starting point for a student team, Vite gives a fast dev loop, MapLibre is open source with no per-render token cost (unlike Mapbox), and TanStack Query + Zod cover server state and runtime API-response validation. Leaflet was considered for its lighter footprint, but MapLibre's vector tiles and smoother panning matter more for the QA1 spike-load map scenario.

### Consequences

* Good - JSON-only API contract is independent of frontend framework; if the team switches frameworks later, the API is unchanged.
* Good - MapLibre rules out per-render token costs that would punish load tests.
* Good - TanStack Query + Zod cover the server-state and runtime-validation needs identified in [`../../docs/conventions.md`](../../docs/conventions.md).
* Bad - push notification reliability varies by browser; mitigated by the strategy chosen in [ADR-0011](0011-web-push-via-vapid.md).

### Confirmation

* Frontend lives under [`../../web/`](../../web/), built to a static bundle.
* No server-side rendering paths in the API.
* Map library version pinned in `package.json`.
* `tsc --strict` in CI.

## Pros and Cons of the Options

### React + Vite + TypeScript

* Good - broadest team familiarity.
* Good - large ecosystem (TanStack Query, Zod, Playwright, Storybook).
* Bad - runtime overhead is higher than Svelte; matters less for our scale.

### Vue + Vite + TypeScript

* Good - gentle learning curve.
* Bad - smaller ecosystem in this project's specific niche (typed API clients, runtime validation).

### SvelteKit

* Good - minimal runtime, fast.
* Bad - less common; ramp-up cost; smaller ecosystem.

### Map library: MapLibre GL JS vs. Leaflet

* MapLibre - vector tiles, smoother panning, more modern stack. Heavier dependency.
* Leaflet - battle-tested, lighter, raster-tile by default. Less smooth at high zoom levels with many markers.
* Both are open source and free of per-render token costs (unlike Mapbox). Either is acceptable; pick by team experience.

## More Information

* [`../../docs/architecture-overview.md`](../../docs/architecture-overview.md) - the SPA + JSON-API shape.
* [ADR-0011](0011-web-push-via-vapid.md) - web push delivery strategy and the FR7 SLO definition.
