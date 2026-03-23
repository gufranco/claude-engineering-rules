# Pre-Flight

## Core Rule

No implementation without pre-flight verification. Wrong-direction work is the most expensive mistake.

## When to Apply

Before implementing any non-trivial change. Skip for single-line fixes, typos, and config tweaks where the change is obvious.

## Gate

Run these checks in order. If any fails, stop and resolve before writing code.

### 1. Duplicate Check

Search the codebase, open PRs, recent branches, and community packages for existing solutions.

| Where to look | How |
|----------------|-----|
| Current codebase | Grep for keywords, function names, feature terms |
| Open PRs | `gh pr list --search "<keywords>"` |
| Recent branches | `git branch -a --list "*<keyword>*"` |
| Closed PRs | `gh pr list --state closed --search "<keywords>"` |
| Community packages | Search for established libraries that solve the problem. Check npm, PyPI, or the relevant registry |

If a solution exists in the codebase, reuse or extend it. If a well-adopted package exists, suggest it before implementing manually. Building from scratch what a maintained library already solves is wasted effort and ongoing maintenance burden.

When suggesting a package, follow the evaluation criteria from `rules/code-style.md` Dependencies section: compare top options, check maintenance activity, community size, vulnerabilities, and bundle size.

### 2. Architecture Fit

Read the surrounding code. Confirm the new code fits the existing patterns, except when existing patterns violate `~/.claude/` rules. Rules always take priority.

- What conventions does this area of the codebase follow?
- What abstractions already exist that the new code should use?
- Would this change require modifying callers, consumers, or dependents?
- Does it belong in this module, or does it belong somewhere else?

If the change doesn't fit the existing architecture, raise it before implementing.

### 3. Interface Verification

Verify every external interface the implementation will touch.

| Interface | How to verify |
|-----------|---------------|
| Functions to call | Read their signatures and return types |
| APIs to consume | Read the route, controller, or schema |
| Libraries to use | Fetch docs (llms.txt or official docs) |
| Database tables | Read the schema or migration files |
| Config and env vars | Read `.env.example` or consuming code |

No guessing. If the interface is ambiguous, clarify before coding.

### 4. Root Cause Confirmation (Bug Fixes Only)

For bug fixes, confirm the root cause before writing the fix.

- Can you reproduce the bug reliably?
- Can you explain WHY it happens, not just WHERE?
- Can you predict what a specific test input will do?

If any answer is no, investigate further. Do not write a speculative fix.

### 5. Warning Baseline

Apply the "Warning baseline" section of `checklists/checklist.md` category 17. Run linter, type checker, and test suite on the files you plan to change. Record the current warning count. After implementation, the count must be equal to or lower.

### 6. Scope Agreement

Confirm the scope is bounded and agreed upon.

- What files will change? List them.
- What will NOT change? State the boundary explicitly.
- Are there follow-up tasks that should be separate?

If scope is unclear, ask one question before starting.

## Confidence Signal

After completing the gate, briefly state:

- What was checked and confirmed
- Which interfaces were verified
- What the implementation approach will be

Then proceed. One sentence is enough for small tasks.

## Common Failures

- Starting implementation before reading the existing code in the area
- Assuming a library API works a certain way without checking docs
- Fixing a bug based on a theory that was never tested
- Implementing a feature that already exists in a different module
- Expanding scope mid-implementation without checking with the user
