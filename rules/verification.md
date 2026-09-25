# Verification

No completion claim without fresh evidence run in this session. Previous runs, cached results, and "it should work" are not evidence.

- Gate: identify what would fail if the work were wrong, run it now, read the full output, confirm it matches, only then claim done.
- Code changes: formatter, tests, lint, and build, all four. Frontend and mobile: render it in a real engine or simulator; a jsdom or widget test is not render evidence.
- Evidence means output: 0 test failures, 0 lint warnings, a clean build, a reproduction that now succeeds, the actual endpoint response, the file re-read.
- Zero warnings is part of clean. Scan output for `warn`, `warning`, `deprecated`, `deprecation`, `notice`. CI is clean only with zero annotations.
- A flagged problem is in scope even when it predates your work. Fix it rather than dismissing it by age or authorship.
- Never read test results with `tail -N`; grep for `passed|failed` or check the exit code.
- A check that errored or would not parse is failed, never skipped. Gate on exit codes, never on grepping output. Confirm which stream carries the payload before parsing.
- Calibrate an existence oracle both ways before trusting it: a name that cannot exist reports absent, one that exists reports present.
- Before blaming your change, stash it and rerun. A randomized-order suite failing outside the diff reruns with order fixed, `-p no:randomly` for pytest.
- A blocked tool call ran nothing. Re-read the target and repeat the whole command. A pass after a block is the first real check.
- Run `date` before reasoning about today, deadlines, or elapsed time.
- Re-fetch the primary source before publishing a specific that a subagent, snippet, or summary reported.
- Never read files via `FETCH_HEAD` after another fetch; use `origin/<branch>`.
- Run checks at the project's pinned toolchain version, never an unpinned local default.
- Validate every platform branch independently.
- Scheduled jobs: execution time must fit the interval; with no history, use at least 2x the expected duration.
- After deploying to a shared environment, monitor for 10 minutes and roll back on regression.
- Confidence 7-10 report normally, 5-6 with a caveat, below 5 suppress and investigate.
- Partial completion: say what was and was not verified. Never round up. Never present the tested set as the required set.
- Self-check analysis for fabrication, source drift, logic gaps, contradictions, and uncritical agreement.

Full rule, examples, and rationale: [`standards/verification.md`](../standards/verification.md). Read it before declaring a task done, reporting CI status, or verifying infrastructure, deploys, or scheduled jobs.
