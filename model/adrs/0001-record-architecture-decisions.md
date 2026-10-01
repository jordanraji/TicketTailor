---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Record architectural decisions

## Context and Problem Statement

CSSE6400 grades architecture description (25%) and architecture evaluation (20%) - together, 45% of the project. The marker traces architecture evolution through the decision history. We need a uniform, reviewable record of every significant decision: what we chose, what we considered, and why.

## Decision Drivers

* The architecture-description grading criterion explicitly values clarity and traceability of decisions.
* Future readers (markers, future team, future-us) must be able to reconstruct intent from the repository alone.
* Decisions made in chat or in standup vanish; decisions in the repo persist.

## Considered Options

* No structured decision log - decisions live in commit messages and chat.
* MADR (Markdown Any Decision Records) format - one file per decision, numbered sequentially.
* Confluence/Notion external decision log.

## Decision Outcome

Chosen option: **MADR**, because the decision history needs to live with the code, be reviewable in PRs, and survive the loss of any external tool. The team has already authored an MADR template at [`template.md`](template.md).

### Consequences

* Good - every architecturally significant decision is reviewed and committed alongside the code that implements it.
* Good - the report's "Architecture Options" section can cite ADRs directly rather than re-litigating decisions.
* Good - the marker can audit the decision history in one directory.
* Bad - adds discipline overhead. A team that forgets to add an ADR before implementing a significant change has to backfill it.

### Confirmation

ADR-first rule recorded in [`../../docs/working-agreement.md`](../../docs/working-agreement.md). PR review enforces it: any PR that introduces a new service, datastore, external dependency, or cross-module import without an ADR is blocked.

## Pros and Cons of the Options

### No structured decision log

* Good - zero overhead.
* Bad - fails the grading criterion. Reviewers can't reconstruct *why*.

### MADR

* Good - lives with the code, reviewed in PRs, survives tool churn.
* Good - template already authored; pattern is well-known.
* Bad - discipline overhead.

### External tool

* Good - richer formatting and search.
* Bad - yet-another-tool. Drift from the code is the failure mode. If the tool goes away the history is lost.

## More Information

Template: [`template.md`](template.md). New ADRs are numbered sequentially. Status transitions: `proposed` → `accepted` (via team review) → optionally `superseded by ADR-NNNN` if replaced.
