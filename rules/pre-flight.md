# Pre-Flight

## Core Rule

No implementation without pre-flight verification. Wrong-direction work is the most expensive mistake.

## When to Apply

Before implementing any non-trivial change. Skip for single-line fixes, typos, and config tweaks where the change is obvious.

## Gate

Run these checks in order. If any fails, stop and resolve before writing code.

### 1. Duplicate Check

| Where to look | How |
|----------------|-----|
| Current codebase | Grep for keywords, function names, feature terms |
| Open PRs | `gh pr list --search "<keywords>"` |
| Recent branches | `git branch -a --list "*<keyword>*"` |
| Closed PRs | `gh pr list --state closed --search "<keywords>"` |
| Community packages | Search npm, PyPI, or the relevant registry for established solutions |

If a solution exists in the codebase, reuse or extend it. If a well-adopted package exists, suggest it before implementing manually. When suggesting a package, evaluate top options using the criteria in `rules/code-style.md` (Dependencies section).

### 1b. Market and Competitor Research (Feature Planning)

**When this gate applies:** any new feature, workflow, integration, or UX pattern. Does not apply to bug fixes, config changes, or purely internal refactors.

Research competitors across regions (US enterprise, US/CA startups, European, Brazilian, LatAm), open source projects in the same stack and any stack, the user's own repos across all accounts, and comparison/review sites. Do not stop after 2-3 results.

For every platform or project researched, extract:
1. **Feature inventory**: what features exist, each one listed individually
2. **Data model**: entities, relationships, and cross-module connections
3. **Integration points**: cross-module triggers (quote auto-creates job, job completion auto-generates invoice)
4. **Lifecycle flows**: full journey from first touch to completion, with statuses and transitions
5. **UX patterns**: one-click conversions, inline editing, approval workflows
6. **Differentiators**: what this platform does that others do not
7. **Gaps**: what is missing compared to others

Document findings in `references.md` in the spec folder:

```markdown
### Platform Name (Region, Type)

**Features:** bullet list
**Data model highlights:** key entities and relationships
**Integration patterns:** cross-module triggers
**Unique approach:** what they do differently
**Gaps vs our platform:** what they lack
**Ideas to adopt:** specific patterns worth implementing
```

Build a cross-reference matrix after researching all sources:

| Feature/Pattern | Source A | Source B | Source C | Our platform | Action |
|----------------|---------|---------|---------|-------------|--------|
| Quote-to-job conversion | Yes | Yes | No | Missing | Implement |

Features present in 3+ sources are market-validated. Implement them. Do not present a plan until research is complete.

**Validation principle:**
- If every competitor implements a feature the same way, do it the same way. Users expect it
- If competitors implement it poorly, improve the implementation but keep the concept
- If no competitor has the feature, design it carefully with extra user validation
- Never assume a feature is unnecessary because competitors lack it. Ask the user
- Never assume a feature is necessary because competitors have it. Validate against the user's actual workflow

| Task scope | Research depth |
|-----------|---------------|
| Single feature | Search 5+ competitors. Read 2+ implementations |
| Module improvement | Search 10+ platforms across all regions. Read 3+ open source implementations. Build comparison matrix |
| Full roadmap or architecture plan | Search 15+ platforms. Read 5+ open source projects. Analyze user's own repos across all accounts |

### 1b-ii. Technology Selection is Deliberate

Reference projects are sources of ideas, not technology directives. Before adopting any technology from a reference:

1. Check if the current project already solves the problem with an existing tool
2. Evaluate the reference's choice against the current stack on the merits, not because the reference used it
3. Prefer consistency with the existing stack. Adding a new tool has an ongoing maintenance cost

### 1b-iii. Additive Planning

Follow-up instructions from the user merge into the existing plan. They never replace it. Add new requirements to the existing spec folder at the correct position in the task breakdown. Do not create a new spec folder or start over.

### 2. Architecture Fit

Read the surrounding code. Confirm the new code fits existing patterns, except when patterns violate `~/.claude/` rules. Rules always take priority.

- What conventions does this area follow?
- What abstractions already exist that the new code should use?
- Would this change require modifying callers, consumers, or dependents?
- Does it belong in this module?

If the change does not fit the existing architecture, raise it before implementing.

### 3. Interface Verification

| Interface | How to verify |
|-----------|---------------|
| Functions to call | Read their signatures and return types |
| APIs to consume | Read the route, controller, or schema |
| Libraries to use | Fetch docs (llms.txt or official docs) |
| Database tables | Read the schema or migration files |
| Config and env vars | Read `.env.example` or consuming code |

No guessing. If the interface is ambiguous, clarify before coding.

### 4. Root Cause Confirmation (Bug Fixes Only)

- Can you reproduce the bug reliably?
- Can you explain WHY it happens, not just WHERE?
- Can you predict what a specific test input will do?

If any answer is no, investigate further. Do not write a speculative fix.

### 5. Warning Baseline

Run linter, type checker, and test suite on the files you plan to change. Record the current warning count. After implementation, the count must be equal to or lower.

### 6. Scope Agreement

- What files will change? List them
- What will NOT change? State the boundary explicitly
- Are there follow-up tasks that should be separate?

If scope is unclear, ask one question before starting.

### 7. Diff-Aware Scope Detection

```bash
git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached
```

| Signal | File patterns |
|--------|--------------|
| `SCOPE_FRONTEND` | `*.tsx`, `*.jsx`, `*.css`, `*.scss`, `*.svelte`, `*.vue`, `components/`, `pages/`, `app/` |
| `SCOPE_BACKEND` | `*.service.ts`, `*.controller.ts`, `*.resolver.ts`, `routes/`, `handlers/`, `api/` |
| `SCOPE_TESTS` | `*.test.*`, `*.spec.*`, `__tests__/`, `tests/`, `test/` |
| `SCOPE_INFRA` | `*.tf`, `*.hcl`, `Dockerfile`, `docker-compose*.yml`, `k8s/`, `helm/` |
| `SCOPE_CONFIG` | `*.json`, `*.yaml`, `*.yml`, `*.toml`, `.env*`, `settings.*` (excluding lockfiles) |
| `SCOPE_SCHEMA` | `prisma/`, `migrations/`, `schema.graphql`, `*.sql` |
| `SCOPE_DOCS` | `*.md`, `docs/`, `README*`, `CHANGELOG*` |

Per-signal actions:
- `SCOPE_FRONTEND`: run Lighthouse or a viewport test. Check layout regressions
- `SCOPE_BACKEND`: verify every changed route, service method, and data contract
- `SCOPE_TESTS`: confirm coverage does not drop below 95% on changed files
- `SCOPE_INFRA`: run `terraform plan`. Verify no unintended resource changes
- `SCOPE_CONFIG`: check all consumers of the changed config are updated
- `SCOPE_SCHEMA`: verify migration is idempotent, reversible, and all related services are updated

When multiple signals are active, run all applicable checks.

## Confidence Signal

After completing the gate, briefly state what was checked, which interfaces were verified, and the implementation approach. One sentence is enough for small tasks.

## Common Failures

- Starting implementation before reading the existing code in the area
- Assuming a library API works a certain way without checking docs
- Fixing a bug based on a theory that was never tested
- Implementing a feature that already exists in a different module
- Expanding scope mid-implementation without checking with the user
