---
name: plan
description: Plan implementations, record architecture decisions, and scaffold boilerplate. Subcommands: plan (default), adr, scaffold. Creates spec folders, manages ADRs, and generates files from existing project patterns. Use when user says "plan this", "how should I implement", "design this feature", "create an ADR", "scaffold a service", "architecture decision", or needs to think through an approach before coding. Do NOT use for code review (use /review), shipping (use /ship), or running tests (use /test).
argument-hint: "/plan <feature> | /plan adr new <title> | /plan scaffold <type> <name> | /plan to-issues | /plan multi-execute <task>"
allowed-tools: "Read, Grep, Glob, Write, Edit, Bash, AskUserQuestion, WebFetch, WebSearch"
user-invocable: true
sensitive: true
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
| `/plan to-issues` | Export the active spec folder's task breakdown to GitHub issues |
| `/plan multi-execute <task>` | Plan and execute under a single-writer protocol with parallel model tiers |
| `/plan archive` | Merge a completed change's spec delta into the living spec and stamp the plan folder archived |

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

**Optional research step.** If the task touches a domain with active community discussion, public competitors, or external prior art, run `/research <topic>` and link the output in the spec folder's `references.md`. The research skill enforces entity resolution, citation discipline, and confidence scoring. This step is user-initiated, not automatic. Skip when the task is purely internal.

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

The steps below are enablers, not gates. Their order shows what becomes possible next, not a one-way waterfall. Discovery, scope review, alternatives, and the plan itself are revisitable at any time: if implementation reveals the design was wrong, reopen the relevant artifact and update it rather than forcing the original plan through. The dependencies exist so each step has the context the next one needs, not to lock the work.

0. **Context snapshot.** Before anything else, write `context.md` in the spec folder:

   ```markdown
   # Context Snapshot
   **Created:** <YYYY-MM-DD HH:MM GMT>

   ## Task
   <Task statement from user input, verbatim>

   ## Desired Outcome
   <What success looks like, in one sentence>

   ## Known Facts
   - <Fact from user input or codebase>

   ## Constraints
   - <Time, tech, scope, or resource constraints>

   ## Unknowns
   - <Questions that need answers before implementation>

   ## Codebase Touchpoints
   - <Files or modules likely to change>

   ## Branch State
   - Branch: <current branch>
   - Recent commits: <last 3 commit subjects>
   ```

   This snapshot prevents context drift in long sessions. Re-read `context.md` at the start of each phase, steps 1, 5, 8. If the task has evolved, update the snapshot before continuing.

1. **Clarify scope.** One question at a time. What is being built? Expected outcome? Constraints?. Skip if discovery phase already covered this.

2. **Search for existing work**. The tool ordering is mandatory; stop at first match:
   1. Local codebase: `rg -i "<keyword>"`, including file names. Cover [`skills/`](../../skills), [`agents/`](../../agents), [`rules/`](../../rules), [`standards/`](../../standards), [`hooks/`](../../hooks) when the new work could land in `~/.claude/`.
   2. Open PRs: `gh pr list --search "<keywords>"`.
   3. Recent branches: `git branch -a --list "*<keyword>*"`.
   4. Closed PRs: `gh pr list --state closed --search "<keywords>"`. A closed PR often names a dead-end or a postponed approach.
   5. GitHub code search: `gh search code "<keywords>" --language=<lang>`.
   6. Library docs: `llms.txt` first, then official docs of the major library in the area.
   7. Package registry: `npm search`, `pip search`, `cargo search`, `gem search`.
   8. Web search: last resort, only if 1-7 turned up nothing.

   **Anti-duplication gate for skills, agents, hooks, standards, rules.** Before proposing a new file in `~/.claude/skills/`, `~/.claude/agents/`, `~/.claude/hooks/`, `~/.claude/standards/`, or `~/.claude/rules/`, run steps 1-2 against `~/.claude/` and the [`rules/index.yml`](../../rules/index.yml) on-demand entries first. Prefer extending an existing file, new subcommand, new section, new mode, over creating a new one. Justify the new file in writing when no extension fits. See [`rules/pre-flight.md`](../../rules/pre-flight.md) for the full rule.

3. **Gather references.** Identify 2-5 files following patterns the new code should match. Read them. Note structure, naming, error handling, testing.

4. **Match relevant rules.** Read [`rules/index.yml`](../../rules/index.yml). Match top 3-5 rules by triggers. Read them.

5. **Evaluate alternatives.** For non-trivial decisions, 2-3 approaches with trade-offs, risk level, and recommendation. For each:
   - **Decisive test**: smallest experiment to confirm/invalidate.
   - **Stop signal**: what result means the approach is wrong.
   - **Pivot trigger**: when to switch to next-best alternative.
   Present for approval. Suggest `/plan adr new` for significant decisions.

