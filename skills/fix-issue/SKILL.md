---
name: fix-issue
description: Fix a GitHub issue by number. Fetches the issue, analyzes requirements, searches the codebase, implements the fix with tests, and commits referencing the issue. Use when user says "fix issue #N", "fix #N", "resolve issue N", "close issue N", or wants to implement a fix for a specific GitHub issue. Do NOT use for general debugging without an issue (use /investigate), code review (use /review), or feature planning (use /plan).
---

End-to-end workflow for resolving a GitHub issue: from reading the issue to committing a tested fix.

## Arguments

- `<number>` (required): the GitHub issue number to fix.
- `--dry-run`: analyze and propose a fix without implementing.

## Process

### Phase 1: Understand

1. **Fetch the issue.** Run:
   ```bash
   GH_TOKEN=$(gh auth token --user <account>) gh issue view <number> --json title,body,labels,assignees,comments
   ```
   Determine the account from the git remote URL using the mapping in `../../rules/github-accounts.md`.

2. **Parse requirements.** Extract from the issue:
   - What is broken or missing.
   - Reproduction steps, if provided.
   - Acceptance criteria, if stated.
   - Labels that indicate priority or category.

3. **Classify the issue.** Determine the type:

   | Type | Indicators |
   |------|-----------|
   | Bug | "error", "crash", "broken", "regression", reproduction steps |
   | Feature | "add", "implement", "support", "new" |
   | Improvement | "refactor", "optimize", "clean up", "improve" |
   | Documentation | "docs", "readme", "update documentation" |

### Phase 2: Pre-Flight

Run the pre-flight checks from `../../rules/pre-flight.md`:

1. **Duplicate check.** Search for existing fixes:
   - `gh pr list --search "<keywords from issue>"` for open PRs.
   - `gh pr list --state closed --search "<keywords>"` for already-resolved PRs.
   - `git branch -a --list "*<keyword>*"` for in-progress branches.

2. **Codebase search.** Find relevant code:
   - Grep for error messages, function names, or keywords from the issue.
   - Read the files that are likely involved.
   - Identify the module and layer where the fix belongs.

3. **Interface verification.** Read the signatures, types, and contracts of every function or API the fix will touch.

4. **Root cause confirmation** (bugs only). Follow `../../rules/debugging.md`:
   - Reproduce the bug.
   - State the root cause: WHY, not just WHERE.
   - Predict what a test input will produce.

### Phase 3: Implement

1. **Create a branch.** Name it `bugfix/<number>-<short-description>` for bugs, `feature/<number>-<short-description>` for features.

2. **Implement the fix.** Follow `../../rules/code-style.md` for all code written.

3. **Write tests.** Every fix must have tests that:
   - Fail without the fix and pass with it (for bugs).
   - Cover the new behavior including edge cases (for features).
   - Meet 95%+ coverage on changed files.

4. **If `--dry-run`:** stop here. Present the proposed approach, affected files, and test plan. Do not write code.

### Phase 4: Verify

Run the full completion gates from `../../rules/verification.md`:

1. Formatter. Show output.
2. Linter. Zero warnings, zero errors. Show output.
3. Type checker. Zero errors. Show output.
4. Test suite. All pass. Show output.
5. Build. Clean, zero warnings. Show output.

### Phase 5: Commit

1. **Commit the fix.** Use the format from `../../rules/git-workflow.md`:
   ```
   fix(<scope>): <description>

   <body explaining what and why>

   Fixes #<number>
   ```

2. **Summary.** State:
   - Root cause or rationale.
   - Files changed.
   - Tests added.
   - Verification evidence.

## Rules

- Never implement without reading the issue first. The issue is the source of truth for requirements.
- Never skip pre-flight. An existing fix or PR for the same issue makes this work redundant.
- For bugs, reproduce before fixing. A fix without reproduction is a guess.
- The commit footer must reference the issue with `Fixes #N` so GitHub auto-closes it on merge.
- Account token prefixing is mandatory for all `gh` commands per `../../rules/github-accounts.md`.
- All code must follow `../../rules/code-style.md`. Existing violations in the codebase are not permission to add more.

## Related Skills

- `/investigate` -- Deep debugging when the root cause is unclear.
- `/test` -- Run the test suite during verification.
- `/ship pr` -- Create a PR after committing the fix.
- `/review` -- Self-review the fix before shipping.
