---
name: plan
description: Plan implementations, record architecture decisions, and scaffold boilerplate. Subcommands: plan (default), adr, scaffold. Creates spec folders, manages ADRs, and generates files from existing project patterns. Use when user says "plan this", "how should I implement", "design this feature", "create an ADR", "scaffold a service", "architecture decision", or needs to think through an approach before coding. Do NOT use for code review (use /review), shipping (use /ship), or running tests (use /test).
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
- `--discover`: run a structured discovery session before planning (see Discovery Phase below).
- `--auto`: run discovery, scope review, and engineering review automatically. Surface only decisions that need human input. Skip interactive approval between phases.

### Discovery Phase (when `--discover` or `--auto` is passed)

Before step 1, run a structured discovery session. Ask these six forcing questions, one at a time:

1. **Problem.** What problem does this solve? Who has it today? How do they work around it?
2. **User.** Who is the user? What is their workflow before and after this feature?
3. **Success.** What does success look like? How will you measure it?
4. **Scope.** What is the minimum viable scope? What can be deferred?
5. **Risk.** What are the biggest risks? Technical, product, timeline.
6. **Alternatives.** What existing solutions did you consider? Why are they insufficient?

Record the answers in the spec folder's `decisions.md` under a "Discovery" heading.

### Scope Review (when `--auto` is passed, runs after discovery)

Challenge the scope with four lenses before proceeding to architecture:

| Lens | Question |
|------|----------|
| Expansion | What is missing that users will expect? What adjacent features add outsized value? |
| Selective expansion | Which additions have the best effort-to-impact ratio? |
| Hold | Is the scope right as-is? Does every item justify its cost? |
| Reduction | What can be cut without losing core value? What is nice-to-have masquerading as must-have? |

Present the scope review findings. In `--auto` mode, only pause for user input if the review suggests changes. If the scope is clean across all four lenses, proceed.

### Process

1. **Clarify scope.** One question at a time. What is being built? Expected outcome? Constraints? (Skip if discovery phase already covered this.)

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

7. **Append mandatory closing gates.** Every `plan.md` task breakdown must end with these two items, in this order, as the final tasks. They are not optional. They cannot be moved earlier or removed.

   **Gate 1: Test Coverage (95%+).** Apply `../../checklists/checklist.md` category 8 (Testing). Every file changed or directly related to the changes must reach 95%+ coverage across all applicable test types. "Related" means: files that import from, are imported by, or share a data contract with a changed file. Run the coverage tool scoped to changed files. If any file is below 95%, write the missing tests before proceeding.

   **Gate 2: Clean Room Verification.** Apply `../../checklists/checklist.md` category 50 (Clean Room). Run all checks from sections A through E against every file produced by this plan. If no external sources were consulted, state that explicitly and skip. Full process and remediation steps: `rules/clean-room.md`.

8. **Present plan.** Wait for approval.

9. **Hand off.** Confirm spec written. State first step. Suggest `/plan scaffold` if new files needed. Suggest `/plan adr` if architecture decision was made.

### Research Discipline

These rules apply during steps 2-4 and any research, spike, or exploration phase. They prevent context loss during long investigative sessions.

**2-action rule.** After every two search, read, or browse operations, persist key findings to `references.md` in the spec folder before continuing. Do not accumulate findings only in context. Multimodal content like screenshots, PDF contents, or browser output must be captured as text immediately because it does not survive context compaction.

**Read before decide.** Re-read `plan.md` before any major decision. After ~50 tool calls, the original goal drifts out of the attention window. Re-reading pushes it back in. This applies to implementation too: before starting a new phase, re-read the plan.

**Never repeat failures.** If an action failed, the next action must be different. Track every failed attempt with its error in `decisions.md` using this format:

| Attempt | What was tried | Error | Next action |
|---------|---------------|-------|-------------|
| 1 | ... | ... | ... |

Failed approaches are valuable context. Keep them visible so the model updates its beliefs rather than retrying the same path.

### 3-Strike Error Protocol

When an approach fails during planning or research:

1. **Strike 1: Diagnose and fix.** Read the error. Identify root cause. Apply a targeted fix.
2. **Strike 2: Alternative approach.** Same error? Try a different method, tool, or data source. Never repeat the exact same failing action.
3. **Strike 3: Broader rethink.** Question the assumptions behind the approach. Search for solutions. Consider updating the plan's approach entirely.
4. **After 3 strikes: Escalate.** Explain what was tried, share the specific errors, and ask for guidance. Do not continue guessing.

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

1. Show draft, incorporate feedback, write file.
2. For supersession: update original status to `superseded by ADR-NNN`, link from new ADR.

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

- `/design` -- Design consultation before planning UI features.
- `/review` -- Review code quality after implementing the plan.
- `/ship` -- Ship the implementation.
- `/deploy` -- Merge and deploy after shipping.
- `/assessment` -- Audit completeness after plan execution.
