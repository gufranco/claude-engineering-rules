---
name: gan
description: Generator-Evaluator iteration loop for building features against a scored rubric. Use when user says "gan", "gan loop", "generator evaluator", "iterate to threshold", "build with feedback loop", or needs an iteration pattern stronger than `/loop` for feature work that has a measurable quality signal. Do NOT use for one-shot implementations (use `/plan` + direct edits), recurring schedules (use `/loop`), or visual design exploration (use `/design variants`).
---

Run a planner → generator → evaluator loop with a score-gated stop condition. The planner expands the brief into acceptance criteria and a rubric. The generator implements against the criteria. The evaluator scores the result, returns feedback. The loop iterates until the score crosses the threshold or the iteration cap is hit.

## When to use

- The output has a measurable quality signal, Playwright test outcome, lint pass, custom rubric.
- The first attempt is unlikely to be the last attempt.
- The cost of running a feedback loop is justified by the quality lift.

## When NOT to use

- One-shot implementations where the spec is unambiguous.
- Recurring schedules. Use the `/loop` built-in.
- Visual design exploration. Use `/design variants`.
- Trivial fixes. Direct edit is faster.

## Arguments

`/gan "<brief>"` is the canonical form. The brief is one or two sentences describing what to build.

Environment variables:

- `GAN_MAX_ITERATIONS` (default 8). Hard cap on planner-generator-evaluator cycles.
- `GAN_PASS_THRESHOLD` (default 8.0). Weighted score 0-10 to consider passing.
- `GAN_EVAL_MODE` (default `playwright`). One of `playwright`, `screenshot`, `code-only`. Determines which evaluator surface runs.
- `GAN_DEV_SERVER_PORT` (default 3000). Port the running app is reachable on.
- `GAN_DEV_SERVER_CMD` (default `pnpm dev`). Command to start the dev server when not already running.

## Subagents

The skill orchestrates three Claude Code agents shipped alongside it:

- [`agents/gan-planner.md`](../../agents/gan-planner.md): expands the brief into acceptance criteria, file list, and a 5-row scoring rubric.
- [`agents/gan-generator.md`](../../agents/gan-generator.md): implements the plan; returns proposed diffs or full file contents, NOT direct writes.
- [`agents/gan-evaluator.md`](../../agents/gan-evaluator.md): scores the implementation against the rubric, returns per-row scores and a verdict.

The orchestrator, this skill, is the sole filesystem writer. Same single-writer invariant as `/plan multi-execute`.

## Process

0. **Pre-flight.**
    - Verify `playwright` is installed when `GAN_EVAL_MODE=playwright`.
    - Verify the dev server is reachable on `GAN_DEV_SERVER_PORT`, start it if not.
    - Initialize `gan-harness/` workspace in the spec folder: `feedback/`, `screenshots/`, `iterations/`.

1. **Plan once.** Spawn `gan-planner` with the brief. Receive:
    - Acceptance criteria as a checklist.
    - File list, paths the implementation will touch.
    - Rubric: 5 rows, each weighted 1-10, total weights sum to 10. Each row names a measurable quality.

2. **Iterate**, cap `GAN_MAX_ITERATIONS`:

    a. **Generate.** Spawn `gan-generator` with the plan, current state, and last iteration's feedback, if any. Generator returns proposed changes as unified diffs.

    b. **Apply.** Orchestrator parses the diffs and writes via Edit / Write / MultiEdit. On apply failure, treat as a generator failure: feed the error back to the generator, retry once, then move on.

    c. **Evaluate.** Spawn `gan-evaluator` against the running app. Evaluator returns:
        - Per-row score 0-10.
        - Weighted total 0-10.
        - Verdict: `ship`, `iterate`, or `abandon`.
        - Concrete feedback per low-scoring row.

    d. **Check stop.** Stop when:
        - Weighted total >= `GAN_PASS_THRESHOLD`. Status: passed.
        - Verdict is `abandon`. Status: aborted by evaluator.
        - Iterations >= `GAN_MAX_ITERATIONS`. Status: budget exhausted.
        - Score has not improved across the last 2 iterations. Status: plateau.

3. **Close.** Write `gan-harness/result.md` with: final score, iteration count, verdict, list of changed files, and a one-paragraph next-step suggestion.

## Single-Writer Invariant (NON-NEGOTIABLE)

`gan-generator` and `gan-evaluator` are briefed: "Return your output as text. Do NOT call Edit, Write, or MultiEdit. Do NOT modify any files." The orchestrator applies. If a subagent ignores the briefing, discard its response and respawn.

## Rules

- Planner runs once. Re-planning mid-loop indicates the rubric was wrong; abort and start a fresh `/gan` instead.
- Apply costs are real. Cap `GAN_MAX_ITERATIONS` at 8 by default; loops past that have diminishing returns.
- Always check `GAN_PASS_THRESHOLD` against the rubric's weighted total, not against any single row.
- The evaluator must run the same evidence path each iteration. Switching from screenshot to Playwright mid-loop invalidates the score history.

## Related skills

- `/plan`. Use first to scope the brief. The plan can be the input to `/gan`.
- `/plan multi-execute`. Different parallelism shape: multi-execute splits one task across model tiers; `/gan` iterates one task through a feedback loop.
- `/test`. The evaluator may call `/test` under the hood when `GAN_EVAL_MODE=code-only`.
- `/loop`. The Claude Code built-in for recurring or self-paced execution. `/gan` is a single-task iteration; `/loop` is a cadence.
