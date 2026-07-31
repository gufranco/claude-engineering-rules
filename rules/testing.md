# Testing

## Philosophy

Tests should verify real behavior, not mock behavior.

## Priority

1. **Integration**, preferred: real database, real services
2. **E2E**: full user flows
3. **Unit**, fallback: pure functions only

## Mocks Policy (STRICT)

**Allowed:** External third-party APIs outside your control, systems you do not own and cannot run locally, Time/Date, Randomness

**NEVER Mock:**
- **Database**: connect to a real database. Add it to docker-compose for the test environment. Use `beforeAll()` to seed, `afterAll()` to clean up
- **Redis, caches, queues**: connect to real instances. Add them to docker-compose
- **Your own services and modules**: if the code calls an internal service, the test calls the real service. Mocking your own code proves the mock works, not the code

A test that mocks infrastructure it depends on may pass while the actual integration is broken. This is worse than having no test at all. During code review, mocking internal infrastructure is a **blocking issue**.

## Test Structure

Every test follows Arrange, Act, Assert, in that order. The three phases are mandatory and their order is fixed. What is banned is labeling them, never the shape itself.

A test body carries zero comments. No section markers, no inline notes, no explanatory labels. `// Arrange`, `// Act`, `// Assert`, and every variant of them are comments, so the comment ban in [`code-style.md`](code-style.md) "Comments Policy" removes them along with everything else. The ban applies to test files exactly as it applies to production code, with the same single exemption for tool directives.

Removing the labels must not remove the structure. The phases stay; they are expressed in the code instead of announced above it.

### The three blocks

A test body is three blocks of statements separated by exactly one blank line each. The blank lines are the phase boundaries. Nothing else marks them.

| Phase | Contains | Must not contain |
|-------|----------|------------------|
| Arrange | Fake data, seeded records, fixtures, stubs for the allowed mock surface, the input value | Any call to the unit under test, any assertion |
| Act | Exactly one call to the unit under test, with its result bound to a name | Setup, branching, loops, a second call to the unit under test |
| Assert | Assertions on the bound result and on observable side effects | New setup, a second call to the unit under test |

Three supporting rules make the blocks readable without labels:

- **The test name carries the intent.** It states the behavior under test, so no header is needed to announce what follows.
- **Named helpers carry the setup.** When the arrange block needs explaining, extract it into a function whose name does the explaining: `seedAccountAtDailyLimit()` beats six lines of literals.
- **One act per test.** Two calls to the unit under test are two behaviors, so they are two tests. This is what keeps the middle block one line long and unmistakable.

If a step inside a test would need a comment to make sense, the test is too complex. Extract a helper or split the test.

```typescript
it('rejects a transfer that exceeds the daily limit', async () => {
  const account = await seedAccount({ dailyLimit: 500, transferredToday: 450 });

  const result = await transfer(account.id, 100);

  expect(result.status).toBe(TransferStatus.Rejected);
  expect(result.reason).toBe(RejectionReason.DailyLimitExceeded);
});
```

The blank lines above are load-bearing. A reader sees the arrangement, the single call, and the claims about it without reading a word of prose.

### The same shape in other languages

```python
def test_rejects_a_transfer_that_exceeds_the_daily_limit(db):
    account = seed_account(db, daily_limit=500, transferred_today=450)

    result = transfer(account.id, 100)

    assert result.status is TransferStatus.REJECTED
    assert result.reason is RejectionReason.DAILY_LIMIT_EXCEEDED
```

```go
func TestRejectsTransferExceedingDailyLimit(t *testing.T) {
    account := seedAccount(t, accountOpts{DailyLimit: 500, TransferredToday: 450})

    result, err := Transfer(account.ID, 100)

    require.NoError(t, err)
    require.Equal(t, StatusRejected, result.Status)
    require.Equal(t, ReasonDailyLimitExceeded, result.Reason)
}
```

### Violations

