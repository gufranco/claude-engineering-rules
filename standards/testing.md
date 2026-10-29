# Testing

## Philosophy

Tests should verify real behavior, not mock behavior.

## Priority

1. **Integration**, preferred: real database, real services
2. **E2E**: full user flows
3. **Unit**, fallback: pure functions only

## What To Test

If a user would notice it broken, it needs a test. Test the behavior users depend on, through the path the real application uses, and leave implementation details untested.

- **Leave to the compiler what the compiler proves.** A test never restates a guarantee the type system already enforces: a return shape, a required field, an argument type. Spend tests on runtime behavior the compiler cannot verify, such as ordering, the relationships left after a write, conflict resolution, and business-rule edge cases.
- **Extract component state logic before wiring it.** Move the reducer, its state transitions, and their helpers out of the component into a pure module beside it. Test that module directly, state and action in, state out, one red-green cycle per action or edge case. Wire it into the component only after its tests are green, so the component stays thin: it dispatches actions and renders state.

```typescript
it('marks a pending task done when it is completed', () => {
  // Arrange
  const taskId = faker.string.uuid();
  const state = { tasks: [{ id: taskId, status: TaskStatus.Pending }] };

  // Act
  const next = taskReducer(state, { type: TaskAction.Complete, taskId });

  // Assert
  expect(next.tasks).toEqual([{ id: taskId, status: TaskStatus.Done }]);
});
```

Provenance: 2026-10-12, owner request. Adopted from the ai-hero-cli what-to-test skill and the course-video-manager do-work DB-TDD and FRONTEND-TDD guides.

## Mocks Policy (STRICT)

**Allowed:** External third-party APIs outside your control, systems you do not own and cannot run locally, Time/Date, Randomness

**NEVER Mock:**
- **Database**: connect to a real database. Add it to docker-compose for the test environment. Use `beforeAll()` to seed, `afterAll()` to clean up
- **Redis, caches, queues**: connect to real instances. Add them to docker-compose
- **Your own services and modules**: if the code calls an internal service, the test calls the real service. Mocking your own code proves the mock works, not the code

A test that mocks infrastructure it depends on may pass while the actual integration is broken. This is worse than having no test at all. During code review, mocking internal infrastructure is a **blocking issue**.

### Per-Operation Ports For Third-Party APIs

Wrap each third-party operation in its own function on a typed port, rather than one generic fetcher that branches on method and path. A test then stubs exactly the operation it exercises, the stub carries that operation's types, and an unstubbed operation fails loudly instead of falling through a shared branch.

```typescript
interface BillingPort {
  readonly createCharge: (input: ChargeInput) => Promise<Charge>;
  readonly refundCharge: (chargeId: ChargeId) => Promise<Refund>;
}
```

This shape applies only to the allowed mock surface above. Internal services stay real in tests.

Provenance: 2026-10-12, owner request. Adopted from the ai-engineer-workshop tdd skill's mocking guide.

## Test Structure

Every test follows Arrange, Act, Assert, in that order. The three phases are mandatory, their order is fixed, and each phase is labeled.

Each block opens with its marker comment in the language's comment syntax: `// Arrange`, `// Act`, `// Assert` in C-family languages, `# Arrange`, `# Act`, `# Assert` in Python, Ruby, and shell, and the equivalent elsewhere. A marker is the bare word. Nothing follows it on the line, so `// Assert: status code` is a violation. The three markers are the only comments a test carries; the comment ban in [`code-style.md`](../rules/code-style.md) "Comments" covers everything else in a test exactly as it covers production code, with the same exemption for tool directives.

Provenance: 2026-10-12, an owner decision that restores the markers banned on 2026-09-18. The markers make the phase boundaries scannable at a glance, and every other comment stays banned so the code remains the documentation.

### The three blocks

A test body is three marked blocks separated by exactly one blank line each.

| Phase | Contains | Must not contain |
|-------|----------|------------------|
| Arrange | Fake data, seeded records, fixtures, stubs for the allowed mock surface, the input value | Any call to the unit under test, any assertion |
| Act | Exactly one call to the unit under test, with its result bound to a name when it returns one; a command that returns nothing stays unbound and Assert checks its observable effect | Setup, branching, loops, a second call to the unit under test |
| Assert | Assertions on the bound result and on observable side effects | New setup, a second call to the unit under test |

