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
- Coverage gate: 95%+ statements, branches, functions, and lines on new code, changed files, and related files. Never reduce existing coverage. Agent-produced code meets the same gate. Coverage locates untested behavior a user would notice broken; it is never the target.
- Every new or modified write path ships two extra tests against the real database: 10+ identical parallel calls asserting exactly one effect, and two sequential calls asserting one effect and a replayed response. Assert the loser's outcome. Restart the process between calls when a dedup store is involved.
- Tests are deterministic: fixed clock, seeded randomness, isolated data, no `sleep` in assertions, random ports, temp dirs. Fix or delete a flaky test.
- Env schema changes update `.env.example`, `.env.test`, CI, and Docker Compose in the same commit.
- Each page gets at least one mobile viewport E2E test; 320px is the minimum width.

Full rule, examples, and rationale: [`standards/testing.md`](../standards/testing.md). Read it before writing tests, planning scenarios, snapshots, contract tests, or benchmarks.

## Enforcement

Enforced by: [`hooks/mock-internal-blocker.py`](../hooks/mock-internal-blocker.py).
Enforced by: [`hooks/tdd-gate.py`](../hooks/tdd-gate.py).
Enforced by: [`hooks/dangerous-command-blocker.py`](../hooks/dangerous-command-blocker.py).

## Provenance

Added 2026-03-06, recurrence not recorded. Origin: not recorded at creation. Amended 2026-10-27, by direct user instruction, under the fails-without-an-error-signal condition: a weakened or deleted test turns a failing change green, and a prose-only ban was reported to shift the agent from editing tests to deleting them.
