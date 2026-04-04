---
name: refactor
description: Guided refactoring with behavior preservation verification. Identifies candidates (long functions, deep nesting, duplicated logic, god classes), proposes a refactoring plan, executes incrementally with tests between steps, and verifies no behavior change. Use when user says "refactor", "clean up this code", "simplify", "extract", "restructure", "reduce complexity", "split this file", or wants to improve code structure without changing behavior. Do NOT use for new features (use /plan), bug fixes (use /investigate), or code review (use /review).
---

Incremental refactoring workflow that enforces behavior preservation at every step. Each refactoring is a separate commit with test verification before and after.

The refactoring principles follow `../../rules/code-style.md`. This skill provides the execution workflow.

## Arguments

- No arguments: analyze the current branch diff for refactoring candidates.
- `<path>`: refactor the specified file or directory.
- `--plan-only`: identify and rank candidates without executing any changes.

## Process

### Phase 1: Establish Baseline

1. **Run the full test suite.** Record the result. If tests fail, stop. Do not refactor code with a failing test suite. The user must fix tests first.

2. **Record coverage.** If a coverage tool is configured, record the current coverage numbers for affected files. Coverage must not decrease after refactoring.

### Phase 2: Identify Candidates

Scan the target files for refactoring candidates. Check each category:

| Category | Threshold | Refactoring |
|----------|-----------|-------------|
| Long functions | >30 lines | Extract function |
| Deep nesting | >3 levels | Guard clauses, early returns |
| Duplicated blocks | >5 lines appearing 2+ times | Extract shared function |
| Large files | >300 lines | Split by responsibility |
| God classes | >7 public methods | Split into focused classes |
| Long parameter lists | >4 parameters | Extract options object |
| Circular imports | Any cycle | Restructure module boundaries |
| Dead code | Unreachable branches, unused exports | Remove |
| Primitive obsession | Repeated string/number with domain meaning | Extract type or enum |
| Feature envy | Function using more of another module's data than its own | Move to the correct module |

### Phase 3: Rank and Present

Rank candidates by impact score: lines affected multiplied by complexity reduction. Present as a table:

| Priority | File | Line | Issue | Proposed refactoring | Impact |
|----------|------|------|-------|---------------------|--------|
| 1 | ... | ... | ... | ... | High |
| 2 | ... | ... | ... | ... | Medium |

If `--plan-only` was passed, stop here.

### Phase 4: Execute Incrementally

For each approved candidate, in priority order:

1. **Describe the change.** State what will change and what will stay the same.
2. **Predict the test outcome.** All existing tests must continue to pass with no modifications.
3. **Apply the refactoring.** One structural change at a time.
4. **Run tests.** If tests fail:
   - Revert the change.
   - Analyze why the refactoring broke tests. If the tests were testing implementation details rather than behavior, note this as a separate finding.
   - Try an alternative approach.
   - If the alternative also fails, skip this candidate and move to the next.
5. **Run linter and type checker.** Fix any new warnings introduced by the refactoring.
6. **Commit.** One commit per refactoring step:
   - `refactor(scope): extract validateInput from processOrder`
   - `refactor(scope): flatten nested conditionals in AuthService`
   - `refactor(scope): remove duplicate price calculation`

### Phase 5: Final Verification

1. Run the full test suite. All tests pass.
2. Run the linter. Zero warnings.
3. Run the type checker. Zero errors.
4. Run the build. Clean build.
5. Compare coverage. Coverage is equal to or higher than the baseline.
6. Review the full diff. Confirm no behavior changes leaked in.

## Rules

- Never change behavior. A refactoring that alters what the code does is a bug, not a refactoring.
- Never combine refactoring with feature work in the same commit. Structure changes and behavior changes are separate commits.
- Never modify test assertions during refactoring. If a test breaks, the refactoring changed behavior.
- One refactoring per commit. If a commit does two things, split it.
- Revert immediately when tests fail. Do not debug a failed refactoring for more than 5 minutes. Try a different approach or skip the candidate.
- Do not refactor code you do not understand. Read the function, its callers, and its tests before touching it.

## Related skills

- `/review` -- Review the refactoring diff before shipping.
- `/test` -- Run the test suite during verification.
- `/ship commit` -- Commit each refactoring step.
- `/investigate` -- Debug if a refactoring unexpectedly changes behavior.
