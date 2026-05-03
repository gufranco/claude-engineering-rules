---
name: tdd
description: Red-green-refactor TDD loop for a single behavior. Writes a failing test first, runs it to confirm red, implements minimum code to make it green, then refactors with the test as a safety net. Use when user says "tdd", "test first", "red green refactor", "write the test first", or wants a disciplined test-first cycle. Do NOT use for bulk test backfill (use /test), debugging existing failures (use /investigate), or planning a feature (use /plan).
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
---

Red-green-refactor loop. One behavior at a time. The test must fail before any production code is written.

## Arguments

- `<description>`: the behavior to implement, in plain English. Example: `/tdd user.create rejects empty email`.
- `--no-refactor`: skip the refactor step. Useful when the green code is already minimal.

## Process

### 1. Clarify the behavior

State the behavior in one sentence. If it covers more than one assertion, split into multiple `/tdd` runs. One behavior, one test.

Identify:
- The function or class under test.
- The input that triggers the behavior.
- The expected observable outcome (return value, thrown error, side effect).

If any of the three is unclear, ask one question and stop.

### 2. Locate or create the test file

Match the project's test colocation pattern. Read 2 nearby tests to confirm:
- Naming convention (`*.test.ts`, `*_test.go`, `test_*.py`).
- Test runner imports.
- Setup and teardown style.
- Fake data approach. Apply `rules/testing.md` Test Data section.

Add the test file if missing. Match the existing folder layout exactly.

### 3. Red: write the failing test

- Use the AAA comment pattern from `rules/testing.md`. Three markers, no other comments in the test body.
- Use the most specific assertion available. No `toBeTruthy`. Apply the Assertion Specificity table.
- Seed any fake data generator deterministically.

Run the single test. Confirm it fails.

| Failure type | What it means |
|--------------|---------------|
| Assertion failure | Expected. Proceed to step 4 |
| Compile or import error | Test setup is wrong. Fix before continuing |
| Test passes | The behavior already exists, or the test does not exercise it. Stop and reassess |

### 4. Green: minimum production code

Write the smallest change that makes the test pass. Resist the urge to add nearby features, generalize, or refactor at this step.

- No new error handling beyond what the test asserts.
- No new abstractions.
- No "while I'm here" cleanup.
- Stay surgical. See `rules/surgical-edits.md`.

Run the test. Confirm it passes. Run the full test file to confirm no regressions on neighbors.

### 5. Refactor: improve with the test as safety net

Skip if `--no-refactor` was passed.

Look for:
- Duplication introduced in step 4.
- Names that no longer match the new behavior.
- Functions that grew past the file's typical size.

Run the full test file after every refactor change. The bar is zero failing tests, zero new warnings.

### 6. Verify gates

- Format, lint, typecheck, full test suite. Apply `rules/git-workflow.md` Local Quality Gate.
- Coverage for the changed file at 95% or higher. Apply `rules/testing.md` Coverage section.

Report a one-line summary: behavior implemented, test name, files changed, coverage on changed file.

## Anti-patterns

- Writing production code before the failing test. The whole point is the red step proves the test exercises the behavior.
- Writing a test that passes on the first run. The test is not measuring what you think.
- Adding multiple assertions for unrelated behaviors in one test. Split into separate `/tdd` runs.
- Skipping the refactor step on every cycle. The codebase decays without it.
- Mocking internal infrastructure to make the test cheap. Apply `rules/testing.md` Mocks Policy.

## Rules

- One behavior per cycle. No exceptions.
- Test must fail before production code is written. No exceptions.
- The green step writes the minimum. Generalization belongs in refactor or in a later cycle.
- Use the project's real test infrastructure. Never mock the database, queue, or your own services.
- Apply existing rules: `rules/testing.md`, `rules/surgical-edits.md`, `rules/git-workflow.md`.

## Related skills

- `/test` for running the suite, coverage, lint, scan.
- `/investigate` for debugging an existing failure rather than writing a new test.
- `/plan` for designing a feature before any TDD cycle starts.
