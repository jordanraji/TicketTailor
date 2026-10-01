---
status: "{proposed | accepted | rejected | deprecated | superseded by ADR-NNNN}"
date: YYYY-MM-DD
decision-makers: [names]
consulted: [names]
informed: [names]
---

# {Short noun phrase describing the decision}

## Context and Problem Statement

{2-3 sentences on the situation, the forces in tension, and the question being decided. Link to related ADRs, ASRs, or proposal sections.}

## Decision Drivers

* {e.g. scalability ASR - must handle event-publish spikes}
* {e.g. interoperability ASR - must export to Google/Outlook/Apple Calendar}
* {e.g. team familiarity, deadline pressure, …}

## Considered Options

* {Option 1 - short name}
* {Option 2 - short name}
* {Option 3 - short name}

## Decision Outcome

Chosen option: **{Option X}**, because {one-sentence justification tied to the strongest decision driver}.

### Consequences

* Good - {positive consequence}
* Good - {positive consequence}
* Bad - {negative consequence / what we give up}

### Confirmation

{How will we know this decision is being honoured? e.g. an integration test, a CI check, a code review rule, an architecture-fitness function.}

## Pros and Cons of the Options

### {Option 1}

* Good - {argument}
* Bad - {argument}

### {Option 2}

* Good - {argument}
* Bad - {argument}

## More Information

{Links to spikes, prototypes, related ADRs, references. Note any conditions under which this decision should be revisited.}
