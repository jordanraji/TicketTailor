---
status: "accepted"
date: 2026-06-04
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Learner Lab deployment profile

## Context and Problem Statement

The deployment target named throughout [`docs/architecture-overview.md`](../../docs/architecture-overview.md) (ECS Fargate for API and relay, Lambda for the worker, RDS primary + read replica, **ElastiCache** for the counter, SNS→SQS, S3 + CloudFront, ALB) assumes a full AWS account. The course deploys into **AWS Academy Learner Lab**, a sandbox with hard constraints that the idealised topology violates: no IAM role/policy creation, sessions are short-lived (~4 h) with rotating credentials, and there is no Route 53 hosted zone for custom domains. (ElastiCache was initially assumed unavailable too, but a probe in this account proved otherwise - see substitution (1).) This ADR decides **how the accepted architecture is realised within those constraints** so the Terraform under [`../../infra/`](../../infra/) is buildable and the deployed system still demonstrates every quality attribute. It does not change any application-level decision (ADR-0002/0005/0006/0008/0010/0016); it records the deployment-environment substitutions.

## Decision Drivers

* Learner Lab constraints - `LabRole` is the only assumable IAM role; custom IAM and custom domains are unavailable. (ElastiCache was assumed unavailable but a probe confirmed it provisions - see substitution (1).)
* Scalability ASR (QA1) - the deployed target must still run the N=1,000 fan-out / M=50 RPS load test against a real primary + read replica + counter + queue.
* Reliability ASR (QA3) - the primary-failover reliability test needs a real RDS primary + replica to exercise.
* Fidelity to the accepted architecture - substitutions must preserve each tactic (independent counter store, extracted worker, async fan-out, read replica), not drop it.
* Cost and teardown - every run must be destroyable (`terraform destroy`); no resource that survives a torn-down stack.

## Considered Options

* (a) Deploy the idealised topology unchanged - assumes ElastiCache and custom IAM.
* (b) Abandon AWS; demonstrate the topology only via `docker-compose`.
* (c) **Learner Lab profile** - map each accepted tactic onto a Learner-Lab-provisionable resource, substituting only where the sandbox forbids the first choice.

## Decision Outcome

Chosen option: **(c) Learner Lab profile**, because it is the only option that both runs on the marked environment and keeps every quality-attribute tactic observable in a real deployment. The substitutions:

1. **Counter store: ElastiCache (managed) - Fargate-Redis substitution withdrawn.** The idealised topology's ElastiCache was initially assumed unavailable in the lab. A throwaway Terraform probe (a single `cache.t3.micro` cluster, applied then destroyed on 2026-06-05) confirmed the `voclabs` role *can* create ElastiCache, so the counter uses the managed service exactly as ADR-0005 and [`docs/architecture-overview.md`](../../docs/architecture-overview.md) specify - a single-node, cluster-mode-disabled Redis cluster reached at its node endpoint, with no internal NLB or Cloud Map workaround. This withdraws the earlier "Redis on Fargate behind an internal NLB" substitution entirely. Trade-off: a single node has no automatic failover - acceptable because the counter is reconstructable from the persisted RSVP rows (ADR-0008 reconciliation, QA3-reconcile), and a replication group with Multi-AZ failover is the documented HA upgrade path (ADR-0005).
2. **IAM: per-service roles → `LabRole`.** Every ECS task role, task execution role, and Lambda execution role references the pre-provisioned `LabRole` ARN (looked up via a data source). No least-privilege custom policies - a documented limitation of the sandbox, not of the design. Note the *deploying* principal is the `voclabs` assumed role, which is more restricted than the classic Learner Lab `LabRole`: in addition to forbidding IAM creation it denies `cloudfront:*` (see substitution 4). It also denies `servicediscovery:*`, but with the counter now on managed ElastiCache (substitution 1, withdrawn) nothing in the design needs Cloud Map.
3. **Networking.** A purpose-built VPC with public + private subnets across two AZs; a single NAT Gateway gives private-subnet Fargate tasks and the Lambda worker outbound reach to the web-push and email providers. Torn down with the stack.
4. **Frontend: CloudFront deferred; S3 website on the lab.** The `voclabs` role is denied `cloudfront:*`, so the CloudFront frontend module (S3 + CloudFront + OAC) is gated behind `enable_frontend` (default **off**) and reserved for a full account. On the lab the SPA (`web/`, Next.js static export, ADR-0018) is instead served from a public S3 static **website** bucket over HTTP, decided in [ADR-0020](0020-frontend-lab-deploy-s3-website.md) and gated behind `enable_frontend_website`; `scripts/deploy-web.sh` builds and publishes `web/out`. A future full-account frontend also needs HTTPS on the API - an ACM cert + HTTPS ALB listener, or the API behind CloudFront, since the ALB is HTTP-only (substitution 5) - and the CloudFront origin added to `CORS_ALLOWED_ORIGINS`, or the HTTPS SPA breaks on mixed content / CORS.
5. **TLS / domain: ACM + Route 53 → default endpoints.** The ALB DNS name is used directly over HTTP; no custom domain or ACM certificate.
6. **Secrets: SSM Parameter Store (SecureString).** `SECRET_KEY`, the VAPID public key, and `RESEND_API_KEY` are stored as SSM SecureString parameters and injected into the ECS tasks; the Lambda worker receives its push/email secrets as environment variables (no native SSM injection for Lambda).
7. **RDS engine pin.** The Postgres engine is pinned to **major version `16`** (not a specific minor) so RDS selects the latest available minor - a pinned minor (e.g. `16.4`) can be retired in-region and fail creation.
8. **Lambda image format.** The worker image must be a Docker v2 schema-2 manifest, not an OCI image index; the build uses `docker buildx --provenance=false` because Lambda rejects the attestation-bearing OCI manifest buildx emits by default.
9. **Region.** Learner Lab pins compute to a single region; `aws_region` is a Terraform variable (the app default is `ap-southeast-2`, but the lab here grants `us-east-1` - confirm per session). Everything else is region-agnostic.

