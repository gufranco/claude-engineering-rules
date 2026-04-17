# Code Review

## As Author

- Self-review the entire diff line by line
- Run all tests locally
- Keep PRs small (< 400 lines ideally, max 1000)
- One logical change per PR
- Include before/after screenshots for UI changes
- Verify visual identity consistency: new pages must match existing pages in layout structure, spacing tokens, component usage, badge patterns, loading states, and pagination

## Review Comments

Write review comments the way a human colleague would. No prefix labels, no structured templates. Just say what you mean directly.

### No Internal Config Leakage (MANDATORY)

Every review comment, PR description, PR comment, Slack message, and any other externally-visible text must read as if a human engineer wrote it from experience. The reader has no access to our internal configuration and must never learn it exists.

**Never reference, cite, or mention:**

- `~/.claude/`, `rules/`, `checklists/`, `standards/`, `skills/`
- File names like `checklist.md`, `code-style.md`, `testing.md`, `database.md`
- Phrases like "per our rules", "per our standards", "category 17", "checklist item 3"
- Rule-sourced phrasing that implies a codified checklist: "this violates rule X", "standard Y requires"

**Instead, state the engineering reason directly:**

```
# Bad: leaks internal config
This violates `rules/testing.md` mock policy. Per `checklists/checklist.md`
category 8, mocking internal services is a blocking issue.

# Good: same knowledge, human voice
These tests mock internal services instead of using a real database.
A test that verifies mock wiring proves the mock works, not the code.
If someone reverts the fix, all five tests still pass. That is zero
regression protection for a security fix.
```

## Test Evidence (MANDATORY)

Every behavior-changing PR must have passing test evidence. CI pipeline passing is sufficient. Only request manual output when CI doesn't exist, doesn't run tests, or hasn't executed.

## Branch Freshness (MANDATORY)

Before approving any PR, check if the branch is behind the base branch. If it is:

- Request a rebase onto the latest base branch
- Request fresh test evidence after the rebase
- If there are merge conflicts, request resolution and new evidence

## Documentation (README) - MANDATORY

Every task completion MUST include a README check. Update the README when the change affects:

- New environment variables
- New API endpoints
- Authentication changes
- New commands or scripts
- Changed setup steps
- New dependencies with setup
- Architecture changes
- New features

## Technical Debt

**When reviewing or completing work:**

- If you introduce a shortcut or known limitation, document it with a `TODO(debt):` comment explaining what the ideal solution is and why it wasn't done now
- If you encounter existing debt while working, note it but do not fix it in the same PR. File it separately
- Classify debt by impact: **blocks future work** (fix soon), **slows development** (schedule), **cosmetic** (backlog)

### Architecture Decision Records (ADR)

```
# ADR-NNN: <Title>

**Status**: proposed | accepted | deprecated | superseded by ADR-NNN
**Date**: YYYY-MM-DD

## Context
## Decision
## Consequences
```

Store in `docs/adr/`. Number sequentially. Never delete superseded ADRs, mark them as superseded and link to the replacement.

## Zero Warnings (MANDATORY)

Warnings are blocking issues with the same severity as bugs. A PR that "passes CI" with deprecation warnings or non-fatal annotations is not passing.

## Pre-Completion Checklist

Run through `checklists/checklist.md`. All categories apply during implementation as a self-review loop.