Three supporting rules keep the blocks readable:

- **The test name carries the intent.** It states the behavior under test, so the markers stay bare.
- **Named helpers carry the setup.** When the arrange block needs explaining, extract it into a function whose name does the explaining: `seedAccountAtDailyLimit()` beats six lines of literals.
- **One act per test.** Two calls to the unit under test are two behaviors, so they are two tests.

If a step inside a test would need a comment beyond its marker to make sense, the test is too complex. Extract a helper or split the test.

```typescript
it('rejects a transfer that exceeds the daily limit', async () => {
  // Arrange
  const account = await seedAccount({ dailyLimit: 500, transferredToday: 450 });

  // Act
  const result = await transfer(account.id, 100);

  // Assert
  expect(result.status).toBe(TransferStatus.Rejected);
  expect(result.reason).toBe(RejectionReason.DailyLimitExceeded);
});
```

### The same shape in other languages

```python
def test_rejects_a_transfer_that_exceeds_the_daily_limit(db):
    # Arrange
    account = seed_account(db, daily_limit=500, transferred_today=450)

    # Act
    result = transfer(account.id, 100)

    # Assert
    assert result.status is TransferStatus.REJECTED
    assert result.reason is RejectionReason.DAILY_LIMIT_EXCEEDED
```

```go
func TestRejectsTransferExceedingDailyLimit(t *testing.T) {
    // Arrange
    account := seedAccount(t, accountOpts{DailyLimit: 500, TransferredToday: 450})

    // Act
    result, err := Transfer(account.ID, 100)

    // Assert
    require.NoError(t, err)
    require.Equal(t, StatusRejected, result.Status)
    require.Equal(t, ReasonDailyLimitExceeded, result.Reason)
}
```

### Violations

| Violation | Why it fails | Fix |
|-----------|--------------|-----|
| A block with no marker, or a marker out of order | The phase boundary is no longer explicit | Open each block with its bare marker, in order |
| Text after a marker, `# Act: call the service` | The marker became a prose comment | Keep the bare word; move the intent into the test name |
| Any other comment in the test | Banned by the comment policy and by the hook | Delete it; rename, extract a helper, or split the test |
| One unbroken block of statements | The reader has to parse every line to find the call under test | Separate the three marked blocks with one blank line each |
| Assertion inside the arrange block | Asserts the fixture, not the behavior | Move the guarantee into the helper, or into its own test of the helper |
| Setup between the act and the assertions | The reader can no longer tell which state the assertions describe | Move it above the act |
| Two calls to the unit under test | Two behaviors in one test; the failure message names neither | Split into two tests |
| Act and assert on one line, `expect(transfer(id, 100)).toBe(...)` | The act disappears into the assertion | Bind the result in Act, then assert on the name |

### Expected throws keep three blocks

Bind the call in Act without awaiting or invoking it, then assert on the binding. No test fuses act and assert.

```typescript
it('throws when the account does not exist', async () => {
  // Arrange
  const missingId = faker.string.uuid();

  // Act
  const pending = transfer(missingId, 100);

  // Assert
  await expect(pending).rejects.toThrow(AccountNotFoundError);
});
```

A synchronous call binds a thunk: `const act = () => parse(input);`, then `expect(act).toThrow(ParseError);`. In Python, capture the exception in Act and assert on it:

```python
def test_rejects_an_unknown_account(db):
    # Arrange
    missing_id = fake.uuid4()

    # Act
    with pytest.raises(AccountNotFound) as raised:
        transfer(missing_id, 100)

    # Assert
    assert raised.value.account_id == missing_id
```

### Shared arrangement

Shared setup moves to `beforeEach` or a fixture. The Arrange block stays in the test and binds what the act uses from the shared fixture, so every test still carries three marked blocks.

```typescript
describe('transfer', () => {
  let account: Account;

  beforeEach(async () => {
    account = await seedAccount({ dailyLimit: 500 });
  });

  it('settles a transfer within the daily limit', async () => {
    // Arrange
    const amount = 100;

    // Act
    const result = await transfer(account.id, amount);

    // Assert
    expect(result.status).toBe(TransferStatus.Settled);
  });
});
```

