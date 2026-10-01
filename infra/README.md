# Infrastructure as code

Terraform for deploying TicketTailor to **AWS Academy Learner Lab**. The module
layout mirrors the architecture; the Learner Lab substitutions (`LabRole`
instead of per-service IAM, default endpoints instead of custom domains) are
decided in [ADR-0017](../model/adrs/0017-learner-lab-deployment-profile.md). The
RSVP counter runs on managed ElastiCache, as the idealised topology specifies -
the lab was confirmed to permit it.

> **New teammate? Read this top to bottom once.** The whole deploy is ~6 commands,
> but the Learner Lab environment (the `voclabs` role) has sharp edges that the
> [Troubleshooting](#troubleshooting) section at the bottom covers.

## What gets deployed

| Module | Resources | Architecture role |
| --- | --- | --- |
| `networking` | VPC, public/private subnets ×2 AZ, IGW, one NAT, security groups | Isolation; private egress for Fargate/Lambda |
| `database` | RDS Postgres 16 + PostGIS primary **+ read replica** | Primary store; map reads off the replica (ADR-0008) |
| `messaging` | SNS topic → notifications SQS queue + DLQ | Async fan-out (ADR-0006/0016) |
| `registry` | ECR repos: `api`, `relay`, `worker` | Image registry |
| `compute` | ECS cluster; API service (ALB + CPU autoscaling); relay singleton; ElastiCache Redis counter; worker container Lambda + SQS trigger | The three deployable units + counter (ADR-0002/0005/0010/0016/0017) |
| `frontend_website` | Public S3 static website (HTTP) - the **lab SPA host** (`enable_frontend_website=true`) | SPA hosting on the lab over HTTP (ADR-0020); published with `make web` after apply |
| `frontend` | S3 + CloudFront (OAC) - **gated off** (`enable_frontend=false`) | Full-account SPA host (HTTPS); `cloudfront:*` is denied to voclabs, so use `frontend_website` on the lab (ADR-0017/0018/0020) |

All task/execution/Lambda roles reference the pre-provisioned `LabRole`; this
config creates **no** `aws_iam_role`/`aws_iam_policy` resources (ADR-0017).

## 1. Prerequisites (install once)

| Tool | Why | Install (Ubuntu/WSL) |
| --- | --- | --- |
| Terraform ≥ 1.6 | runs everything | [terraform.io/downloads](https://developer.hashicorp.com/terraform/downloads) |
| Docker (running) | build the 3 images | already on most dev boxes; `docker info` to check |
| AWS CLI v2 | ECR login in the push step | see below |
| Python 3 | the helper scripts | preinstalled |
| `make` (optional) | command shortcuts | `sudo apt install make` |

```bash
# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install && rm -rf awscliv2.zip aws
aws --version
```

Don't have `make`? Every `make X` below has the raw command beside it - use either.

## 2. Each lab session - credentials (they expire ~4 h)

The deploying role is **`voclabs`**, and its credentials are temporary and rotate
every time you start the lab.

1. In the Learner Lab page: **AWS Details → AWS CLI: Show**.
2. Copy the whole block into `~/.aws/credentials` under `[default]`. It has **three**
   lines - `aws_access_key_id`, `aws_secret_access_key`, **and `aws_session_token`**.
   The session token is mandatory; Terraform fails with auth errors without it.
3. Verify:

```bash
aws sts get-caller-identity   # prints an ARN ending in .../voclabs/... when good
```

If this errors, your session has lapsed - re-copy the block.

## 3. App secrets → `terraform.tfvars` (once)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars

# generate secret_key + a valid VAPID key pair, then paste the printed lines in
./scripts/gen-secrets.sh
```

Then edit `terraform.tfvars` and set `db_password` (any strong string). Leave
`resend_api_key = ""` unless you have a Resend key - empty disables email and is
fine for the demo. `terraform.tfvars` is gitignored; **never commit it**.

> For a **shared team deployment**, agree on one set of secrets (especially the
> VAPID pair, which must match the frontend later) and share them out-of-band -
> don't each generate your own for the same stack. For independent `dev` stacks,
> generating your own is fine.

## 4. Deploy (~6 commands)

Run from `infra/`. The worker Lambda validates its image when it's created, so the
ECR repos and images must exist **before** the full apply - hence the two-phase order.

```bash
# init + select the environment workspace
make init ENV=dev          # terraform init && terraform workspace select dev || terraform workspace new dev

# dry run - creates nothing; checks creds, LabRole, region, config
make plan ENV=dev          # terraform plan

# create ONLY the ECR repos
make repos ENV=dev         # terraform apply -target=module.registry

# build + push api/relay/worker images into those repos
make images TAG=latest     # ./scripts/build-and-push.sh latest

# create everything else (RDS, ECS, ALB, SNS/SQS, Lambda, ElastiCache)
make apply ENV=dev         # terraform apply

# smoke-check the API through the ALB
make smoke ENV=dev         # curl -fsS "$(terraform output -raw api_healthcheck)"

# publish the SPA (only if enable_frontend_website = true; see "Frontend" below)
make web                   # ./scripts/deploy-web.sh
```

`terraform output` then prints the API URL, ECR repos, DB primary/replica
addresses, the SNS topic, the SQS queue URL, and - when the frontend is on -
`frontend_website_url`, the public SPA URL.

### Frontend (the public SPA URL) - ADR-0020

The `voclabs` role is denied `cloudfront:*`, so the HTTPS CloudFront frontend
(`enable_frontend`) is a full-account path. On the **lab**, serve the SPA from a
public S3 static **website** bucket over HTTP (HTTP both ends, so no mixed
content with the HTTP API):

1. Set `enable_frontend_website = true` in `terraform.tfvars`.
2. `make apply ENV=dev` - creates the website bucket and wires the bucket's
   origin into the API's `CORS_ALLOWED_ORIGINS` automatically.
3. `make web` - builds the SPA with `NEXT_PUBLIC_API_URL = $(terraform output -raw api_url)`
   and syncs `web/out` to the bucket. (Must run **after** apply: the build bakes
   the ALB API URL, which only exists post-apply.)
4. Open `terraform output -raw frontend_website_url`.

Re-run `make web` whenever the SPA changes. If you ever recreate the bucket,
re-run `make apply` first so the API CORS origin follows the new URL.

> The full apply takes **~10-15 min** - RDS primary + replica dominate (the
> replica can only build after the primary's backups exist; Terraform orders it).
> The API container runs DB migrations on startup, so there's no manual migration
> step; if a service looks unhealthy for the first minute, give RDS time and
> re-run the smoke check.

## 5. Teardown - every session, when done

```bash
make destroy ENV=dev       # terraform destroy
```

The lab bills while resources exist (RDS ×2, NAT, ALB, ElastiCache, Fargate tasks).
Don't leave a stack up overnight. `force_delete`/`skip_final_snapshot` are set so
destroy is clean and leaves nothing billable.

## Remote state (team - recommended)

So teammates share one state instead of each holding a local copy: uncomment the
`backend "s3"` block in `versions.tf`, `cp backend.hcl.example backend.hcl`, set
your team's pre-created bucket, then `terraform init -backend-config=backend.hcl`.
Left commented, Terraform uses local state (fine for a solo run / `plan`).

## Troubleshooting

Errors we have actually hit on `voclabs`, and what they mean:

| Error (abridged) | Cause | Fix |
| --- | --- | --- |
| `aws: command not found` (in the push step) | AWS CLI not installed | install it (§1) |
| `make: command not found` | `make` not installed | `sudo apt install make`, or use the raw command beside each step |
| Auth / `ExpiredToken` / `InvalidClientTokenId` | lab session lapsed, or `aws_session_token` line missing | re-copy all three credential lines (§2) |
| `not authorized to perform: servicediscovery:*` | voclabs denies Cloud Map | no longer relevant - the counter is on managed ElastiCache, nothing needs Cloud Map (ADR-0017). If you see this, you're on stale code; `git pull` |
| `not authorized to perform: cloudfront:*` | voclabs denies CloudFront | already handled - frontend is gated off (`enable_frontend=false`) |
| RDS `Cannot find version 16.x` | that minor was retired in-region | already handled - engine is pinned to major `16` |
| Lambda `image manifest ... not supported` | image built as an OCI index | already handled - `build-and-push.sh` uses `--provenance=false`. Rebuild + push, then re-apply |
| SSM `Value at 'value' failed ... length >= 1` | an empty secret (e.g. `resend_api_key`) | already handled - empty secrets are skipped |
| `Invalid for_each argument ... sensitive value` | older code used a secret in a `for_each` key | already handled; `git pull` if you see it |
| `... already exists` after an interrupted apply | a resource was created but isn't in state | re-run `terraform apply` (often resolves); if not, `terraform import` it or destroy + redeploy. **Don't** hand-delete in the console while state thinks it exists |
| Smoke check fails right after apply | RDS/containers still warming | wait ~1 min, re-run `make smoke ENV=dev`; check ECS service events / CloudWatch logs `/ecs/tickettailor-dev/*` |

## Known gaps / follow-ups

- **Lab frontend is HTTP-only (S3 website, no CDN/TLS)** - on the lab the SPA is
  served from a public S3 static website over HTTP (ADR-0020), because voclabs
  denies `cloudfront:*`. See "Frontend (the public SPA URL)" above for the
  publish steps. The HTTPS upgrade is the CloudFront path (`enable_frontend`),
  which on a full account also needs HTTPS on the API (ACM cert + HTTPS ALB
  listener) and the CloudFront origin in `CORS_ALLOWED_ORIGINS`, or the HTTPS
  SPA breaks on mixed content / CORS.
- **No HTTPS on the ALB** - the API is HTTP over the ALB DNS name (no ACM cert /
  custom domain on the lab). Fine for testing; note it in the security critique.
- **`LabRole` is broad** - not least-privilege; called out in ADR-0017.
- **QA1 transition-scan index** - done: the partial index
  `idx_events_transition_scan` on `(transition_at) WHERE visibility='club_only'`
  is created by events migration `c4a9e1f2b3d5`, so the relay's FR5 flip scan is
  index-backed before load-testing.