| Violation | Why it fails | Fix |
|-----------|--------------|-----|
| One unbroken block of statements | The phases are unreadable; the reader has to parse every line to find the call under test | Insert the two blank lines |
| Blank lines scattered every two or three lines | Four or five blocks mean no block is a phase | One blank line, twice, and nowhere else |
| Assertion inside the arrange block | Asserts the fixture, not the behavior; a fixture failure reads as a behavior failure | Move the guarantee into the helper, or into its own test of the helper |
| Setup between the act and the assertions | The reader can no longer tell which state the assertions describe | Move it above the act |
| Two calls to the unit under test | Two behaviors in one test; the failure message names neither | Split into two tests |
| Act and assert on one line, `expect(transfer(id, 100)).toBe(...)` | The act disappears into the assertion | Bind the result, then assert on the name |
| A comment restoring the labels | Banned by the comment policy and by the hook | Delete the comment; the blank lines already say it |

### The two permitted deviations

**Expected-throw tests fuse act and assert.** Every runner's rejection matcher takes the call as its argument, so the act cannot be bound to a name first. This produces two blocks, not three. It is the only two-block form allowed.

```typescript
it('throws when the account does not exist', async () => {
  const missingId = faker.string.uuid();

  await expect(transfer(missingId, 100)).rejects.toThrow(AccountNotFoundError);
});
```

**Shared arrangement moves to `beforeEach` or a fixture.** The arrange phase still exists, at the file or describe level instead of inside the body. A test whose arrangement is fully shared opens with the act, and that is correct: the phase did not disappear, it was hoisted. Keep the per-test remainder of the arrangement inside the body, above the act.

```typescript
describe('transfer', () => {
  let account: Account;

  beforeEach(async () => {
    account = await seedAccount({ dailyLimit: 500 });
  });

  it('settles a transfer within the daily limit', async () => {
    const result = await transfer(account.id, 100);

    expect(result.status).toBe(TransferStatus.Settled);
  });
});
```

Both deviations are about where a phase lives, never about dropping one. A test with no assertions is not a test, and a test with no act asserts nothing about the system.

## Assertion Specificity

Use the most specific assertion available. Vague assertions pass when they should fail.

| Avoid | Use instead | Why |
|-------|-------------|-----|
| `toBeTruthy()` | `toBeDefined()`, `toBe(true)`, or `toEqual(expected)` | `toBeTruthy()` passes for `1`, `"any string"`, `[]`, `{}`. It does not verify the value is what you expect |
| `toBeFalsy()` | `toBeUndefined()`, `toBeNull()`, `toBe(false)` | Same problem in reverse |
| `toEqual(expect.anything())` | `toEqual(expect.objectContaining({...}))` | Asserts nothing about shape |
| `expect(arr.length).toBeGreaterThan(0)` | `expect(arr).toHaveLength(expectedCount)` | Verifies exact count, not just "some" |

When asserting on objects returned from services, assert specific field values, not just existence. `expect(result.data.status).toBe('COMPLETED')` is a real test. `expect(result.data).toBeTruthy()` is not.

## Test Data

Use a fake data generator to produce test data. Never use hardcoded static values like `"test@example.com"`, `"John Doe"`, or `"password123"` in test setup.

Static values hide couplings. A test passing with `"test@example.com"` might fail with `"María.O'Connor+tag@subdomain.example.co.uk"`. Fake generators catch these edge cases.

**Seeding:** seed the generator per test file or describe block. Same seed produces the same sequence on every run.

| Language | Library |
|----------|---------|
| TypeScript / JavaScript | `@faker-js/faker` |
| Python | `faker` |
| Go | `gofakeit` |
| Ruby | `faker` |
| Rust | `fake` |
| Java / Kotlin | `datafaker` |

```typescript
// Bad: static values hide edge cases
const user = { name: 'John Doe', email: 'test@example.com' };

// Good: realistic, deterministic via seed
import { faker } from '@faker-js/faker';
faker.seed(12345);
const user = { name: faker.person.fullName(), email: faker.internet.email() };
```

During code review, static test data is a **blocking issue** with the same severity as mocking internal infrastructure.

