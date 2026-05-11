# Continuous Integration

How this repo is verified on every push and pull request.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.2.4.

## Jobs

The single workflow at `.github/workflows/ci.yml` runs three jobs in parallel.

| Job | Purpose | Key steps |
|-----|---------|-----------|
| `lint` | Static checks for non-Python assets and metadata | `ruff check`, `shellcheck`, markdownlint, JSON/YAML/agent/settings/skill/index validators |
| `hooks` | Legacy bash smoke tests for hooks | `tests/test-hooks.sh`, `scripts/hook-benchmark.sh` with a 500 ms threshold |
| `pytest` | Python unit + integration test suite with branch coverage | `make test-cov`, `make test-bats`, coverage artifact upload |

## Local equivalent

Run the full suite locally with:

```bash
make test-all
```

This is the same gate CI enforces. It chains `test-cov`, `test-bats`, `lint`, and `typecheck`. If any step fails, the chain stops with a non-zero exit code.

For a faster inner loop while writing a single test:

```bash
make test-fast PYTEST_K="some_keyword"
```

## Coverage gate

`pytest.ini` enforces `--cov-fail-under=95` against the include list in `.coveragerc`. The CI run fails when total branch coverage on the included files drops below 95%.

The included files are listed explicitly so newly-added hooks and scripts must be added to the coverage scope deliberately.

## Coverage of subprocess hooks

Hooks are invoked as subprocesses by the test harness so the process boundary itself is exercised end-to-end. To stitch coverage back into the parent run:

1. `tests/_subprocess_cov/sitecustomize.py` calls `coverage.process_startup()` when `COVERAGE_PROCESS_START` is set.
2. `tests/conftest.py` injects that directory into `PYTHONPATH` and exports `COVERAGE_PROCESS_START` only when the parent run is itself under coverage.
3. After the suite finishes, `make test-cov` runs `coverage combine` to merge the per-process data files into a single report.

Without this glue, every hook subprocess would record zero coverage even though the hook ran.

## Test selection

| Goal | Command |
|------|---------|
| All tests, parallel, no coverage | `make test` |
| All tests, parallel, branch coverage, 95% gate | `make test-cov` |
| Fail on first failure, serial | `make test-fast` |
| Filter by name | `make test PYTEST_K="suppression"` |
| Filter by marker | `make test PYTEST_M="not slow"` |
| Bats shell hook tests only | `make test-bats` |

## Branch protection

Required status checks on `main`:

- `lint`
- `hooks`
- `pytest`

A pull request cannot merge until all three pass. Run `gh pr checks --watch` after every push.

## Adding a new hook

When a new hook is introduced under `hooks/`:

1. Add the file to `[run] include =` in `.coveragerc`.
2. Add a test module under `tests/hooks/<hook-name>/` and a per-hook conftest if hook-specific fixtures are needed.
3. The top-level `tests/conftest.py` provides `tool_use`, `assert_blocks`, `assert_allows`, and `assert_modifies_input` for free.
4. If the hook is shell, add a corresponding bats suite under `tests/bats/`.
5. Run `make test-all` locally before pushing.

## Investigating CI failures

```bash
gh run list --branch <branch>             # find the failed run
gh run view <id> --log-failed             # tail logs from failed jobs only
gh run download <id> -n coverage-report   # pull coverage artifact
```

The coverage artifact contains both the JUnit-style XML and the HTML report under `htmlcov/index.html` for line-level inspection.
