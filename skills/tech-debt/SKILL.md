---
name: tech-debt
description: Technical debt triage and prioritization. Scans the codebase for TODO/FIXME/HACK/debt markers, categorizes by impact, estimates effort, and produces a prioritized backlog. Use when user says "tech debt", "show todos", "what needs fixing", "debt triage", "technical debt", "cleanup backlog", or wants to systematically review accumulated shortcuts. Do NOT use for implementing fixes (use the fix directly), code review (use /review), or assessment (use /assessment).
---

Systematic scan and triage of technical debt markers across the codebase. Produces a prioritized backlog that can be turned into tickets or PR groupings.

## Arguments

- No arguments: full codebase scan.
- `<path>`: scan only the specified directory.
- `--critical`: show only items categorized as "blocks future work".

## Process

### Step 1: Scan for debt markers

Search the codebase for these patterns using Grep:

| Marker | Meaning |
|--------|---------|
| `TODO` | Planned work not yet done |
| `FIXME` | Known broken code that needs repair |
| `HACK` | Intentional shortcut that should be replaced |
| `XXX` | Dangerous or fragile code |
| `TEMP` | Temporary solution meant to be replaced |
| `WORKAROUND` | Bypass for an external bug or limitation |
| `DEBT` | Explicitly tagged technical debt |
| `@deprecated` | Code marked for removal |
| `TODO(debt):` | Debt tagged per project convention |

Exclude `node_modules/`, `dist/`, `build/`, `.next/`, `vendor/`, and other build output directories.

### Step 2: Extract context

For each finding:

1. Record the file path and line number.
2. Read 2 lines before and 2 lines after the marker for context.
3. Extract the comment text following the marker.
4. Check if the marker includes an author or ticket reference.

### Step 3: Categorize by impact

Assign each item to one of three categories:

| Category | Criteria | Priority |
|----------|----------|----------|
| Blocks future work | Referenced by other TODOs, sits in a code path that a planned feature needs, prevents a dependency upgrade, or blocks a migration | High |
| Slows development | Repeated workaround across multiple files, missing abstraction that forces copy-paste, fragile code that breaks on every change | Medium |
| Cosmetic | Naming improvements, dead code removal, formatting inconsistencies, outdated comments | Low |

### Step 4: Estimate effort

Assign a size estimate based on the scope of the fix:

| Size | Definition |
|------|-----------|
| S | Under 1 hour, touches 1-2 files |
| M | Half day, touches 3-5 files |
| L | Full day, cross-cutting change across a module |
| XL | Multi-day, architectural change affecting multiple modules |

### Step 5: Check staleness

Run `git blame` on each finding to determine when the marker was added. Items older than 6 months get a staleness flag. Staleness indicates the debt has been tolerated long enough that it is either not important or has become so embedded that fixing it requires extra care.

### Step 6: Output the backlog

Present findings as a prioritized table:

| # | Priority | File:Line | Category | Size | Age | Description |
|---|----------|-----------|----------|------|-----|-------------|
| 1 | High | src/auth/session.ts:42 | Blocks | M | 8mo | TODO: replace session store before scaling |
| 2 | High | src/billing/invoice.ts:115 | Blocks | L | 3mo | HACK: hardcoded tax rate |
| 3 | Medium | src/api/middleware.ts:28 | Slows | S | 14mo | FIXME: error swallowed silently |

If `--critical` was passed, show only "Blocks future work" items.

### Step 7: Suggest groupings

Identify items that can be fixed together in a single PR:

- Items in the same file
- Items that address the same pattern across multiple files
- Items that share a dependency on the same refactoring

Present groupings as suggested PR scopes:

```
PR 1: "fix(auth): replace session store"
  - src/auth/session.ts:42
  - src/auth/refresh.ts:18

PR 2: "fix(billing): extract tax calculation"
  - src/billing/invoice.ts:115
  - src/billing/quote.ts:89
  - src/billing/credit-note.ts:34
```

## Rules

- This skill scans and reports. It does not fix anything. Use the appropriate skill or direct implementation for fixes.
- Do not modify any files during the scan.
- Report every marker found. Do not filter silently. If a marker seems trivial, categorize it as "Cosmetic" but still include it.
- When a marker includes a ticket reference, include it in the output so the user can cross-reference with their issue tracker.
- Staleness is informational, not judgmental. Old debt is not automatically more important than new debt.

## Related skills

- `/refactor` -- Execute structural improvements identified by the scan.
- `/assessment` -- Full codebase quality assessment beyond debt markers.
- `/review` -- Review a PR that addresses debt items.
- `/investigate` -- Debug issues caused by known debt.