## Zero Warnings in Test Output

Apply [`checklists/checklist.md`](../checklists/checklist.md) category 17. A clean test run means zero failures AND zero warnings. Test runner warnings, deprecation notices, and console warnings during test execution all count. A noisy test suite trains developers to ignore output, which means real failures get missed.

## Test Naming

- Describe behavior, not implementation
- **NEVER** reference ticket/task IDs in test names
- Use: `should create user with valid email`

## Coverage

- New code: 95%+ coverage
- Changed files and files directly related to the changes: 95%+ coverage
- Existing code: do not reduce coverage
- **Coverage is a delivery gate.** No task is declared complete until every changed or related file meets 95%+ across statements, branches, functions, and lines. "Related" means files that import from, are imported by, or share a data contract with a changed file. Run the coverage tool scoped to changed files with fresh output. "It should pass" is not evidence.
- **Agent-delegated work included.** When agents implement code, their deliverables must meet the same 95%+ threshold. The orchestrator must verify coverage after agent work completes, not assume it.

## Write-Path Tests (MANDATORY)

Any new or modified write path ships two tests beyond its behavior tests. A write path is any code that persists, mutates shared state, charges, sends, or enqueues: an endpoint, a queue consumer, a webhook receiver, a scheduled job, a service method that writes.

Coverage percentage does not substitute for these. A handler at 100% line coverage can still create two rows when two requests arrive together, because the line that races was executed exactly once by the test.

### Test 1: concurrent duplicates

Fire N identical calls in parallel, N at 10 or more, and assert the invariant rather than the timing.

```typescript
it('creates exactly one order when the same request arrives ten times at once', async () => {
  const payload = buildOrderPayload();

  const results = await Promise.allSettled(
    Array.from({ length: 10 }, () => createOrder(payload)),
  );

  expect(await db.order.count({ where: { idempotencyKey: payload.idempotencyKey } })).toBe(1);
  expect(results.every((result) => result.status === 'fulfilled')).toBe(true);
});
```

### Test 2: sequential duplicates

Call twice in sequence. Assert one effect and a replayed response, not merely the absence of a crash.

```typescript
it('replays the first response when the same key is used twice', async () => {
  const payload = buildOrderPayload();

  const first = await createOrder(payload);
  const second = await createOrder(payload);

  expect(second.body.id).toBe(first.body.id);
  expect(await db.order.count({ where: { idempotencyKey: payload.idempotencyKey } })).toBe(1);
});
```

### Rules for both

- Run against the real database. Isolation-level behavior is part of what is under test, and no mock reproduces it.
- Assert the loser's outcome, not only the winner's. A test that ignores what the second caller received tolerates a 500.
- Restart the process between the two calls when the path uses a deduplication store. An in-memory store passes every other test and fails this one, which is the point.
- Seed the fake data generator so every parallel call carries an identical payload.
- When the path is genuinely single-writer, say so in one line where the tests would be, and name what enforces it.

Shapes for narrower windows, including the barrier pattern, are in [`../standards/concurrency.md`](../standards/concurrency.md). Idempotency-specific cases, including fingerprint mismatch and TTL expiry, are in [`../standards/idempotency.md`](../standards/idempotency.md).

## Test Scenario Planning

When planning non-trivial tasks, generate test scenarios before implementing. Scenarios become acceptance criteria: the task is only done when all pass.

### Requirement Traceability

Map each requirement to specific test scenarios:

| Requirement | Test Scenario | Type | Priority |
|-------------|---------------|------|----------|
| User can create X | `should create X with valid data` | Integration | P0 |
| X validates email | `should reject invalid email format` | Unit | P0 |

### Priority Definitions

- **P0**: Critical path, core behavior. Failure means broken feature. Every requirement needs at least one.
- **P1**: Security, integration points, important edge cases.
- **P2**: Performance, accessibility, backward compatibility. Add when the task touches that area.

### Required Categories

