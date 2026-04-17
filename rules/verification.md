# Verification

## Core Rule

No completion claims without fresh verification evidence. Previous runs, cached results, and "it should work" are not evidence.

## Gate Function

Before declaring any task complete:

1. **Identify** what proves the claim. What command, test, or check would fail if the work were wrong?
2. **Run** it. In the current session, right now
3. **Read** the output. The full output, not just the exit code
4. **Verify** the output matches the expected result
5. **Only then** claim the task is done

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

Apply `checklists/checklist.md` category 17 during every verification. A tool run that produces warnings is a failing verification. Scan the full output for: `warn`, `warning`, `deprecated`, `deprecation`, `notice`. If any appear, fix and re-run.

## Common Failures to Catch

- "Tests pass" based on a previous run, but code changed since then
- "It should work" based on reading the code, without executing it
- "Build succeeds" based on no syntax errors, without actually building
- "Fixed the bug" based on the fix looking correct, without reproducing
- Conflating "no errors" with "works correctly" (silent failures)
- "CI passed" but ignoring deprecation warnings or non-fatal annotations
- Relying on `tail -N` for test results. Test runners print failures BEFORE the summary. Always use `grep -E "passed|failed"` to capture full result counts, or read the exit code. Never assume "X passed" means zero failures unless the failure count is explicitly shown as 0

## Verification by Task Type

**Code changes**: run formatter + tests + lint + build. All four.

**Configuration changes**: verify the config loads correctly. Start the relevant service or run a validation command.

**Infrastructure changes**: `terraform plan` shows expected diff. After apply, verify the resource exists with a direct query.

**Documentation changes**: verify links work, code examples run, and referenced files exist.

**Dependency changes**: lockfile committed, tests pass, build succeeds. No version conflicts.

**Scheduled jobs (cron, pg_cron, CloudWatch):**
- Before finalizing any interval, verify that job execution time fits within it. Query historical run times from `cron.job_run_details` for pg_cron or CloudWatch Logs for AWS. If execution time exceeds the interval, jobs queue behind a lock
- On first deploy with no history, set the interval to at minimum 2x the expected duration
- After the first full cycle completes, confirm all jobs reached a succeeded status with no overlap

## Response Self-Check

Before presenting analysis, recommendations, or findings:

| Category | What to look for |
|----------|-----------------|
| Fabrication | Did you reference any file path, function name, API endpoint, or version without reading it in this session? |
| Source drift | Does your summary say something stronger or different than the code actually shows? |
| Logic gaps | Does every "therefore" or "because" follow from evidence, not assumption? |
| Internal contradictions | Does any part of your response contradict another part? |
| Uncritical agreement | Did you accept the user's framing without scrutiny? |

## Cross-Platform Verification

When code has platform-specific branches, never validate on a single platform and assume the others work. Each platform branch needs independent verification.

## Post-Deploy Verification

After any deployment to a shared environment:

1. Monitor the live application for 10 minutes after deploy
2. Check for new console errors or warnings
3. Compare error rate against pre-deploy baseline
4. Verify key user flows: login, core feature, critical path
5. Compare performance metrics against baseline
6. If regression detected: trigger rollback and investigate

## Confidence Scoring

When presenting verification findings or review results, assign a confidence score of 1-10:
- 7-10: display normally
- 5-6: display with a caveat explaining uncertainty
- Below 5: suppress from output, investigate further before reporting

## Multi-Task Completion Sweep (MANDATORY)

When executing a batch of tasks from a spec, plan, or "do everything" instruction, a final sweep is required before declaring the batch complete.

**Required steps before declaring a batch done:**

1. Re-read the original task list, spec, or plan from its source file. Do not rely on memory
2. For each item: run its verification command or grep
3. Produce a count: N done, M pending. Only declare done if M = 0
4. If any item is pending, implement it before closing. Do not report partial completion as completion

**This rule applies whenever:**
- The user says "do everything", "all of them", "todos", or equivalent
- A plan.md or spec defines a numbered list of items
- A previous session's summary lists items as pending
- Context compaction occurred mid-batch

**The final response must state the count explicitly: "N/N items verified." If that count is absent, the sweep did not run.**

## Partial Completion

- State what was verified and what was not
- Explain why full verification was not possible
- Never round up. 80% done is not done
