# TicketTailor

CSSE6400 capstone project, Semester 1 2026. Final submission: whatever is on `main` at 15:00 on 8 June 2026.

A university social-events platform - interactive map, RSVP, club/society follow-graph, real-time notifications when events change or transition from club-only to public.

## Where things live

| Location | What it is |
| --- | --- |
| [`docs/architecture-overview.md`](docs/architecture-overview.md) | What the system is and how it's structured |
| [`docs/working-agreement.md`](docs/working-agreement.md) | Rules everyone (human or AI) follows when working in this repo |
| [`docs/conventions.md`](docs/conventions.md) | Coding conventions |
| [`docs/traceability.md`](docs/traceability.md) | Requirements → tests matrix |
| [`docs/extension-paths.md`](docs/extension-paths.md) | How each module would be extracted to a service |
| [`model/artefacts/c4/`](model/artefacts/c4/) | C4 L1/L2/L3 diagrams (d2 source, auto-rendered to SVG by CI) |
| [`model/adrs/`](model/adrs/) | Architectural decision records (MADR format) |
| [`report/`](report/) | LaTeX source for the assessment report |
| [`docker-compose.yml`](docker-compose.yml) | Local development stack (PostgreSQL+PostGIS, Redis, Mailpit, API) |
| [`infra/README.md`](infra/README.md) | **Deploy runbook** - Terraform to AWS Academy Learner Lab (start here to deploy) |
| [`demo.md`](demo.md) | Demo video link (added before submission) |

Source code, tests, and infrastructure scaffolding live under [`api/`](api/), [`worker/`](worker/), [`relay/`](relay/), [`web/`](web/), [`tests/`](tests/), and [`infra/`](infra/). Each has its own `README.md`.

## Running locally

The full development stack is defined in [`docker-compose.yml`](docker-compose.yml). From the repository root:

```bash
docker compose up --build
```

This starts PostgreSQL+PostGIS, Redis, and Mailpit, applies all database migrations, and serves the API on http://localhost:8000 (Swagger at `/docs`). See [`api/README.md`](api/README.md) for the full backend workflow, including running tests.

## Deploying to AWS

The cloud deployment (ECS Fargate API + relay, Lambda worker, RDS primary + read replica, SNS/SQS, Redis) is fully described in [`infra/README.md`](infra/README.md) - a step-by-step runbook for AWS Academy Learner Lab, including credential setup, secret generation, the deploy sequence, teardown, and a troubleshooting table. Decisions behind the Learner Lab mapping are in [`model/adrs/0017-learner-lab-deployment-profile.md`](model/adrs/0017-learner-lab-deployment-profile.md).

## First time in the repo

Before any non-trivial change, read [`docs/working-agreement.md`](docs/working-agreement.md). It is short and binding.