1. **Happy path**: All success scenarios with valid inputs. One scenario per distinct success outcome.
2. **Edge cases**: Boundary values, empty/null/zero, special characters, max lengths.
3. **Error handling**: Invalid inputs, missing fields, unauthorized access, resource not found.
4. **Security**: Auth bypass attempts, injection, input sanitization. Include when the task touches APIs or auth.
5. **Integration points**: External service failures, timeouts, contract changes. Include when calling external services.

### Critical Scenarios Beyond Happy Path

These scenarios catch bugs that standard happy-path and validation tests miss. Include them when the task touches the relevant area.

| Scenario | What to test | When to include |
|----------|-------------|-----------------|
| Hidden effect | A failed operation (auth failure, validation error) does not mutate data. Assert both the error response AND that the database is unchanged | Write operations with validation |
| Overdoing | An operation only affects its target. Create a control record, perform the operation on a different record, verify the control is untouched | Bulk operations, deletes, updates |
| Zombie process | A startup failure causes process exit with proper logging, not a silent broken state serving errors | Service initialization, health checks |
| Slow collaborator | An external dependency times out. Verify retry behavior, proper logging, and appropriate error response (503) | External service integrations |
| Poisoned message | A malformed or invalid payload sent to a queue consumer is rejected gracefully, not retried in an infinite loop | Message queue consumers |
| Contract drift | API responses match the documented schema (OpenAPI, GraphQL SDL). Catches silent schema drift between docs and code | API endpoints with published contracts |

### Skip for Trivial Changes

Typos, config values, single-line fixes with no behavior change: a short list of 1-3 scenarios or "no new scenarios, existing tests cover this" is enough.

## Deterministic Tests

Every test must produce the same result on every run, on every machine. A test that passes 99% of the time is a broken test.

**Never depend on:**

| Source of flakiness | Fix |
|---------------------|-----|
| Current time | Inject a fixed clock or mock `Date.now()` |
| Random values | Seed the fake data generator per test file. Never use unseeded random generation |
| Network calls | Mock external APIs (allowed by mock policy) |
| Shared database state | Isolate per test: unique IDs, transactions that rollback, or fresh schema |
| Test execution order | No shared mutable state between tests. Each test sets up its own data |
| Timing and delays | Never use `setTimeout` or `sleep` in assertions. Use deterministic signals (events, callbacks, polling with timeout) |
| File system | Use temp directories, clean up in `afterEach` |

If a test fails intermittently, fix or delete it. Flaky tests erode trust in the entire suite and train developers to ignore failures.

## Test Tagging

Tag tests for selective execution. Fast feedback during development, full verification in CI.

| Tag | When to run | What it contains |
|-----|-------------|-----------------|
| `@unit` | Every save / pre-commit | Pure functions, no I/O |
| `@integration` | Pre-push / CI | Real database, real services |
| `@e2e` | CI only | Full user flows, browser or HTTP |
| `@slow` | CI only | Tests exceeding 5 seconds |
| `@smoke` | Post-deploy | Critical path verification |

Use the test runner's native tagging: Jest `--testPathPattern`, Vitest `--reporter`, pytest `-m`, Go build tags, JUnit `@Tag`. Keep the taxonomy flat; three to five tags are enough for most projects.

## Test Environment Sync

When changing environment variable schemas, validation rules, or defaults, update ALL environment files in the same commit. A mismatch between the env schema and `.env.test` causes mass test failures that look like code bugs.

| Change | Files to update |
|--------|----------------|
| Add/remove env var in validation schema | `.env.example`, `.env.test`, CI workflow env section, Docker Compose env section |
| Change env var default | `.env.test` if tests relied on the old default |
| Change env var from optional to required | `.env.test` must provide a value |
| Remove env var | Grep all `.env*` files and CI configs for references |

When changing the database schema, Prisma, migrations, push to both dev and test databases before running tests. Use the connection string from `.env.test`, not a manually constructed one.

## Test Resource Isolation

Tests running in parallel must not compete for shared resources.

