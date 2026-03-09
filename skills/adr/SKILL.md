---
name: adr
description: Create and manage Architecture Decision Records for significant technical decisions
---

# /adr

Creates, lists, and manages Architecture Decision Records. ADRs capture the context, alternatives, and reasoning behind significant technical decisions so future engineers understand WHY, not just WHAT.

## When to use

- After making a non-trivial architecture decision: database choice, service boundary, auth strategy, framework selection
- When changing or reversing a previous architecture decision
- During `/plan` when a decision deserves its own permanent record
- When someone asks "why did we do it this way?" and the answer isn't obvious from the code

## When NOT to use

- Implementation details that don't affect architecture
- Decisions that are trivially reversible: variable naming, file placement within an established structure
- Temporary experiments or spikes

## Arguments

- No arguments: list existing ADRs in the project
- `new <title>`: create a new ADR interactively
- `supersede <number> <title>`: create a new ADR that supersedes an existing one
- `--status <status>`: filter list by status: proposed, accepted, deprecated, superseded

## Process

### 1. Locate or create the ADR directory

Check for `docs/adr/` in the project root. If it doesn't exist, create it.

Read existing ADRs to determine the next sequence number. Files follow the pattern `NNN-<slug>.md` where NNN is zero-padded to 3 digits.

### 2. Gather context (for new ADRs)

Ask the user one question at a time:

1. "What decision needs to be recorded?" — The specific technical choice made
2. "What problem or situation required this decision?" — The context and constraints
3. "What alternatives were considered?" — At least 2 options with trade-offs

Wait for each answer before asking the next.

### 3. Draft the ADR

```markdown
# ADR-NNN: <Title>

**Status:** accepted
**Date:** <YYYY-MM-DD>

## Context

What problem or situation required this decision? What constraints exist?

## Decision

What was decided and why this option was chosen over the alternatives.

## Alternatives Considered

### <Alternative 1>

Description, pros, cons.

### <Alternative 2>

Description, pros, cons.

## Consequences

### Positive

- What becomes easier or better

### Negative

- What becomes harder or more complex

### Risks

- What could go wrong with this decision
```

### 4. Review and create

Show the draft to the user. Incorporate feedback. Write the file to `docs/adr/NNN-<slug>.md`.

### 5. Handle supersession

When superseding an existing ADR:

1. Read the original ADR
2. Update its status line to: `**Status:** superseded by [ADR-NNN](NNN-<slug>.md)`
3. Create the new ADR with a reference: "Supersedes [ADR-NNN](NNN-<slug>.md)" in the Context section
4. Write both files

### 6. Summary

After creating or updating, show:

- File path of the new ADR
- Updated status of any superseded ADRs
- Total ADR count in the project

## Rules

- ADRs are append-only. Never delete a superseded ADR. Mark its status and link to the replacement
- Number sequentially starting from 001. Gaps are fine
- The title describes the decision, not the problem: "Use PostgreSQL for primary store" not "Database selection"
- Status values: `proposed`, `accepted`, `deprecated`, `superseded by ADR-NNN`
- Keep ADRs concise. Context and Decision sections together should fit on one screen
- At least two alternatives must be documented. If only one option exists, explain why
- Reference related ADRs when decisions interact with each other

## Related skills

- `/plan` — Creates specs that may trigger ADR creation for significant decisions
- `/assessment` — May surface undocumented decisions that need ADRs
- `/review` — Checks whether architectural changes have corresponding ADRs
