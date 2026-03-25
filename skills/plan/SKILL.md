---
name: plan
description: Plan implementations, record architecture decisions, and scaffold boilerplate. Subcommands: plan (default), adr, scaffold. Creates spec folders, manages ADRs, and generates files from existing project patterns.
---

Unified planning skill for requirements gathering, architecture decisions, and code generation. Replaces standalone `/plan`, `/adr`, and `/scaffold` skills.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/plan` or `/plan <description>` | Create implementation plan (default) |
| `/plan adr` | List existing ADRs |
| `/plan adr new <title>` | Create a new ADR |
| `/plan adr supersede <number> <title>` | Supersede an existing ADR |
| `/plan scaffold <type> <name>` | Generate boilerplate from project patterns |

If no subcommand is recognized, treat the argument as a plan description.

---

## plan (default)

Gather requirements, search for existing solutions, evaluate trade-offs, and produce a structured implementation plan saved to a spec folder.

### When to use

- Before implementing any feature touching 3+ files or involving architectural decisions.
- When evaluating multiple approaches.
- Before refactoring that changes module boundaries.

### Arguments

- No arguments: interactive planning mode.
- `<description>`: start planning with the given task.
- `--light`: abbreviated plan without references or trade-off analysis. Produces `plan.md` only.
- `--resume`: continue from the most recent spec folder.

### Process

1. **Clarify scope.** One question at a time. What is being built? Expected outcome? Constraints?

2. **Search for existing work** (parallel):
   - Grep codebase for related patterns.
   - `gh pr list --search "<keywords>"` for open PRs.
   - `git branch -a --list "*<keyword>*"` for branches.
   - `gh pr list --state closed --search "<keywords>"` for prior attempts.

3. **Gather references.** Identify 2-5 files following patterns the new code should match. Read them. Note structure, naming, error handling, testing.

4. **Match relevant rules.** Read `rules/index.yml`. Match top 3-5 rules by triggers. Read them.

5. **Evaluate alternatives.** For non-trivial decisions, 2-3 approaches with trade-offs, risk level, and recommendation. For each:
   - **Decisive test**: smallest experiment to confirm/invalidate.
   - **Stop signal**: what result means the approach is wrong.
   - **Pivot trigger**: when to switch to next-best alternative.
   Present for approval. Suggest `/plan adr new` for significant decisions.

6. **Create spec folder:**
   ```
   specs/<YYYY-MM-DD>-<slug>/
     plan.md        (goal, approach, task breakdown, risks, validation)
     decisions.md   (context, options, chosen with reasoning)
     references.md  (patterns, related work, applicable rules)
   ```

7. **Present plan.** Wait for approval.

8. **Hand off.** Confirm spec written. State first step. Suggest `/plan scaffold` if new files needed. Suggest `/plan adr` if architecture decision was made.

---

## adr

Create and manage Architecture Decision Records. ADRs capture context, alternatives, and reasoning behind significant technical decisions.

### When to use

- After a non-trivial architecture decision.
- When changing or reversing a previous decision.
- During planning when a decision deserves its own record.

### Subcommands

- No arguments: list existing ADRs.
- `new <title>`: create interactively.
- `supersede <number> <title>`: create new ADR that supersedes existing.
- `--status <status>`: filter by proposed/accepted/deprecated/superseded.

### Process

1. Locate or create `docs/adr/`. Files: `NNN-<slug>.md`, zero-padded.
2. For new ADRs, ask one question at a time: what decision? What problem? What alternatives?
3. Draft:

```markdown
# ADR-NNN: <Title>

**Status:** accepted
**Date:** <YYYY-MM-DD>

## Context
## Decision
## Alternatives Considered
### <Alt 1> -- pros, cons
### <Alt 2> -- pros, cons
## Consequences
### Positive
### Negative
### Risks
```

4. Show draft, incorporate feedback, write file.
5. For supersession: update original status to `superseded by ADR-NNN`, link from new ADR.

### Rules

- ADRs are append-only. Never delete superseded ones.
- At least two alternatives documented.
- Status values: proposed, accepted, deprecated, superseded by ADR-NNN.
- Title describes the decision, not the problem.

---

## scaffold

Generate boilerplate by reading existing project patterns. No external generators, everything derived from the codebase.

### When to use

- Creating a new endpoint, service, component, module, or model.
- When new code must match existing style.

### Arguments

`<type> <name>` where type is a project pattern: `endpoint`, `service`, `component`, `module`, `model`, `controller`, `middleware`, `hook`.

### Steps

1. Parse type and name. If missing, list available types and ask.
2. **Detect framework and find examples** (parallel): read manifest, map directory structure, search for existing examples of the type.
3. Analyze 2-3 examples: naming convention, export style, imports, code structure, test file location, TypeScript patterns.
4. Generate: main file + test file following exact patterns. Placeholder `TODO` comments for business logic.
5. Present for approval before writing.
6. Write files. Update barrel exports if applicable.

### Rules

- Always read existing code to derive patterns.
- Always present for approval before writing.
- Match exact naming, export style, imports.
- Never generate without at least one example.
- Never install dependencies.
- Keep generated code minimal: skeleton with TODOs.

---

## Rules

- Planning is investigation, not implementation. Do not write production code during `/plan`.
- Every decision must document at least two alternatives.
- Spec folders are permanent. They record WHY decisions were made.
- The plan must reference verified file paths.
- Search for existing work before designing new solutions.
- Spec folders go in `specs/` or `.claude/specs/` within the project, never in `~/.claude/`.

## Related skills

- `/review` -- Review code quality after implementing the plan.
- `/ship` -- Ship the implementation.
- `/assessment` -- Audit completeness after plan execution.
