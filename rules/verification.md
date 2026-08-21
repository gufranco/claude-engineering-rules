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
| "The focus ring is visible" | Computed `outline` and `boxShadow` read off `document.activeElement` in a real engine, not the rule declared in the theme |
| "This control is accessible" | The accessibility tree as computed, not the `aria-label` present in source |
| "The layout holds" | A render at a stated viewport width, with the smallest supported width included when layout changed |
| "The screen works" (mobile) | A run on a simulator or emulator. A widget test proves structure, not paint and not platform semantics |
| "CI is clean" | All checks pass AND zero annotations/warnings. Deprecation notices and non-fatal alerts count as unresolved |

## Zero Warnings as Verification Requirement

Apply [`checklists/checklist.md`](../checklists/checklist.md) category 17 during every verification. "Zero errors" is not "clean". A tool run that produces warnings is a failing verification. Scan the full output for: `warn`, `warning`, `deprecated`, `deprecation`, `notice`. If any appear, fix and re-run.

## Common Failures to Catch

- "Tests pass" based on a previous run, but code changed since then
- "It should work" based on reading the code, without executing it
- "Build succeeds" based on no syntax errors, without actually building
- "Fixed the bug" based on the fix looking correct, without reproducing
- Conflating "no errors" with "works correctly". Silent failures
- "CI passed" but ignoring deprecation warnings or non-fatal annotations in the run output
- Dismissing a flagged issue as "pre-existing" or "not introduced by this change". A problem surfaced by a verification surface is in scope regardless of when it was introduced. See [`found-fix.md`](found-fix.md)
- Trusting an existence oracle that was never calibrated. Many web indexes answer HTTP 200 with a "not found" page, and many commands exit 0 on a miss, so a naive check reports every candidate as present. Before running the check across a list, run it against a name that cannot exist and confirm it reports absent
- Attributing a failure to your own change without confirming it fails without your change. A suite that will not run because the project needs a path set, a fixture that was already absent, a flake that predates the session: all of them look like a regression when they surface right after an edit. Stash the change, run it again, and read the result before diagnosing. The cost is one command; the cost of the alternative is rewriting working code to fix something it did not break
- Assuming a blocked tool call partially applied. A PreToolUse block runs nothing, so every change that call carried is still unmade, including the parts that precede the offending one. Re-read the file instead of re-running only the piece that tripped the hook
- Reading the absence of a hook block as proof the content is clean. The first hook to block ends the chain, so every hook registered after it never evaluates the payload. A new source file that trips the TDD gate is never seen by the comment blocker, and clearing the first block can surface a second one on the same content. A call that passes on the second attempt was checked by more hooks than the first attempt, not fewer, so treat the first clean run after a block as the first real check rather than a confirmation of the earlier one. Hooks are a backstop, never the verification itself: check the payload against the rule directly
- Writing a parser against a tool's output without confirming the stream and the field positions. Diagnostics commonly go to stderr, so a `2>/dev/null` pipeline silently reads an empty stream and the loop over it does nothing while appearing to succeed. Run the command once, see which stream carries the payload, and count the columns before depending on them
- Reading one run of a suite that randomizes test order as a stable verdict. A runner like `pytest-randomly` reshuffles every run, so a suite can pass, then fail in files the change never touched, then pass again. When failures land outside the diff, re-run with order fixed, `-p no:randomly` for pytest, before diagnosing anything. A deterministic pass plus a randomized failure is a flake with a real cause, so name the cause and report it; it is never a reason to re-run until green
- Relying on `tail -N` for test results. Test runners print failures BEFORE the summary. `tail -20` on a run with 50+ failures shows only the summary line, hiding every failure. Always use `grep -E "passed|failed"` to capture the full result counts, or read the exit code. Never assume "X passed" means zero failures unless the failure count is explicitly shown as 0
- Reading file content through `FETCH_HEAD` after any later `git fetch`. Every fetch overwrites `FETCH_HEAD`, so a `git show FETCH_HEAD:<path>` issued after a second fetch silently returns the newer fetch's branch. Nothing errors, and the content is plausible enough to reason about for several steps. Fetch into a named remote-tracking ref and read from that, `git show origin/<branch>:<path>`, rather than from `FETCH_HEAD`. Suspect this immediately when a file's content contradicts a diff already read in the same session, and re-verify every read taken after the last fetch, not only the one that surfaced the contradiction

