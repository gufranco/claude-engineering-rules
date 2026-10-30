# Testing

Tests verify real behavior against real infrastructure. Prefer integration, then E2E, then unit tests for pure functions only.

- Mock only third-party APIs you do not control, systems you cannot run locally, time, and randomness.
- Never mock the database, Redis, caches, queues, or your own services and modules. Run them in docker-compose. Mocking internal infrastructure is a blocking review issue.
- Every test is Arrange, Act, Assert: three blocks separated by exactly one blank line each, nowhere else. Each block opens with its marker comment in the language's syntax, `// Arrange`, `// Act`, `// Assert` or `# Arrange`, `# Act`, `# Assert`, and the marker is the bare word.
- Those three markers are the only comments a test body carries. The test name states the behavior; named helpers carry setup.
- One call to the unit under test in Act, bound to a name when it returns a value; a command that returns nothing is called unbound and Assert checks its effect. An expected throw binds the call as a thunk or promise, or captures it with `pytest.raises`, in Act, and asserts in Assert. Shared setup may be hoisted to `beforeEach`; the Arrange block then binds what the act uses.
- Never delete, loosen, or skip an existing assertion, test case, or test file to make a change pass; fix the code, or get the user's agreement when the behavior was removed on purpose.
- Use the most specific assertion. Never `toBeTruthy()`, `toBeFalsy()`, or `expect.anything()`; assert exact values and `toHaveLength(n)`.
- Expected values come from an independent source: a known-good literal, a worked example, or the spec, never a recomputation of the code's own logic.
- Generate data with a seeded faker: `@faker-js/faker`, `faker`, `gofakeit`, `fake`, `datafaker`. Static values like `"test@example.com"` are a blocking issue.
- Zero warnings in test output. Names describe behavior and never reference ticket IDs.
- Coverage gate: 100% statements, branches, functions, and lines on every hand-written file, per file. Agent-produced code meets the same gate. Coverage locates untested behavior a user would notice broken; it is never the target.
- No exclusions: no `pragma: no cover`, `istanbul ignore`, `c8 ignore`, or any other directive, and no omit entry for hand-written code. Only generated and vendored code stays out, listed by path in the coverage config. A threshold never drops below 100.
- A line no test can reach is a design defect: delete dead code, inject the hidden dependency, or move the defensive check to the boundary. Refactor until it is covered.
- 100% E2E: every user-facing entry point, route, screen, command, endpoint, and job trigger, and every requirement scenario, has an end-to-end test driving it the way a user does.
- Every new or modified write path ships two extra tests against the real database: 10+ identical parallel calls asserting exactly one effect, and two sequential calls asserting one effect and a replayed response. Assert the loser's outcome. Restart the process between calls when a dedup store is involved.
- Tests are deterministic: fixed clock, seeded randomness, isolated data, no `sleep` in assertions, random ports, temp dirs. Fix or delete a flaky test.
- Tests never depend on the developer's machine: set the git identity in any repository a test creates, point `HOME` at a temp directory before reading a dotfile, and cover each platform branch on a platform CI runs.
- Deleting a test file asks first, except a file that is untracked and in no commit, such as a temporary capture spec the session created.
- Env schema changes update `.env.example`, `.env.test`, CI, and Docker Compose in the same commit.
- Each page gets at least one mobile viewport E2E test; 320px is the minimum width.

Full rule, examples, and rationale: [`standards/testing.md`](../standards/testing.md). Read it before writing tests, planning scenarios, snapshots, contract tests, or benchmarks.

## Enforcement

Enforced by: [`hooks/mock-internal-blocker.py`](../hooks/mock-internal-blocker.py).
Enforced by: [`hooks/tdd-gate.py`](../hooks/tdd-gate.py).
Enforced by: [`hooks/dangerous-command-blocker.py`](../hooks/dangerous-command-blocker.py).
Enforced by: [`hooks/coverage-exclusion-guard.py`](../hooks/coverage-exclusion-guard.py).
Enforced by: [`hooks/commit-test-weakening.py`](../hooks/commit-test-weakening.py).