- **Ports**: use random or OS-assigned ports, port 0. Never hardcode, 3000, 8080: they fail in parallel runs or when the port is in use
- **Database schemas**: use per-test or per-worker schemas, unique database names, or transactional rollback to prevent test data collisions
- **File system**: use OS-provided temp directories with unique prefixes per test. Clean up in `afterEach`
- **Environment variables**: restore originals after each test. Leaked changes cause order-dependent failures

## Responsive and Viewport Testing

Every page and component must render correctly on the smallest supported viewport. A layout that works on desktop but breaks on mobile is a bug.

- Test on 320px width, iPhone SE as the minimum. If it works at 320px, it works everywhere
- E2E tests must include at least one mobile viewport test per page using Playwright's `page.setViewportSize({ width: 375, height: 667 })`
- Verify: no horizontal overflow, no truncated buttons, no overlapping elements, no unreadable text
- Tables must either scroll horizontally or collapse into a card layout on mobile
- Page headers must stack vertically on mobile (`flex-col gap-4 sm:flex-row`)

## Benchmark Methodology

When comparing implementations or measuring performance:

- **Use median, p50, not mean.** GC pauses, JIT warmup, and outliers distort the mean. Report p50, p95, and p99
- **Include the runtime version.** Results change across versions. Record language version, runtime, and date
- **Audit for correctness.** A silent error produces misleading "fast" results. Verify the benchmark exercises the intended code path
- **Measure with realistic data.** Micro-benchmarks with 10 items do not predict behavior with 10,000 items. Use representative data sizes and realistic code paths

## Snapshot Testing

Snapshot tests serialize output and compare it against a stored reference. They catch unintended changes but create maintenance burden when used carelessly.

**When snapshots are appropriate:**

- Serialized output that is expensive to assert field-by-field: complex JSON responses, GraphQL query results, CLI output formatting
- Rendered component trees where the exact markup matters, like design system components
- Generated code, SQL, or config where the full output should be reviewed on change

**When snapshots are inappropriate:**

- Business logic. A snapshot passing tells you "nothing changed", not "the behavior is correct". Use explicit assertions
- Data structures that change frequently. API responses with timestamps, IDs, or version fields generate constant snapshot updates that train developers to blindly approve changes
- Large objects where a meaningful diff is hard to spot. If the snapshot is 500 lines, nobody reads the diff carefully

**Rules:**

- Review every snapshot update in the diff. Blindly running `--update` defeats the purpose
- Keep snapshots small. Extract the relevant subset before snapshotting instead of capturing the entire response
- Use inline snapshots when the output is short enough to read in the test file. External `.snap` files are harder to review
- Never snapshot non-deterministic values. Strip or mask timestamps, UUIDs, and random tokens before comparing
- When a snapshot test fails during refactoring, check if it must be an explicit assertion instead. If the test name does not describe a specific behavior, convert it

## Contract Testing

When services communicate across network boundaries with independent deployment cadences, use consumer-driven contract testing.

- The consumer defines expected interactions and generates a contract file
- The provider verifies against the contract in its own CI pipeline
- Use a contract broker for sharing contracts between services
- Run `can-i-deploy` checks in CI before deploying any service update
- Contract tests replace exhaustive E2E tests for service interaction verification
- Use contract testing when: microservices with multiple consumers, independent release cadences
- Use integration testing when: monolithic application, tightly coupled services, single deployment unit

## Performance Regression Testing

Detect performance regressions before they reach production.

- Establish baselines for API latency, page load time, and bundle size
- Compare before/after on every PR. Alert on p95 latency increase >10% or bundle size increase >5%
- Use median, p50 for primary reporting, not mean. GC pauses and outliers distort the mean
- Report p50, p95, and p99 with runtime version and date
- Verify benchmarks exercise the intended code path. Silent errors produce misleading "fast" results
- Use realistic data sizes. Micro-benchmarks with 10 items do not predict behavior with 10,000 items

## Enforcement

Enforced by: [`hooks/mock-internal-blocker.py`](../hooks/mock-internal-blocker.py).
Enforced by: [`hooks/tdd-gate.py`](../hooks/tdd-gate.py).
