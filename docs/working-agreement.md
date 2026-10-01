# Working agreement

How everyone - every team member, every reviewer - works in this repository. These rules are the contract that keeps the architecture credible at submission time.

## Read before non-trivial work

Before any change beyond a typo:

1. The latest ADRs in [`../model/adrs/`](../model/adrs/), in numerical order. The decision history is part of the architecture description grade.
2. This working agreement.
3. [`conventions.md`](conventions.md) - coding conventions.
4. [`traceability.md`](traceability.md) - every functional or quality-attribute requirement maps to a test here.
5. [`architecture-overview.md`](architecture-overview.md) - the prose description of what we are building and why.

If you don't know whether a change is "non-trivial," ask in the team channel before you start.

## Core rules

### Editing rule

Prefer editing existing files over creating parallel ones. Two `service.py` files in different shapes is the failure mode this rule prevents. If the existing file is wrong, fix it; if the right answer is genuinely a new file, add it once and replace the old one in the same change.

### ADR-first rule

Architecturally significant decisions require an ADR proposed and committed *before* the implementation lands on `main`. Significant means at least one of:

- A new deployable process or service.
- A new datastore or persistent store.
- A new external dependency (third-party API, paid service).
- A change to authentication, authorisation, or any other security-relevant tactic.
- A change to a quality-attribute strategy (e.g. how scalability is achieved).
- Any cross-module import inside the API that would breach the agreed module boundaries.

Use [`../model/adrs/template.md`](../model/adrs/template.md). Number sequentially. Status starts `proposed`; flip to `accepted` only after the team agrees in review.

### Quality-attribute claims rule

Every claim about a quality attribute - in the report, in a PR description, in a demo - links to the actual test that measured it, recorded in [`traceability.md`](traceability.md). Never invent metrics. If a number isn't backed by a test artefact in the repo, it doesn't go in the report.

### Report sync rule

[`../report/`](../report/) must stay in sync with reality. If the code diverges from what the report claims, whoever notices opens an issue or fixes the report in the same PR. Drift between report and code is the single most common way capstones lose architecture-description marks.

### Module boundary rule

The API is a modular monolith. Modules talk to each other only through their service interfaces - never by importing another module's repository, model, or internal helpers. This rule is what makes the "expandable to a larger system" criterion answerable. It must be enforced in CI by an automated boundary check (import-linter or equivalent - see [`conventions.md`](conventions.md)). PRs that breach it are blocked.

### Commit hygiene

Don't commit:

- Binaries, `.docx`, generated PDFs (the report PDF is built by CI, not committed).
- `node_modules/`, `.venv/`, `__pycache__/`, build/test caches (already gitignored).
- Terraform state files (`.tfstate`, `.tfstate.backup`).
- Real credentials, `.env` files (use `.env.example` instead).

Use `git add <path>` rather than `git add -A` for any commit that includes untracked files.

## Branching, PRs, review

- `main` is protected. No direct pushes.
- Feature branches off `main`, merged via PR.
- Every PR needs at least one team-member review.
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. PR titles follow the same convention.
- Squash-merge by default unless the branch is genuinely a multi-commit story worth preserving.

## Definition of done for a change

A change is done when:

1. Code is written and reviewed.
2. Tests are written, the relevant row in [`traceability.md`](traceability.md) is updated, and CI is green.
3. ADRs touched or required by the change are committed.
4. If the change affects architecture, [`architecture-overview.md`](architecture-overview.md) is updated in the same PR.
5. If the change affects user-visible behaviour, the report is updated or an issue is filed.
