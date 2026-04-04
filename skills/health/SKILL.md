---
name: health
description: Code quality dashboard with weighted scoring. Runs type checker, linter, test suite with coverage, and dead code detection in parallel, then computes a 0-10 quality score. Tracks trends over time. Use when user says "health check", "code quality", "project health", "quality score", "how healthy is this project", or wants a quick quality snapshot. Do NOT use for code review (use /review), running tests alone (use /test), or security audit (use /audit).
---

Report-only quality dashboard that computes a weighted score from multiple quality signals. Never auto-fixes anything.

## Arguments

- No arguments: run the full health check on the current project.
- `--no-trend`: skip trend tracking, report only.

## Process

### 1. Detect Project Tools

Read the project's package manager config, lockfile, and scripts to identify:

| Signal | Detection method |
|--------|-----------------|
| Type checker | `tsc`, `mypy`, `pyright`, `go vet` in scripts or devDependencies |
| Linter | `eslint`, `ruff`, `golangci-lint`, `clippy` in scripts or devDependencies |
| Test runner | `jest`, `vitest`, `pytest`, `go test`, `cargo test` in scripts or devDependencies |
| Coverage tool | `--coverage` flag, `c8`, `nyc`, `coverage.py` in scripts or devDependencies |
| Formatter | `prettier`, `black`, `gofmt`, `rustfmt` in scripts or devDependencies |

If a tool is not present, skip that signal and redistribute its weight proportionally across the remaining signals.

### 2. Run Checks in Parallel

Execute all detected tools simultaneously:

- **Type checker:** run with no-emit flag. Count errors.
- **Linter:** run in report mode. Count errors and warnings separately.
- **Test suite:** run with coverage enabled. Capture pass/fail counts and coverage percentages for statements, branches, functions, and lines.
- **Dead code detection:** grep for exported symbols and check if they are imported elsewhere. Count unused exports.

### 3. Compute Scores

Each signal produces a 0-10 sub-score:

| Signal | Weight | Scoring |
|--------|--------|---------|
| Tests | 30% | 10 if all pass, subtract 1 per failure, floor at 0 |
| Coverage | 25% | coverage percentage divided by 10, e.g. 95% = 9.5 |
| Lint | 20% | 10 minus 0.5 per warning minus 1 per error, floor at 0 |
| Types | 15% | 10 if zero errors, subtract 1 per error, floor at 0 |
| Dead code | 10% | 10 minus 0.5 per unused export, floor at 0 |

**Composite score:** weighted sum of sub-scores, rounded to one decimal.

### 4. Report

Present results as a summary table:

| Signal | Raw Result | Score | Weight | Weighted |
|--------|-----------|-------|--------|----------|
| Tests | 142 pass, 0 fail | 10.0 | 30% | 3.00 |
| Coverage | 87.3% avg | 8.7 | 25% | 2.18 |
| Lint | 2 warnings, 0 errors | 9.0 | 20% | 1.80 |
| Types | 0 errors | 10.0 | 15% | 1.50 |
| Dead code | 3 unused exports | 8.5 | 10% | 0.85 |
| **Total** | | | | **9.3** |

Include a one-line assessment:

| Score range | Assessment |
|-------------|-----------|
| 9.0 - 10.0 | Healthy. No action needed. |
| 7.0 - 8.9 | Acceptable. Minor issues to address. |
| 5.0 - 6.9 | Degraded. Schedule cleanup. |
| 0.0 - 4.9 | Critical. Prioritize remediation. |

### 5. Track Trends

Unless `--no-trend` is passed:

1. Identify the project by its git remote URL or directory name.
2. Append a JSON line to `~/.claude/telemetry/health-<project>.jsonl`:

   ```json
   {"timestamp":"2026-04-04T12:00:00Z","score":9.3,"tests":{"pass":142,"fail":0},"coverage":87.3,"lint":{"warnings":2,"errors":0},"types":{"errors":0},"deadCode":{"unused":3}}
   ```

3. If previous entries exist, compare the current score against the last entry. Report the delta: "+0.3 since last check" or "-1.2 since last check".

4. Create the `~/.claude/telemetry/` directory if it does not exist.

## Rules

- Report only. Never modify source files, configs, or dependencies.
- Show raw tool output excerpts when a sub-score is below 7.0 so the user can see what needs attention.
- When a tool is missing, state which signal was skipped and note that the score reflects fewer dimensions.
- All timestamps in GMT.
- Trend files are append-only. Never truncate or rewrite them.

## Related Skills

- `/review` -- Detailed code review for specific changes.
- `/test` -- Run the test suite with full output.
- `/audit` -- Security-focused audit.
