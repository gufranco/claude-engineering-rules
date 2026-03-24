# Verification

## Core Rule

No completion claims without fresh verification evidence. Previous runs, cached results, and "it should work" are not evidence.

## Gate Function

Before declaring any task complete:

1. **Identify** what proves the claim. What command, test, or check would fail if the work were wrong?
2. **Run** it. In the current session, right now.
3. **Read** the output. The full output, not just the exit code.
4. **Verify** the output matches the expected result.
5. **Only then** claim the task is done.

## What Counts as Evidence

| Claim | Required evidence |
|-------|------------------|
| "Tests pass" | Test command output showing 0 failures, run in this session |
| "Build succeeds" | Build command output with no errors, run in this session |
| "Lint is clean" | Lint command output with 0 warnings and 0 errors |
| "Bug is fixed" | Reproduction steps that previously failed now succeed |
| "Feature works" | Demonstration with specific inputs and expected outputs |
| "No regressions" | Full test suite output, not just the changed test |
| "File was updated" | Read the file and confirm the changes are present |
| "Endpoint returns X" | Actual response from the endpoint, not the code that should return X |
| "CI is clean" | All checks pass AND zero annotations/warnings. Deprecation notices and non-fatal alerts count as unresolved |

## Zero Warnings as Verification Requirement

Apply `checklists/checklist.md` category 17 during every verification. "Zero errors" is not "clean". A tool run that produces warnings is a failing verification. Scan the full output for: `warn`, `warning`, `deprecated`, `deprecation`, `notice`. If any appear, fix and re-run.

## Common Failures to Catch

- "Tests pass" based on a previous run, but code changed since then
- "It should work" based on reading the code, without executing it
- "Build succeeds" based on no syntax errors, without actually building
- "Fixed the bug" based on the fix looking correct, without reproducing
- Conflating "no errors" with "works correctly" (silent failures)
- "CI passed" but ignoring deprecation warnings or non-fatal annotations in the run output
- Relying on `tail -N` for test results. Test runners print failures BEFORE the summary. `tail -20` on a run with 50+ failures shows only the summary line, hiding every failure. Always use `grep -E "passed|failed"` to capture the full result counts, or read the exit code. Never assume "X passed" means zero failures unless the failure count is explicitly shown as 0

## Verification by Task Type

**Code changes**: run formatter + tests + lint + build. All four.

**Configuration changes**: verify the config loads correctly. Start the relevant service or run a validation command.

**Infrastructure changes**: `terraform plan` shows expected diff. After apply, verify the resource exists with a direct query.

**Documentation changes**: verify links work, code examples run, and referenced files exist.

**Dependency changes**: lockfile committed, tests pass, build succeeds. No version conflicts.

**Scheduled jobs, such as cron, pg_cron, and CloudWatch, add:**

- Before finalizing any interval, verify that job execution time fits within it. Query historical run times from the job's run history table: `cron.job_run_details` for pg_cron, CloudWatch Logs for AWS. If execution time exceeds the interval, jobs queue behind a lock and pile up.
- If no history exists on first deploy, set a conservative interval: at minimum 2x the expected duration. Tighten after observing actual run times.
- After the first full cycle completes, confirm via the run history that all jobs reached a succeeded status with no overlap.

## Response Self-Check

Before presenting analysis, recommendations, or findings, verify your own output against these categories.

| Category | What to look for |
|----------|-----------------|
| Fabrication | Did you reference any file path, function name, API endpoint, or version without reading it in this session? |
| Source drift | Does your summary say something stronger or different than the code actually shows? |
| Logic gaps | Does every "therefore" or "because" follow from evidence, not assumption? |
| Internal contradictions | Does any part of your response contradict another part? |
| Uncritical agreement | Did you accept the user's framing without scrutiny? If the user said "this is simple," did you verify that? |

Walk through each finding or recommendation. If any came from inference rather than source, verify it or label it as unverified.

This check applies to analytical output: reviews, assessments, incident analyses, architecture recommendations. It complements the command-based verification above, which covers code changes.

## Cross-Platform Verification

When code has platform-specific branches (architecture checks, OS detection, conditional package lists), never validate on a single platform and assume the others work. Each platform branch is independent code that needs independent verification. A test passing on x64 says nothing about arm64 if the code paths diverge.

## Partial Completion

If you cannot verify everything:

- State what was verified and what was not.
- Explain why full verification was not possible.
- Never round up. 80% done is not done.
