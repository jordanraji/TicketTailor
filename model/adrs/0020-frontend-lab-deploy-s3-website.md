---
status: "accepted"
date: 2026-06-07
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Learner Lab frontend hosting: public S3 static website over HTTP

## Context and Problem Statement

The idealised frontend topology hosts the SPA on a private S3 bucket behind CloudFront with TLS ([ADR-0004](0004-spa-frontend.md), [ADR-0018](0018-frontend-nextjs-static-export.md)), provisioned by the `frontend` module ([ADR-0017](0017-learner-lab-deployment-profile.md)). That path cannot run on the AWS Academy Learner Lab: the `voclabs` role is denied `cloudfront:*`, so `terraform apply` with `enable_frontend = true` fails. As a result the deployed system had no public URL for the SPA at all - only the API was reachable (the ALB HTTP URL) - and the demo had to serve the SPA from a local dev server. We need an actual public URL that markers and users can open, deployable within the lab's permissions before the deadline.

## Decision Drivers

* Demonstrability - the deploy should produce a real public URL serving the working SPA, not a placeholder.
* Learner Lab permissions - `cloudfront:*` is denied; the solution must use only services the `voclabs` role can create.
* No mixed content - the API is HTTP-only over the ALB (no ACM/custom domain on the lab, ADR-0017). A frontend served over HTTPS would have its `fetch()` calls to the HTTP API blocked by the browser, so the frontend must also be HTTP.
* Minimal drift from the idealised architecture - the logical design (static SPA bundle, separate origin, JSON API over CORS) should stay intact so the report's description and evaluation hold.
* Deadline - a working demo beats a perfect one.

## Considered Options

* Public S3 static website hosting over HTTP (no CloudFront)
* Serve the static bundle from the API container behind the existing ALB (same origin)
* Keep the SPA local-only for the demo (no deployed frontend)

## Decision Outcome

Chosen option: **public S3 static website hosting over HTTP**, added as a second, lab-specific frontend module (`modules/frontend_website`, gated by `enable_frontend_website`) that sits alongside the untouched CloudFront `frontend` module. It is the only option that yields a real public URL within the lab's permissions while keeping the SPA a separately-hosted static bundle, exactly as the idealised design intends - it simply drops the CloudFront CDN/TLS layer the lab forbids. We confirmed by probe that the lab permits public buckets, website configuration, and public-read bucket policies (only `cloudfront:*` is denied). Concretely:

1. **Public website bucket.** `modules/frontend_website` creates an S3 bucket with website configuration (`index.html`, with `index.html` as the error document for static-export/SPA routing), a relaxed public-access block, and a public-read (`s3:GetObject`) bucket policy. The bucket is served at `http://<bucket>.s3-website-<region>.amazonaws.com`.
2. **HTTP both ends, no mixed content.** The SPA is HTTP and the API is HTTP, so the browser makes cross-origin `fetch()` calls without a mixed-content block. CORS bridges the two origins.
3. **CORS wired automatically.** When `enable_frontend_website = true`, the root module sets the API's `CORS_ALLOWED_ORIGINS` to the website origin (plus `http://localhost:3000` for dev). `allow_credentials` forbids a wildcard, so the exact origin is used.
4. **Post-apply build + publish.** `next build` bakes `NEXT_PUBLIC_API_URL`, which is the ALB URL known only after apply, so the publish is a post-apply step: `scripts/deploy-web.sh` (`make web`) reads `terraform output api_url`, runs `NEXT_PUBLIC_API_URL=<api_url> npm run build`, and `aws s3 sync web/out` into the bucket.

### Consequences

* Good - a real, public, working SPA URL on the lab, with the SPA still a standalone static bundle on its own origin (no architectural drift in the logical view; this is a deployment substitution in the spirit of ADR-0017's LabRole/ElastiCache substitutions).
* Good - the CloudFront `frontend` module is untouched and remains the full-account upgrade: flipping to it adds HTTPS + CDN with no change to the application or module boundaries.
* Bad - HTTP only: no TLS, so traffic is in clear and the bucket is publicly readable. Acceptable for a capstone demo; the upgrade path to HTTPS is CloudFront (ADR-0017/0018) or S3 behind a TLS-terminating CDN, and to HTTPS on the API an ACM cert + HTTPS ALB listener. This is called out in the report's security critique.
* Bad - two frontend modules now exist (`frontend` for full-account HTTPS, `frontend_website` for lab HTTP). They are mutually exclusive by flag and clearly documented, but it is more surface area.
* Bad - the publish is a manual post-apply step (`make web`) rather than part of `terraform apply`, because the API URL is only known post-apply. Documented in the runbook.

### Confirmation

* `infra/modules/frontend_website/` creates the bucket, website config, and public-read policy; `enable_frontend_website` gates it in `infra/main.tf`; `terraform output frontend_website_url` prints the public URL.
* The API task's `CORS_ALLOWED_ORIGINS` resolves to the website origin (verifiable in the ECS task definition / a browser request from the deployed SPA succeeds without a CORS error).
* `scripts/deploy-web.sh` builds with the deployed `api_url` and syncs `web/out`; opening `frontend_website_url` serves the working SPA.

## Pros and Cons of the Options

### Public S3 static website hosting over HTTP

* Good - real public URL within lab permissions; SPA stays a standalone static bundle on its own origin; HTTP avoids mixed content with the HTTP API; clean upgrade to CloudFront.
* Bad - HTTP only (no TLS, public bucket); manual post-apply publish step; a second frontend module.

### Serve the bundle from the API container (same origin)

* Good - always works (no public bucket, no CORS); single origin.
* Bad - the SPA client route `/events` collides with the API's `GET /events`, forcing the API under an `/api/*` prefix (touching every test and the e2e) or a Next.js `basePath`; couples the SPA into the API deployable, contradicting the three-deployable-units design (ADR-0002). Too invasive for the deadline.

### Local-only for the demo

* Good - zero infra work; `localhost:3000` is already in the API's CORS default.
* Bad - not a public URL; only works on one machine; does not satisfy "a URL people can access and use".

## More Information

The upgrade path to the idealised topology is unchanged: on a full AWS account, set `enable_frontend = true` to provision CloudFront (HTTPS + CDN), add an ACM cert + HTTPS listener to the ALB so the API is HTTPS too, and point `NEXT_PUBLIC_API_URL` / CORS at the HTTPS origins. Related: [ADR-0017](0017-learner-lab-deployment-profile.md), [ADR-0018](0018-frontend-nextjs-static-export.md), [ADR-0004](0004-spa-frontend.md), [ADR-0009](0009-security-tactics.md).