A test with no assertions is not a test, and a test with no act asserts nothing about the system.

## Assertion Specificity

Use the most specific assertion available. Vague assertions pass when they should fail.

| Avoid | Use instead | Why |
|-------|-------------|-----|
| `toBeTruthy()` | `toBeDefined()`, `toBe(true)`, or `toEqual(expected)` | `toBeTruthy()` passes for `1`, `"any string"`, `[]`, `{}`. It does not verify the value is what you expect |
| `toBeFalsy()` | `toBeUndefined()`, `toBeNull()`, `toBe(false)` | Same problem in reverse |
| `toEqual(expect.anything())` | `toEqual(expect.objectContaining({...}))` | Asserts nothing about shape |
| `expect(arr.length).toBeGreaterThan(0)` | `expect(arr).toHaveLength(expectedCount)` | Verifies exact count, not just "some" |

When asserting on objects returned from services, assert specific field values, not just existence. `expect(result.data.status).toBe('COMPLETED')` is a real test. `expect(result.data).toBeTruthy()` is not.

### Tautological Assertions

Every expected value comes from a source of truth independent of the code under test: a known-good literal, a worked example, or the spec. A tautological assertion recomputes the expected value the way the code computes it, so it passes by construction and can never disagree with the code.

| Tautology | Why it proves nothing | Use instead |
|-----------|-----------------------|-------------|
| `expect(add(a, b)).toBe(a + b)` | The test repeats the implementation; a shared bug passes | A worked example: `add(2, 3)` is `5` |
| `expected = items.reduce(...)`, then `expect(total).toBe(expected)` | Same algorithm on both sides of the assertion | The total computed by hand from the spec |
| A constant asserted equal to itself, `expect(MAX_RETRIES).toBe(MAX_RETRIES)` | Cannot fail | Assert the behavior the constant drives |
| A snapshot or fixture generated by the same code path it checks | The reference inherits every bug in the code | A reviewed snapshot, or explicit field assertions from the spec |

```typescript
it('totals the line items of an order', async () => {
  // Arrange
  const order = await seedOrder({ linePrices: [1000, 550] });

  // Act
  const total = await orderTotal(order.id);

  // Assert
  expect(total).toBe(1550);
});
```