6. **Create spec folder:**
   ```
   specs/<YYYY-MM-DD>-<slug>/
     plan.md        (goal, approach, requirements, task breakdown, risks, validation)
     decisions.md   (context, options, chosen with reasoning)
     references.md  (patterns, related work, applicable rules)
   ```

   For a non-trivial change, `plan.md` carries a **Requirements** section before the task breakdown. Each requirement is one observable behavior stated with a normative keyword, and each carries at least one Given/When/Then scenario. See [`rules/living-specs.md`](../../rules/living-specs.md) for the format and [`rules/normative-keywords.md`](../../rules/normative-keywords.md) for keyword strength. These requirements are the plan's acceptance criteria: each scenario maps to a row in the test traceability matrix (Gate 1) and feeds the 95% coverage gate. The `test-scenario-generator` agent reads this section when present.

   ```markdown
   ## Requirements

   ### Requirement: <one observable behavior, one MUST/SHALL/SHOULD>
   #### Scenario: <names the case>
   - GIVEN <precondition>
   - WHEN <action>
   - THEN <expected, checkable outcome>
   ```

   **Living-spec delta.** When the change touches behavior already covered by a `specs/current/` spec, `plan.md` also carries a delta section against that spec using `## ADDED Requirements`, `## MODIFIED Requirements`, and `## REMOVED Requirements`. Describe the diff, not the whole spec. If the project has no `specs/current/` yet and the change is non-trivial, seed it with only the requirements this change establishes. Full delta discipline and the triviality boundary: [`rules/living-specs.md`](../../rules/living-specs.md). This is the spec-level analogue of [`rules/surgical-edits.md`](../../rules/surgical-edits.md).

7. **Append mandatory closing gates.** Every `plan.md` task breakdown must end with these two items, in this order, as the final tasks. They are not optional. They cannot be moved earlier or removed.

   **Gate 1: Test Coverage, 95%+.** Apply [`../../checklists/checklist.md`](../../checklists/checklist.md) category 8, Testing. Every file changed or directly related to the changes must reach 95%+ coverage across all applicable test types. "Related" means: files that import from, are imported by, or share a data contract with a changed file. Run the coverage tool scoped to changed files. If any file is below 95%, write the missing tests before proceeding.

   **Gate 2: Clean Room Verification.** Apply [`../../checklists/checklist.md`](../../checklists/checklist.md) category 50, Clean Room. Run all checks from sections A through E against every file produced by this plan. If no external sources were consulted, state that explicitly and skip. Full process and remediation steps: `rules/clean-room.md`.

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

## archive

Fold a completed change's spec delta into the living spec, then stamp the plan folder archived. This is the step that keeps `specs/current/` from going stale. It owns the shared merge routine that `/ship` and `/retro` also call, so the result is identical from any entry point, per the delivery-path-consistency rule in [`rules/code-style.md`](../../rules/code-style.md).

### When to use

- After the tasks in a plan folder are implemented, verified, and merged.
- When `/ship` or `/retro` prompts to close out a change that has a `specs/current/` delta.

### Arguments

- No arguments: resolve the most recent plan folder under `specs/` that has an unmerged delta.
- `<spec-folder>`: explicit path to the plan folder to archive.
- `--dry-run`: print the merge that would happen without writing.

### Steps

1. **Resolve the plan folder** and read its `plan.md` delta sections (`ADDED`, `MODIFIED`, `REMOVED`). If the plan has no delta and no `Requirements` section, there is nothing to merge; only stamp it archived.
2. **Locate the target spec** under `specs/current/<domain>/spec.md` for each requirement. Create the domain spec if the delta is all `ADDED` and no spec exists yet.
3. **Idempotency check.** For each delta requirement, compare against the current spec. If it is already merged (ADDED requirement already present with identical text, MODIFIED already applied, REMOVED already absent), skip it and report a no-op. Re-running a completed archive must change nothing.
4. **Name the target before writing.** For every MODIFIED and REMOVED requirement, state which requirement in the current spec it replaces or deletes, per the destructive-action discipline in [`rules/code-style.md`](../../rules/code-style.md). In `--dry-run`, stop here and print the plan.
5. **Apply the merge.** ADDED appended to the domain spec, MODIFIED replaces the prior requirement in place, REMOVED deleted with the reason recorded in `decisions.md`.
6. **Stamp archived.** Add an `Archived: <YYYY-MM-DD>` line to the plan folder's `plan.md` header. The plan folder stays in place, dated and permanent; only the living spec moves forward.
7. **Report.** Table of merged requirements per domain, plus any skipped no-ops.

### Rules

- Idempotent. Re-running on an already-merged delta is a no-op, never a duplicate append.
- Never rewrite a whole spec. Apply only the delta.
- Never delete the plan folder. It records why; the living spec records what.
- The merge logic lives here. `/ship` and `/retro` invoke it, never reimplement it.

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

## to-issues

Export the active spec folder's task breakdown to GitHub issues. One issue per task.

### When to use

- After a `/plan` run, when the work will be tracked in GitHub issues.
- When handing off a plan to a teammate or queue.

### Arguments

- No arguments: read the most recent spec folder under `specs/` or `.claude/specs/`.
- `<spec-folder>`: explicit path to the spec folder.
- `--label <name>`: label to apply to every created issue. Repeatable.
- `--milestone <name>`: milestone to assign to every issue.
- `--dry-run`: print the issue payloads without creating them.