Unchanged from the accepted architecture: ECS Fargate for API and relay with target-tracking autoscaling, the worker as an SQS-triggered container-image Lambda, RDS Postgres + PostGIS with a managed read replica, and the SNS topic → SQS notifications queue + DLQ.

### Consequences

* Good - the marked deployment runs on the actual course environment, and the QA1 load test and QA3 failover test have a real target (primary + replica + shared Redis + queue).
* Good - every accepted backend tactic survives; the report can argue the substitutions are environment-imposed, not design compromises, and that a full account would restore CloudFront and least-privilege IAM with no change to module boundaries (the counter already runs on the same managed ElastiCache the idealised topology names).
* Bad - a single-node ElastiCache cluster has no automatic failover; a node replacement loses in-flight counts until reconciliation restores them. A replication group with Multi-AZ failover removes this at roughly double the node cost (ADR-0005).
* Bad - `LabRole` is broad; the deployed system is not least-privilege. Called out explicitly in the report's security critique.
* Bad - no HTTPS/CDN frontend on the lab; the SPA is served over plain HTTP from an S3 website bucket (ADR-0020). A full account restores CloudFront + HTTPS with no application change.
* Bad - short-lived lab credentials mean state and `apply` must be re-authenticated each session; documented in the [`../../infra/`](../../infra/) runbook.

### Confirmation

* `terraform validate` and `terraform plan` succeed against the Learner Lab account.
* ElastiCache provisioning verified directly: a single-node probe cluster applied and was destroyed cleanly (2026-06-05) before the counter was wired to the managed service.
* No `aws_iam_role` / `aws_iam_policy` resources exist in the configuration - only a `data` lookup of `LabRole` (grep in code review).
* A deployed stack passes a `/healthz` smoke check via the ALB DNS output, and the QA1/QA3 tests run against the stack's primary + replica + Redis + queue.
* `terraform destroy` leaves no surviving billable resource.

## Pros and Cons of the Options

### (a) Idealised topology unchanged

* Good - matches the overview verbatim; no deviation to document.
* Bad - does not provision on Learner Lab at all (`aws_iam_role`/policy creation and custom domains both fail; ElastiCache itself provisions fine). Non-starter.

### (b) docker-compose only

* Good - zero cloud cost; already exists for local dev.
* Bad - no read replica, no managed queue, no autoscaling, no Lambda - cannot demonstrate QA1 scalability or QA3 failover on real infrastructure. Fails the architecture-evaluation evidence requirement.

### (c) Learner Lab profile

* Good - runs on the marked environment with every tactic intact and a clear "what a full account would change" story.
* Bad - one documented compromise (broad IAM via `LabRole`) plus the deferred CloudFront frontend, both surfaced honestly in the report.

## More Information

Implemented by the Terraform under [`../../infra/`](../../infra/); the apply/destroy runbook and the Learner Lab credential workflow live in [`../../infra/README.md`](../../infra/README.md). Revisit this decision if the team is granted a full AWS account, in which case the remaining substitutions - (2) broad IAM and (4) deferred CloudFront frontend - revert to the idealised topology with no change to module boundaries; the counter (1) already matches it. Related: ADR-0002 (extracted worker), ADR-0005 (counter store), ADR-0006 (async fan-out / outbox), ADR-0008 (read replica + reliability), ADR-0016 (relay-side fan-out).