## Verification by Task Type

When reporting verification output to the user, lead with the symptom, then chronology, then hypothesis, per [`rules/smart-questions.md`](smart-questions.md) "Status and Error Reports". When the task is complete, close with a one-line `FIXED:`, `RESOLVED:`, or `DONE:` resolution that names what changed, where, and the evidence command.

**Code changes**: run formatter + tests + lint + build. All four.

**Configuration changes**: verify the config loads correctly. Start the relevant service or run a validation command.

**Infrastructure changes**: `terraform plan` shows expected diff. After apply, verify the resource exists with a direct query.

**Frontend and mobile changes**: render it. A passing unit test in a DOM emulation is not render evidence, because that layer implements no paint, no real cascade, and no full accessibility tree. Drive the project's browser or simulator suite, or `agent-browser open` plus `eval` for computed style and `snapshot -i` for the tree. Naming which checks were skipped is acceptable; implying they happened is not. See [`frontend-render-gate.md`](frontend-render-gate.md).

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

When code has platform-specific branches, architecture checks, OS detection, conditional package lists, never validate on a single platform and assume the others work. Each platform branch is independent code that needs independent verification. A test passing on x64 says nothing about arm64 if the code paths diverge.

## Pinned Toolchain Verification

Run every verification command at the version the project pins. A local default that differs from the pinned or CI version reports on a toolchain nobody ships, and acting on that report is worse than not running the check at all. The failure is quiet: the command succeeds, the output looks authoritative, and the finding is wrong.

| Surface | Where the pin lives | How to honor it |
|---------|--------------------|-----------------|
| Terraform provider | `required_providers` plus `.terraform.lock.hcl` | Validate from the stack that carries the pin. A bare `terraform init` in a module directory resolves the newest provider and reports deprecations that do not apply |
| Terraform CLI | The `setup-terraform` version in the workflow | Match it, or cross-check the result against a second implementation before trusting it |
| Formatters and linters | `package.json` plus the lockfile | Run through the project's own dependency tree. When it is not installed, pin the exact version explicitly and confirm the project config adds no style options the bare run would miss |
| Language runtime | `.nvmrc`, `.python-version`, `engines` | Match before concluding anything about behavior |

A concrete case: a module validated against AWS provider v6 reported `data.aws_region.current.name` as deprecated. The stack pins `~> 5.0`, where that attribute is correct and the suggested replacement does not exist. Applying the fix would have broken every environment the module builds.

When the pinned version is genuinely unavailable, name the version that produced the result and cross-check with the closest alternative implementation. Never present an unpinned run as though it were the project's own gate.

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

- 7-10: display normally, high confidence
- 5-6: display with a caveat explaining uncertainty
- Below 5: suppress from output, investigate further before reporting

A low-confidence finding that turns out to be real is a calibration learning. Track these to improve scoring accuracy.

## Partial Completion

If you cannot verify everything:

- State what was verified and what was not.
- Explain why full verification was not possible.
- Never round up. 80% done is not done.

## The Tested Set Is Not the Required Set

Rounding down is the mirror of rounding up, and it is easier to miss because it looks like caution. Evidence answers "what did we confirm". It never answers "what is necessary" on its own. Presenting the first as though it were the second understates the thing being described and misleads the reader in a way that sounds careful.

The failure is almost always inherited rather than invented: an earlier document listed the environments that happened to get tested, a later reader parses that list as a compatibility matrix, and it hardens into a requirement nobody ever established.

| Instead of | Write |
|-----------|-------|
| "Runs on a Game Doctor SF7 and an FXPAK Pro" as the hardware section | "No coprocessor and no special mapping hardware, so it runs on any cartridge that can hold it. Verified on a Game Doctor SF7 and an FXPAK Pro" |
| "Supported: Node 20 and Node 22" when only those were in CI | "Requires Node 18 or newer, per the engines field. CI covers 20 and 22" |
| "Works on Postgres 15" after testing one version | "Uses no version-specific feature beyond Postgres 12. Tested against 15" |

Two separate claims, written separately: what the thing actually requires, derived from the code, and what was measured, derived from a run. When the requirement has not been established, say that rather than substituting the test matrix for it.

The check: for every environment, platform or version named in a document, ask whether it is there because the code needs it or because somebody happened to try it. If the second, the sentence is a compatibility claim resting on no analysis.
