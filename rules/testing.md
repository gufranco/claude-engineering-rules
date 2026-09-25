# Testing

Tests verify real behavior against real infrastructure. Prefer integration, then E2E, then unit tests for pure functions only.

- Mock only third-party APIs you do not control, systems you cannot run locally, time, and randomness.
- Never mock the database, Redis, caches, queues, or your own services and modules. Run them in docker-compose. Mocking internal infrastructure is a blocking review issue.
- Every test is Arrange, Act, Assert: three blocks separated by exactly one blank line each, nowhere else. One call to the unit under test, bound to a name.
- Test bodies carry zero comments. No `// Arrange`, `// Act`, `// Assert`. The test name states the behavior; named helpers carry setup.
- Only two deviations: expected-throw tests fuse act and assert; shared setup may be hoisted to `beforeEach`.
- Use the most specific assertion. Never `toBeTruthy()`, `toBeFalsy()`, or `expect.anything()`; assert exact values and `toHaveLength(n)`.
- Generate data with a seeded faker: `@faker-js/faker`, `faker`, `gofakeit`, `fake`, `datafaker`. Static values like `"test@example.com"` are a blocking issue.
- Zero warnings in test output. Names describe behavior and never reference ticket IDs.
- Coverage gate: 95%+ statements, branches, functions, and lines on new code, changed files, and related files. Never reduce existing coverage. Agent-produced code meets the same gate.
- Every new or modified write path ships two extra tests against the real database: 10+ identical parallel calls asserting exactly one effect, and two sequential calls asserting one effect and a replayed response. Assert the loser's outcome. Restart the process between calls when a dedup store is involved.
- Tests are deterministic: fixed clock, seeded randomness, isolated data, no `sleep` in assertions, random ports, temp dirs. Fix or delete a flaky test.
- Env schema changes update `.env.example`, `.env.test`, CI, and Docker Compose in the same commit.
- Each page gets at least one mobile viewport E2E test; 320px is the minimum width.

Full rule, examples, and rationale: [`standards/testing.md`](../standards/testing.md). Read it before writing tests, planning scenarios, snapshots, contract tests, or benchmarks.

## Enforcement

Enforced by: [`hooks/mock-internal-blocker.py`](../hooks/mock-internal-blocker.py).
Enforced by: [`hooks/tdd-gate.py`](../hooks/tdd-gate.py).