The literal prices are the worked example, so they are the oracle, not the filler data [Test Data](#test-data) replaces with faker. Generate every field that does not feed the expected value with the seeded generator.

This section does not replace the database-count assertions in [Write-Path Tests](#write-path-tests-mandatory). Counting rows asserts an observable effect against a literal, which is an independent source of truth.

Provenance: 2026-10-12, threshold skipped because the user explicitly requested adoption. Adopted from the mattpocock/skills `tdd` guidance, whose CHANGELOG records tautological tests as an observed failure: an assertion recomputed the way the code computes it passes by construction and gives zero confidence.

### Assertions Are Never Weakened To Pass

When a change makes a test fail, the code is wrong until shown otherwise. Never delete, loosen, or skip an existing assertion or test case to make the change pass: no removed `expect`, no `toEqual` relaxed to `toBeDefined`, no `it.skip`, `xit`, `@pytest.mark.skip`, `t.Skip()`, or `#[ignore]`, no deleted test file. Fix the code, or, when the behavior the test pins was removed on purpose, say so and get the user's agreement before the test changes.

A banned edit gets replaced by an equivalent in practice. A team that wrote "don't edit the tests to make them pass" saw the agent delete the tests instead; a hook added afterwards was then deleted itself. So the rule is enforced mechanically on every path:

| Path | Enforced by | Response |
|---|---|---|
| Edit, MultiEdit, or Write that lowers the assertion or test-case count, or adds a skip marker, in a test file | [`tdd-gate.py`](../hooks/tdd-gate.py) through [`assertion_weakening.py`](../hooks/_lib/assertion_weakening.py) | Blocked; `TEST_WEAKENING_DISABLE=1` once, after the user agrees |
| `rm`, `git rm`, `unlink`, or `trash` of a test file | [`dangerous-command-blocker.py`](../hooks/dangerous-command-blocker.py) | Confirmation prompt to the user |

Replacing an assertion with a stricter one keeps the count and passes. Moving an assertion between the edits of one MultiEdit keeps the total and passes. Moving a test to another file is the legitimate case the bypass exists for.

## Test Data

Use a fake data generator to produce test data. Never use hardcoded static values like `"test@example.com"`, `"John Doe"`, or `"password123"` in test setup.

Static values hide couplings. A test passing with `"test@example.com"` might fail with `"María.O'Connor+tag@subdomain.example.co.uk"`. Fake generators catch these edge cases.

**Seeding:** seed the generator per test file or describe block. Same seed produces the same sequence on every run.

**Filler, not the input under test.** Generate filler values: emails, names, ids, timestamps, anything the assertion does not depend on. A literal that is itself the behavior under test stays literal, such as the exact command string a hook must block or the worked example an expected value comes from, because it is the oracle. Owner decision, 2026-10-12.

| Language | Library |
|----------|---------|
| TypeScript / JavaScript | `@faker-js/faker` |
| Python | `faker` |
| Go | `gofakeit` |
| Ruby | `faker` |
| Rust | `fake` |
| Java / Kotlin | `datafaker` |

**Bad:** static values hide edge cases.

```typescript
const user = { name: 'John Doe', email: 'test@example.com' };
```

**Good:** realistic values, deterministic through the seed.

```typescript
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

- **100% on every file.** Statements, branches, functions, and lines all reach 100% on every hand-written file, measured per file, never as a project average. With nothing excluded, a 100% total and 100% on every file are the same claim, so a tool that only gates the total, such as `--cov-fail-under=100`, still enforces it.
- **The measured set is every hand-written source file**: application code, scripts, hooks, command-line tools, and build helpers. Generated code and vendored third-party code are the only files left out, and they are left out by path in the coverage config.
- **No exclusion directives.** Never `pragma: no cover`, `pragma: no branch`, `istanbul ignore`, `c8 ignore`, `v8 ignore`, `node:coverage disable`, `coverage:ignore`, `#[coverage(off)]`, `[ExcludeFromCodeCoverage]`, `@codeCoverageIgnore`, `LCOV_EXCL_LINE`, or `:nocov:`, and never an `omit` or `coveragePathIgnorePatterns` entry for hand-written code. `if __name__ == "__main__":` and `if TYPE_CHECKING:` blocks are tested, through `runpy` or a subprocess that coverage follows, or refactored away.
- **A threshold only rises.** Every coverage threshold in config is 100. An edit that writes a lower one is a regression.
- **Coverage is a delivery gate.** No task is declared complete until every changed or related file is at 100%, and the project's own gate passes. "Related" means files that import from, are imported by, or share a data contract with a changed file. Run the coverage tool with fresh output. "It should pass" is not evidence.
- **Agent-delegated work included.** When agents implement code, their deliverables meet the same 100%. The orchestrator verifies coverage after agent work completes, never assumes it.
- **Coverage locates gaps; it is never the target.** Read the uncovered lines to find user-visible behavior that has no test, then test that behavior per [What To Test](#what-to-test). A test written only to move the number asserts nothing a user depends on. The 100% gate holds, and it is met by testing behavior.

### Code No Test Can Reach

A line no test can reach is a design defect, never an exception to the gate. It is one of three things:

| Cause | Fix |
|---|---|
| Dead code: a branch no input can take, a fallback for an import that always succeeds, a loop exit that never fires | Delete it |
| Hidden dependency: the clock, randomness, the filesystem, the network, the environment, process exit | Inject it, or move it into the imperative shell and drive the shell through its real seam, such as a subprocess, a temporary directory, or a stub binary on `PATH` |
| Defensive duplication: a check that a caller or the type system already guarantees | Remove it, or move it to the boundary where invalid input can actually arrive, and test it there |

Refactor until the line is covered or gone. A file that resists is a file whose design is wrong.

### 100% End-To-End

Every user-facing entry point has an end-to-end test that drives it the way a user does: each route, screen, command-line command, public endpoint, and job trigger. Every requirement scenario in the plan or living spec has one too. Keep the mapping explicit, entry point or scenario to the test that drives it, and a missing row fails the task.

The per-file 100% is measured across all suites combined. Integration and unit tests may cover error paths that an end-to-end run cannot reach, so the end-to-end obligation is completeness of entry points and scenarios, not a second per-file percentage.

### Enforcing The Floor

| Tool | Gate |
|---|---|
| pytest-cov | `--cov-fail-under=100` with `branch = True` |
| coverage.py | `fail_under = 100` under `[report]` |
| Node test runner | `--test-coverage-lines=100 --test-coverage-branches=100 --test-coverage-functions=100` |

[`hooks/coverage-exclusion-guard.py`](../hooks/coverage-exclusion-guard.py) blocks an edit that adds an exclusion directive to source or writes a threshold under 100 into a coverage config. It asks before a new omit or exclude entry, which is legitimate only for generated or vendored paths.

Provenance for the coverage-as-locator bullet: 2026-10-12, owner request, adopted from the ai-hero-cli what-to-test skill. Provenance for the 100% floor: 2026-10-28, owner request: unreachable code is treated as an architecture problem, sloppy code, or code to delete.

## Write-Path Tests (MANDATORY)

Any new or modified write path ships two tests beyond its behavior tests. A write path is any code that persists, mutates shared state, charges, sends, or enqueues: an endpoint, a queue consumer, a webhook receiver, a scheduled job, a service method that writes.

Coverage percentage does not substitute for these. A handler at 100% line coverage can still create two rows when two requests arrive together, because the line that races was executed exactly once by the test.

### Test 1: concurrent duplicates

Fire N identical calls in parallel, N at 10 or more, and assert the invariant rather than the timing.

```typescript
it('creates exactly one order when the same request arrives ten times at once', async () => {
  // Arrange
  const payload = buildOrderPayload();

  // Act
  const results = await Promise.allSettled(
    Array.from({ length: 10 }, () => createOrder(payload)),
  );

  // Assert
  expect(await db.order.count({ where: { idempotencyKey: payload.idempotencyKey } })).toBe(1);
  expect(results.every((result) => result.status === 'fulfilled')).toBe(true);
});
```

### Test 2: sequential duplicates

Call twice in sequence. Assert one effect and a replayed response, not merely the absence of a crash. The pair of calls is the act under test, so both sit in the Act block.

```typescript
it('replays the first response when the same key is used twice', async () => {
  // Arrange
  const payload = buildOrderPayload();

  // Act
  const first = await createOrder(payload);
  const second = await createOrder(payload);

  // Assert
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

Shapes for narrower windows, including the barrier pattern, are in [`../standards/concurrency.md`](concurrency.md). Idempotency-specific cases, including fingerprint mismatch and TTL expiry, are in [`../standards/idempotency.md`](idempotency.md).

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
| The developer's machine | Set the git identity inside any repository the test creates, point `HOME` at a temp directory before reading a dotfile, and assert each platform branch on the platform that takes it |

A test that passes only where the author ran it fails first in CI. Origin: `gufranco/claude-engineering-rules` commit `efb6501` on 2026-10-28 fixed three tests that passed only on a configured Mac, two that committed without a git identity and one whose branch was reached only through the personal settings-hygiene blocklist, and gave a darwin-only coverage branch an in-process test that runs on Linux too.

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

When changing the database schema, apply the change to the local dev database and the disposable test database before running tests. A schema-sync shortcut such as `prisma db push` is allowed on those two databases only; every other database receives the change through migrations, per [`orm-migrations.md`](orm-migrations.md) "Schema Sync Strategy". Use the connection string from `.env.test`, not a manually constructed one.

## Test Resource Isolation

Tests running in parallel must not compete for shared resources.

- **Ports**: use random or OS-assigned ports, port 0. Never hardcode, 3000, 8080: they fail in parallel runs or when the port is in use
- **Database schemas**: use per-test or per-worker schemas, unique database names, or transactional rollback to prevent test data collisions
- **File system**: use OS-provided temp directories with unique prefixes per test. Clean up in `afterEach`
- **Environment variables**: restore originals after each test. Leaked changes cause order-dependent failures

## Responsive and Viewport Testing

Every page and component must render correctly on the smallest supported viewport. A layout that works on desktop but breaks on mobile is a bug.

- Test on 320px width, iPhone SE as the minimum. If it works at 320px, it works everywhere
- E2E tests must include at least one mobile viewport test per page using Playwright's `page.setViewportSize({ width: 320, height: 568 })`, matching the 320px minimum
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
