---
status: "accepted"
date: 2026-05-30
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Email provider: Resend in prod, Mailpit in dev and test

## Context and Problem Statement

The architecture overview and the L1/L2 C4 diagrams originally named Amazon SES as the transactional email provider for FR5 and FR7 notification emails. UQ course policy does not permit SES in the assessment environment, so a different provider must be chosen.

Separately, the load test fans out to N=1,000 users (QA1) and the reliability tests redeliver messages when the worker is killed - neither path should send real emails to fake addresses on every run. The provider decision and the dev/test stub strategy belong in the same ADR because they share the adapter interface.

## Decision Drivers

* SES is not available in the UQ environment (policy).
* The free tier of whatever we pick must comfortably cover the project's actual needs (demo + small manual smoke tests). Anything load-test-related must not hit a real provider.
* The notification worker is an AWS Lambda ([ADR-0002](0002-modular-monolith-with-extracted-worker.md), [ADR-0010](0010-visibility-transition-in-outbox-relay.md)); the integration must work from Python in Lambda.
* Test paths (unit, integration, load, reliability) must assert that an email *would* have been sent without actually sending one.
* No team email-provider account exists yet - setup cost matters.
* 9 days to deadline.

## Considered Options

* **Resend + Mailpit** - Resend for the real provider (3,000/month free, no card), Mailpit as a local SMTP catcher in dev and CI.
* **SendGrid + Mailpit** - same shape but SendGrid as the provider (100/day free forever).
* **Mailgun + Mailpit** - Mailgun's free tier is 5,000/month but only for 3 months from signup, then paid.
* **SMTP via Gmail / Outlook + Mailpit** - no extra account, but heavily rate-limited and prone to breaking on demo day.

## Decision Outcome

Chosen option: **Resend in prod, Mailpit in dev and test**, because Resend's API is the simplest of the three viable providers (a POST with an API key), the free tier comfortably covers a capstone demo with no expiry, and Mailpit removes the question of "what happens when the load test sends 1,000 emails" entirely by catching all SMTP traffic locally.

The notification worker exposes an `EmailProvider` interface with two adapters: `ResendProvider` (prod) and `SmtpProvider` (dev, CI, load tests). The active adapter is selected by the `EMAIL_PROVIDER` environment variable.

### Consequences

* Good - no AWS email-service dependency. The provider can be swapped behind the interface without touching worker business logic.
* Good - load and reliability tests assert "the worker called `send` with this payload" against Mailpit's capture API, with no risk of real-email-blast accidents.
* Good - Resend signup is free and immediate; no credit card required.
* Bad - more env vars than a single SES setup would have used (provider selector + per-provider config).
* Bad - without verifying a domain, Resend in sandbox mode only sends to addresses the team has verified. Acceptable for the demo; documented in [`docs/working-agreement.md`](../../docs/working-agreement.md).

### Confirmation

* `EmailProvider` Python protocol in the worker package, with `ResendProvider` and `SmtpProvider` adapters selected by the `EMAIL_PROVIDER` env var.
* `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `RESEND_API_KEY`, `SMTP_HOST`, `SMTP_PORT` declared in [`api/.env.example`](../../api/.env.example) and read in [`api/src/tickettailor/shared/config.py`](../../api/src/tickettailor/shared/config.py).
* Resend API key stored in AWS Secrets Manager in prod; in GitHub Actions secrets for CI manual tests; in local `.env` (gitignored).
* [`../../docker-compose.yml`](../../docker-compose.yml) adds a `mailpit` service for local dev.
* Worker integration test asserts that `SmtpProvider` captures payloads in Mailpit; a separate manual smoke test exercises `ResendProvider` against a verified inbox.

## Pros and Cons of the Options

### Resend + Mailpit

* Good - simplest API of the candidates; smallest Python integration.
* Good - generous free tier with no expiry, no credit card required.
* Bad - newer company than SendGrid; deliverability track record is shorter (adequate for a capstone demo).

### SendGrid + Mailpit

* Good - most established, large community, broad SDK support.
* Bad - Python SDK is heavier than Resend's; daily-rate-limited free tier (100/day) versus Resend's monthly bucket.

### Mailgun + Mailpit

* Good - high free-tier ceiling.
* Bad - free tier expires after 3 months; risk of having to change provider mid-project or pay.

### SMTP via Gmail / Outlook + Mailpit

* Good - zero new accounts.
* Bad - heavily rate-limited; account-suspension risk on bulk; brittle for the demo.

## More Information

* [ADR-0006](0006-async-fanout-with-outbox.md) - async fan-out shape that calls into the email provider.
* [ADR-0010](0010-visibility-transition-in-outbox-relay.md) - visibility transitions trigger emails through the same path.
* [`../../docs/architecture-overview.md`](../../docs/architecture-overview.md) - FR5/FR7 notification flows.
