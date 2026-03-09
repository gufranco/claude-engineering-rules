---
name: plan
description: Gather context and create a structured implementation plan with a persistent spec folder
---

# /plan

Gathers requirements, searches for existing solutions, evaluates trade-offs, and produces a structured implementation plan saved to a spec folder. The spec persists as institutional memory for the project.

## When to use

- Before implementing any feature that touches 3+ files or involves architectural decisions
- When evaluating multiple technical approaches for a problem
- Before refactoring that changes module boundaries or data flow
- When onboarding to a task that needs context from multiple parts of the codebase

## When NOT to use

- Single-file changes, config tweaks, typo fixes
- Tasks where the implementation path is obvious and well-understood
- When a spec already exists and implementation can start immediately

## Arguments

- No arguments: interactive planning mode
- `<description>`: start planning with the given task description
- `--light`: abbreviated plan without reference gathering or trade-off analysis. Produces `plan.md` only
- `--resume`: locate and continue from the most recent spec folder in the project

## Process

### 1. Clarify scope

Ask the user to describe the task in one paragraph. If they already provided a description, confirm understanding.

Determine:

- What is being built or changed?
- What is the expected outcome?
- Are there constraints: timeline, compatibility, performance targets?

One question at a time. Do not front-load multiple questions.

### 2. Search for existing work

Run these **in parallel**:

- Grep the codebase for related patterns, similar features, or prior implementations
- `gh pr list --search "<keywords>"` for open PRs addressing the same area
- `git branch -a --list "*<keyword>*"` for in-progress branches
- `gh pr list --state closed --search "<keywords>"` for previously attempted solutions

If existing work is found, present it with file paths or PR links. The user decides whether to reuse, extend, or start fresh.

### 3. Gather references

Identify 2-5 files in the codebase that follow patterns the new code should match:

- Same module or domain area
- Similar data flow or API shape
- Same framework conventions

Read these files. Note the patterns: naming, structure, error handling, testing approach.

### 4. Match relevant rules

Read `rules/index.yml`. Match rules to the task using the `triggers` field. Suggest the top 3-5 most relevant rules. Read them to inform the plan.

### 5. Evaluate alternatives

For non-trivial decisions, identify 2-3 approaches. For each:

- Brief description in 2-3 sentences
- Trade-offs: performance, complexity, maintainability, compatibility
- Risk level: low, medium, high

Recommend one approach with a clear reason. Present to the user for approval before continuing.

For decisions significant enough to outlive this task, suggest creating an ADR with `/adr new <title>`.

### 6. Create the spec folder

Create a timestamped folder in the project:

```
specs/<YYYY-MM-DD>-<slug>/
  plan.md
  decisions.md
  references.md
```

If the project has a `.claude/` directory, create under `.claude/specs/` instead.

**plan.md:**

```markdown
# <Task Title>

## Goal

One paragraph: what this achieves and why.

## Approach

The chosen approach with key implementation details.

## Task Breakdown

Ordered list of steps. Each step includes:
- What to do
- Which files to create or modify
- Acceptance criteria for this step

## Risks

Known risks and how to mitigate them.
```

**decisions.md:**

```markdown
# Decisions

## <Decision Title>

**Context:** Why this decision was needed.

**Options:**
1. <Option A> — description, pros, cons
2. <Option B> — description, pros, cons

**Chosen:** <Which option> — <why>.
```

**references.md:**

```markdown
# References

## Patterns to Follow

- `path/to/file.ts` — what pattern to follow from this file

## Related Work

- PR #123 — relevance to this task

## Applicable Rules

- `rules/xyz.md` — why this rule applies
```

### 7. Present the plan

Show the full plan to the user. Wait for approval, adjustments, or questions before finalizing.

### 8. Hand off

After approval:

1. Confirm the spec folder was written
2. State the first implementation step clearly
3. If the task involves new files, suggest `/scaffold`
4. If an architecture decision was made, suggest `/adr`

## Rules

- Planning is investigation, not implementation. Do not write production code during `/plan`
- Every decision must document at least two alternatives. "Only one way" is rarely true
- Spec folders are permanent artifacts. They record WHY decisions were made for future reference
- The plan must reference specific file paths verified by reading them, not assumed from memory
- If the task is too small for a full plan, say so and suggest proceeding directly
- Search for existing work before designing new solutions. Reuse first
- Spec folders go in `specs/` or `.claude/specs/` within the project, never in `~/.claude/`

## Related skills

- `/adr` — Record significant architecture decisions from the plan
- `/scaffold` — Generate boilerplate after the plan is approved
- `/discover` — Discover existing patterns that inform the plan
- `/assessment` — Audit implementation completeness after the plan is executed
