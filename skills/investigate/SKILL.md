---
name: investigate
description: Systematic debugging with hypothesis testing, bounded retries, and optional edit freeze. Use when user says "debug this", "investigate", "why is this failing", "find the bug", "trace this error", "root cause", or needs structured debugging beyond reading an error message. Do NOT use for incident postmortems (use /incident), code review (use /review), or running tests (use /test).
---

Structured debugging workflow that enforces hypothesis-driven investigation with a hard limit on fix attempts. Prevents the common failure mode of guessing at fixes in a loop.

The full debugging methodology is in `../../rules/debugging.md`. This skill operationalizes it as an interactive workflow.

## Arguments

- No arguments: interactive mode. Ask what the problem is.
- `<description>`: start investigating the described issue.
- `--freeze <path>`: restrict all file edits to the specified directory for the duration of the investigation. Uses the freeze-scope mechanism in `../../hooks/guard/` skill.
- `--unfreeze`: remove any active freeze scope and exit.

## Process

### Phase 1: Reproduce

1. **Understand the symptom.** Ask the user (or read from the description):
   - What is the expected behavior?
   - What is the actual behavior?
   - When did it start? What changed recently?

2. **Find the minimal reproduction.** Run these **in parallel**:
   - `git log --oneline -20` to see recent changes.
   - `git diff HEAD~5 --stat` to identify recently modified files.
   - Search for error messages in the codebase with Grep.

3. **Reproduce the failure.** Run the reproduction steps. If the failure is not reproducible:
   - Check for timing, concurrency, or state dependencies.
   - Ask the user for more context.
   - Do not proceed until the failure is reproducible or the investigation target is clear.

4. **Activate freeze (if requested).** When `--freeze <path>` was passed:
   - Write the target path to `~/.claude/.freeze-scope`.
   - All subsequent edits are restricted to that directory.
   - State the freeze boundary to the user.

### Phase 2: Isolate

1. **Classify the bug type.** Determine which category applies:

   | Category | Indicators |
   |----------|-----------|
   | Code bug | Wrong logic, missing condition, incorrect calculation |
   | Data bug | Unexpected null, wrong type, encoding issue, stale cache |
   | Config bug | Missing env var, wrong setting, environment mismatch |
   | Environment bug | Version difference, OS behavior, dependency conflict |
   | Integration bug | API contract changed, schema mismatch, network timeout |

2. **Narrow the scope.** Use binary search:
   - If multi-component: trace the request path backward from the error boundary.
   - If single-component: read the full error message and stack trace. The root cause is often in the middle, not the top.
   - Check if the bug exists on the default branch. If not, identify the introducing commit.

### Phase 3: Hypothesize and Test

1. **State the hypothesis.** Before changing any code, write:
   - "I believe the bug is caused by [specific cause] in [specific location]."
   - "If this hypothesis is correct, then [specific test input] will produce [specific output]."

2. **Test the hypothesis.** Run the predicted test.
   - If the prediction matches: proceed to Phase 4.
   - If the prediction does not match: **discard the hypothesis entirely**. Do not patch it. Return to step 7 with a new hypothesis.

### Phase 4: Fix (3-Strike Limit)

1. **Attempt the fix.** Apply a single, focused change that addresses the root cause.

2. **Verify the fix.** Run these **in parallel**:
    - The original reproduction steps (must now succeed).
    - The full test suite (must not regress).

3. **Track attempts.** Maintain a running log:

    | Attempt | Hypothesis | Change made | Result |
    |---------|-----------|-------------|--------|
    | 1 | ... | ... | ... |
    | 2 | ... | ... | ... |
    | 3 | ... | ... | ... |

4. **Strike rules:**
    - **Strike 1:** Diagnose why the fix failed. Apply a targeted correction.
    - **Strike 2:** Different approach. The first strategy is wrong. Try an alternative method.
    - **Strike 3:** Broader rethink. Question the assumptions behind all previous attempts. Search for related issues in the codebase, open issues, or documentation.
    - **After 3 strikes:** Stop. Present the attempt log to the user. Explain what was tried, share the specific errors, and ask for guidance. Do not continue guessing.

### Phase 5: Verify and Clean Up

1. **Verify completeness:**
    - The original reproduction steps succeed.
    - A test exists that fails without the fix and passes with it.
    - The full test suite passes.
    - Check for other places where the same pattern exists. Fix them all.

2. **Remove diagnostic instrumentation.** Delete any temporary logging, debug prints, or test scaffolding added during investigation.

3. **Remove freeze (if active).** Delete `~/.claude/.freeze-scope` to restore normal editing scope.

4. **Summary.** State:
    - Root cause (WHY, not just WHERE).
    - Fix applied.
    - How many attempts it took.
    - Whether the same pattern exists elsewhere.

## Rules

- Never apply a fix without first stating a hypothesis and testing it.
- Never apply two changes simultaneously. One change at a time. If you change two things and the bug disappears, you do not know which one fixed it.
- Never fix the symptom. A null check is not a fix if you do not know why the value is null.
- Never relax a checker, linter, or type constraint to make a failure disappear. Fix the code.
- Never proceed past 3 failed fix attempts without user input.
- The hypothesis log (step 11) is mandatory. It prevents repeating failed approaches and gives the user visibility into the investigation.
- When `--freeze` is active, respect the boundary. Do not edit files outside the frozen scope, even if they seem related. If a fix requires changes outside the scope, ask the user to expand or remove the freeze.
- All fix attempts must follow the full completion gates from `../../rules/verification.md`: formatter, tests, linter, build.

## Related skills

- `/test` -- Run the test suite during verification.
- `/incident` -- Document the incident if it was production-impacting.
- `/ship commit` -- Commit the fix after successful investigation.
- `/review` -- Review the fix before shipping.
