---
name: test
description: Run tests, load benchmarks, coverage analysis, linting, and security scanning. Subcommands absorb /perf for HTTP load testing with k6/wrk/hey/ab. Use when user says "run tests", "check coverage", "lint", "benchmark", "load test", "perf test", or wants to execute the project's test suite with results. Do NOT use for QA analysis of test gaps (use /review qa), security auditing (use /audit), or writing test scenarios during planning (use /plan).
---

Unified testing skill covering test execution, load testing, coverage, linting, and scanning. Replaces standalone `/test` and `/perf` skills.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/test` | Run the full test suite (default) |
| `/test <path>` | Run tests matching a file or pattern |
| `/test --coverage` | Run with coverage reporting |
| `/test --watch` | Run in watch mode |
| `/test lint` | Run linters |
| `/test scan` | Security vulnerability scanning |
| `/test ci` | Simulate CI locally with `act` |
| `/test perf <url>` | Load test an HTTP endpoint |
| `/test stubs <path>` | Generate test stubs for uncovered code |
| `/test flaky` | Detect flaky tests by running the suite multiple times |

---

## Test Execution (default)

### Package Manager Detection

`bun.lock`/`bun.lockb` = bun, `pnpm-lock.yaml` = pnpm, `yarn.lock` = yarn, `package-lock.json` = npm, `Cargo.toml` = cargo, `go.mod` = go, `pyproject.toml` with `uv.lock` = uv, `pyproject.toml` with `[tool.poetry]` = poetry, `pyproject.toml`/`requirements.txt` = pip. Also check `Makefile`/`Justfile` for test targets.

### Test Runner Detection

- Node.js: `vitest.config.*` or vitest in devDeps, `jest.config.*` or jest in devDeps, `mocha` in devDeps.
- Rust: `cargo test`. Go: `go test ./...`. Python: look for `pytest.ini`, `pyproject.toml` with `[tool.pytest]`.
- Shell: check for `shellcheck`.

### Steps

1. Detect package manager and test runner.
2. Build command: base command + path/pattern + `--coverage` or `--watch` flags.
3. Run and capture output.
4. Parse: passed, failed, skipped counts. Coverage summary if requested.
5. Present: pass count, failures with error messages and file locations, coverage if applicable.

---

## lint

Run linters based on project configuration.

- Node.js: `package.json` lint script.
- Go: `golangci-lint run`.
- Shell: `shellcheck` on `.sh`/`.zsh` files.
- Python: `ruff check .` or `flake8`.
- GitHub Actions: `actionlint` on workflow files.

---

## scan

Deep security scanning with available tools.

- `trivy fs .` for dependency + config vulnerabilities.
- `snyk test` + `snyk code test`.
- `gitleaks detect --source .` for leaked secrets.

Report results from whichever tools are installed. List missing tools if none available.

---

## ci

Simulate CI locally with `act`.

1. Verify `act` installed.
2. `act --list` to show workflows.
3. Run selected workflow with `act push --container-architecture linux/amd64`.

---

## perf

Load test HTTP endpoints. Auto-detects the best available tool.

### Arguments

- A URL (required): endpoint to test.
- `-n <requests>`: total requests (default: 1000).
- `-c <concurrency>`: concurrent connections (default: 10).
- `-d <duration>`: test duration (e.g. `30s`). Overrides `-n`.
- `--method <METHOD>`: HTTP method (default: GET).
- `--body <json>`: request body.
- `--header <key:value>`: custom header (repeatable).
- `--compare`: run twice with a pause for changes between runs.
- `--script <path>`: custom k6 script.

### Steps

1. Parse arguments. Validate target with a single request.
2. Detect tool (preference order): k6, wrk, hey, ab.
3. Build command:
   - **k6**: generate temp script with VUs, duration/iterations, headers, body. Run with `--summary-trend-stats`.
   - **wrk**: `wrk -t<threads> -c<concurrency> -d<duration> <url>`. Lua script for POST.
   - **hey**: `hey -n <n> -c <c> -m <method> <url>`.
   - **ab**: `ab -n <n> -c <c> <url>`. Temp file for POST body.
4. Run and extract metrics:

| Metric | Description |
|--------|-------------|
| Total requests | Completed |
| Failed requests | Non-2xx or connection errors |
| Requests/sec | Throughput |
| Latency avg | Mean response time |
| Latency p50 | Median |
| Latency p95 | 95th percentile |
| Latency p99 | 99th percentile |
| Transfer rate | Data throughput |

1. Flag: p99 > 1s, error rate > 1%.
2. **Compare mode**: run once, wait for user signal, run again. Side-by-side comparison with percentage changes.
3. Clean up temp files.

---

## flaky

Detect flaky tests by running the full suite multiple times and tracking which tests have inconsistent results.

### Steps

1. Detect the test runner and build the test command with no watch mode.
2. Run the suite 5 times in sequence, capturing pass/fail status for each test.
3. Track per-test consistency: a test is flaky if it fails in at least 1 run and passes in at least 1 run.
4. Classify by flake rate:
   - Fail rate > 5%: quarantine candidate (flag immediately, never merge until fixed).
   - Fail rate 1-5%: intermittent (investigate root cause before next release).
   - Fail rate < 1%: monitor (log, watch in future runs).
5. Report results:

```
## Flaky Test Report: <date>

### Summary
- Suite runs: 5
- Total tests: <N>
- Consistently passing: <N>
- Flaky (inconsistent): <N>
- Consistently failing: <N>

### Flaky Tests

| Test | Fail Rate | Category | Root Cause Hint |
|------|----------|---------|-----------------|
| <test name> | 2/5 (40%) | quarantine | timing dependency suspected |

### Quarantine Candidates

Skip these tests immediately by applying `.skip` or `xit` — they pollute CI signal.
```

1. For each flaky test, suggest likely root causes: shared mutable state, hardcoded ports, timing, unseeded random, missing database cleanup.

### Rules

- Never run this against production endpoints.
- If the test suite takes more than 60 seconds per run, reduce to 3 runs and note the limitation.
- Do not apply `.skip` automatically. Present the list and wait for approval.

---

## stubs

Generate test file stubs for code that lacks tests.

### Steps

1. Read the target file(s).
2. Identify all exported functions, classes, and methods.
3. Check for existing test files. Skip already-tested exports.
4. Generate a test stub per untested export following project conventions:
   - Read existing test files in the same module for patterns.
   - Follow `rules/testing.md`: AAA pattern, faker for data, real database.
   - Include: one happy-path test, one error-path test, placeholder `// TODO: add edge cases`.
5. Present stubs for approval before writing.
6. After writing, run the test suite to verify stubs compile (they may fail on TODO assertions, which is expected).

---

## Rules

- Always detect package manager and test runner from project config.
- Never install test dependencies without asking.
- Never modify test files during test execution (only `stubs` generates files).
- Never run perf tests against production URLs without explicit confirmation.
- Always validate perf target is reachable before load testing.
- Always clean up temporary files.
- Default perf to safe values (1000 requests, 10 concurrency).
- Show exact commands so user can reproduce manually.
- If no test config exists, say so and stop.

## Related skills

- `/ship` -- Commit after tests pass.
- `/review qa` -- QA analysis for coverage gaps.
- `/audit scan` -- Security vulnerability scanning.