### Steps

1. **Resolve spec folder.** Default to the latest folder under `specs/` or `.claude/specs/`.
2. **Read `plan.md`.** Parse the Task Breakdown section. Each numbered task becomes one issue.
3. **Detect platform and account.** GitHub or GitLab from `git remote get-url origin`. Resolve account per [`standards/borrow-restore.md`](../../standards/borrow-restore.md).
4. **Idempotency check.** For each task, search existing issues by title prefix. Skip if a match exists.
5. **Build issue body.** Include: the task description, the spec folder path, a link to `plan.md`, and any phase grouping.
6. **Create issues.** GitHub: `GH_TOKEN=$(gh auth token --user <account>) gh issue create --title "<title>" --body-file <tmp> --label <label>`. GitLab: equivalent `glab issue create`.
7. **Print summary.** Table of created issues with URLs. Skipped, duplicate issues listed separately.

### Rules

- Idempotent. Re-running must not create duplicates.
- Issue title must include the task number from `plan.md` for traceability.
- Body must link back to the spec folder so context is one click away.
- Never create issues from a `--light` plan with no task breakdown.
- Never push or commit. This subcommand only writes to the issue tracker.

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
2. **Detect framework and find examples**, parallel: read manifest, map directory structure, search for existing examples of the type.
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

## multi-execute

Plan and execute a feature with parallel model tiers, Opus + Sonnet + Haiku, while keeping the running Claude Code session as the **sole filesystem writer**. Subagents propose; the orchestrator integrates and writes.

### When to use

- Feature is large enough to benefit from a planner-reviewer split.
- Cost matters: route deep reasoning to Opus, broad searches to Sonnet, mechanical tasks to Haiku.
- The risk of two writers conflicting on the same files is non-trivial.

### When NOT to use

- Small change, 1-3 files. Overhead exceeds value.
- Time-critical hotfix. Use `/hotfix`.
- The task is purely deterministic, rename, format, refactor. Use `/refactor`.

### Single-Writer Invariant (NON-NEGOTIABLE)

Only the running Claude Code session writes to disk. Subagents return text. The orchestrator parses, validates, and applies.

| Role | Tools | Writes? |
|------|-------|---------|
| Orchestrator (this session) | All tools | YES |
| Planner subagent | Read, Grep, Glob, WebSearch | NO |
| Generator subagents | Read, Grep, Glob | NO |
| Reviewer subagents | Read, Grep, Glob | NO |

Subagents must be briefed with: "Return your proposed changes as unified diffs or full-file content in your response. Do NOT call Edit, Write, or MultiEdit." Violations are a wasted run.

### Process

1. **Plan with Opus.** Spawn a planner subagent, Opus tier to produce the task breakdown. Single agent, single pass.
2. **Decompose.** Split the plan into chunks small enough for parallel generation, one chunk = one file or one cohesive change.
3. **Generate in parallel.** Spawn generator subagents, Sonnet tier at most two at a time per the Parallelism Rule. Each receives one chunk plus the file content. Returns proposed text.
4. **Review in parallel.** Spawn reviewer subagents, Sonnet tier on the proposed changes. Returns approval or rejection with rationale.
5. **Integrate.** The orchestrator applies the approved changes with Edit / Write / MultiEdit. Conflicts between proposals get re-planned, back to step 2 for the conflicting subset.
6. **Verify.** Run formatter + linter + test suite. Show output.

### Cost discipline

- Planner: Opus, 1 call.
- Generator: Sonnet, N calls where N is the number of independent chunks. Cap at 6.
- Reviewer: Sonnet, N calls matching the generators.
- Orchestrator integration: this session.

Estimate cost before running. Abort and run a simpler `/plan` flow when the cost exceeds the marginal benefit of parallelism.

### Rules

- Single-writer invariant is enforced by the briefing, not by the runtime. Audit subagent responses: if any names a write tool, discard the response.
- Generator chunks must not overlap on the same file. The decomposition step is responsible for partitioning.
- Reviewer subagents read the proposal, not the diff. Diffs hide context.
- Failed verification rolls back the orchestrator's writes, `git stash` before re-planning.

---

## Rules

- Planning is investigation, not implementation. Do not write production code during `/plan`.
- Every decision must document at least two alternatives.
- Plan folders are permanent and dated. They record WHY decisions were made. The living spec under `specs/current/` records WHAT the system does now and is maintained by `/plan archive`. See [`rules/living-specs.md`](../../rules/living-specs.md).
- The plan must reference verified file paths.
- Search for existing work before designing new solutions.
- Spec folders go in `specs/` or `.claude/specs/` within the project, never in `~/.claude/`.

## Related skills

- `/design` -- Design consultation before planning UI features.
- `/review` -- Review code quality after implementing the plan.
- `/ship` -- Ship the implementation.
- `/deploy` -- Merge and deploy after shipping.
- `/assessment` -- Audit completeness after plan execution.
