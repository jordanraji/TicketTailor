---
status: "accepted"
date: 2026-06-05
decision-makers: [TicketTailor team]
consulted: []
informed: []
supersedes: [ADR-0004]
---

# Frontend framework: Next.js with static export (supersedes ADR-0004)

## Context and Problem Statement

[ADR-0004](0004-spa-frontend.md) chose **React 18 + Vite + TypeScript** for the SPA. During implementation the frontend was prototyped in **Next.js (App Router)** instead, for its file-based routing, layouts, and built-in Tailwind setup. The team has decided to adopt Next.js. This ADR records that decision and, crucially, reconciles it with two things ADR-0004 and the rest of the architecture already fix: the JSON-only API contract and **static hosting on S3 + CloudFront** (ADR-0017). It does not change the SPA-over-JSON shape or the map-library choice; it changes the framework and the build tooling.

## Decision Drivers

* Keep the deployment model intact - the frontend is a static bundle behind a CDN (ADR-0004, ADR-0017). Whatever framework we pick must still produce static assets.
* Preserve the JSON-only API contract - no server-side rendering coupling to the API.
* Team velocity - a working Next.js prototype already exists; the deadline is 8 June 2026.
* The map (FR2) still needs MapLibre GL JS - unchanged from ADR-0004.

## Considered Options

* (a) Stay on React 18 + Vite per ADR-0004 - discard the prototype.
* (b) Next.js with a Node server (SSR) - run `next start` on ECS Fargate or Amplify.
* (c) **Next.js with static export** (`output: 'export'`) - keep static S3 + CloudFront hosting, reuse the prototype.

## Decision Outcome

Chosen option: **(c) Next.js with static export**, because it adopts the prototype the team already built while preserving the static-hosting deployment and the JSON-API contract that the rest of the architecture depends on. Concretely:

1. **Static export.** `next.config` sets `output: 'export'`; `next build` emits static HTML/JS (`web/out`) targeting the existing S3 + CloudFront frontend module (ADR-0017); no new module or deployable unit is introduced. This is sound because the app is entirely client components with no server-only features (no route handlers, server actions, or `getServerSideProps`). On the Learner Lab the publish step is wired via [ADR-0020](0020-frontend-lab-deploy-s3-website.md): `scripts/deploy-web.sh` builds with the deployed API URL and syncs `web/out` to a public S3 website bucket over HTTP (CloudFront is denied to voclabs). The CloudFront path (private bucket + invalidation) remains the full-account upgrade.
2. **Dynamic detail routes become query-param pages.** Static export cannot pre-render dynamic segments whose ids are only known at runtime, so the prototype's `clubs/[id]` and `events/[id]` routes are reworked into client pages keyed off a query string (e.g. `/clubs/detail?id=...`) that fetch on the client. This keeps the export buildable without `generateStaticParams` over runtime data.
3. **Language: JavaScript now, TypeScript deferred.** The prototype is JavaScript. We port it as-is to hit the deadline; this is a recorded deviation from ADR-0004's TypeScript + `tsc --strict`. A TypeScript migration is a tracked follow-up, not abandoned.
4. **Map unchanged.** MapLibre GL JS remains the map library for FR2 (ADR-0004); it is still to be added.
5. **Directory.** The app lives under `web/`, as ADR-0004's Confirmation already required.
6. **Auth token storage is not endorsed here.** The prototype stores the access token in `localStorage`, which contradicts ADR-0009 (in-memory access token, `httpOnly` refresh cookie). That remains the target; the `localStorage` approach is carried over only to get the SPA working and is a tracked QA4 follow-up.

### Consequences

* Good - reuses the existing prototype; keeps static S3 + CloudFront hosting and the JSON-API contract; adds no new deployable unit; ADR-0017 is unaffected.
* Good - Next.js App Router gives file-based routing and layouts with less boilerplate than hand-rolled React Router on Vite.
* Resolved (lab) - the publish step and prod `NEXT_PUBLIC_API_URL` build are wired for the Learner Lab via ADR-0020 (`scripts/deploy-web.sh` -> public S3 website over HTTP). Still open for a full-account CloudFront deploy: it additionally requires HTTPS on the API - an ACM cert + HTTPS ALB listener, or the API behind CloudFront, since the ALB is HTTP-only today (ADR-0017) - and the CloudFront origin added to `CORS_ALLOWED_ORIGINS`, or the HTTPS SPA breaks on mixed content / CORS.
* Bad - static export forbids SSR, server components, and server actions, and requires the query-param detail-page pattern. If the app ever needs SSR, this decision must be revisited (option b).
* Bad - JavaScript now means losing `tsc --strict` safety until the TypeScript migration lands; the convention deviation is recorded.
* Bad - the prototype runs React 19 / Next 16, newer than the React 18 named in ADR-0004; acceptable, but pin versions in `package.json`.

### Confirmation

* `next build` with `output: 'export'` produces a static bundle deployable to S3 + CloudFront.
* No server-only Next.js features exist in `web/` (grep for route handlers / server actions in review).
* The frontend lives under `web/`; the map is delivered via MapLibre GL JS (FR2 follow-up).
* CI builds the `web/` bundle.

## Pros and Cons of the Options

### (a) React 18 + Vite (ADR-0004 unchanged)

* Good - matches the accepted ADR and conventions (TypeScript, `tsc --strict`); no deviation to document.
* Bad - discards a working prototype and the team's chosen direction. Rejected.

### (b) Next.js with a Node server (SSR)

* Good - unlocks SSR, server components, and server actions.
* Bad - introduces a new deployable unit and rewrites the S3 + CloudFront frontend module; more infra and operational load for no MVP benefit. Rejected.

### (c) Next.js with static export

* Good - keeps static hosting and the JSON-API contract intact while adopting Next.js.
* Bad - the static-export constraints (no SSR; query-param detail pages) must be respected.

## More Information

Supersedes [ADR-0004](0004-spa-frontend.md): the framework (React + Vite -> Next.js) and build tooling (`tsc --strict` deferred) change; ADR-0004's SPA-over-JSON principle, the MapLibre map choice, and the "static bundle behind a CDN" shape are retained. Related: [ADR-0009](0009-security-tactics.md) (token storage target), [ADR-0011](0011-web-push-via-vapid.md) (web push), [ADR-0017](0017-learner-lab-deployment-profile.md) (S3 + CloudFront hosting).
