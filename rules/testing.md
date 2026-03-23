# Testing

## Philosophy

Tests should verify real behavior, not mock behavior.

## Priority

1. **Integration** (preferred): real database, real services
2. **E2E**: full user flows
3. **Unit** (fallback): pure functions only

## Mocks Policy (STRICT)

**Allowed:** External third-party APIs outside your control, Time/Date, Randomness

**NEVER Mock:**
- **Database**: connect to a real database. Add it to docker-compose for the test environment. Use `beforeAll()` to seed, `afterAll()` to clean up
- **Redis, caches, queues**: connect to real instances. Add them to docker-compose
- **Your own services and modules**: if the code calls an internal service, the test calls the real service. Mocking your own code proves the mock works, not the code

A test that mocks infrastructure it depends on may pass while the actual integration is broken. This is worse than having no test at all. During code review, mocking internal infrastructure is a **blocking issue**.

## Test Structure (AAA Pattern)

Every test MUST use these exact Arrange-Act-Assert comments:

```
// Arrange
// Act
// Assert
```

Never append descriptions or colons: `// Act`, not `// Act: do something`. If a test needs more context, it is too complex. Split or rename.

No other comments are permitted anywhere in a test body. No inline comments between statements, no section labels, no explanatory notes. The three markers are the complete comment budget for a test. If a line between `// Arrange` and `// Act` needs a comment to make sense, the test setup is too complex: extract a helper or split the test.

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

A clean test run means zero failures AND zero warnings. Test runner warnings, deprecation notices, and console warnings during test execution all count.

- Fix warnings from the test runner itself: experimental API notices, configuration deprecations, plugin compatibility issues
- Fix warnings emitted by the code under test: runtime deprecation calls, console.warn output, driver warnings. If the code warns during a test, either the code has a problem or the test is exercising a deprecated path
- Never let warning noise accumulate. A test suite that routinely prints 50 warnings trains developers to ignore the output, which means real failures get missed

## Test Naming

- Describe behavior, not implementation
- **NEVER** reference ticket/task IDs in test names
- Use: `should create user with valid email`

## Coverage

- New code: 80%+ coverage
- Existing code: do not reduce coverage

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

## Test Resource Isolation

Tests running in parallel must not compete for shared resources.

- **Ports**: use random or OS-assigned ports (port 0). Never hardcode (3000, 8080): they fail in parallel runs or when the port is in use
- **Database schemas**: use per-test or per-worker schemas, unique database names, or transactional rollback to prevent test data collisions
- **File system**: use OS-provided temp directories with unique prefixes per test. Clean up in `afterEach`
- **Environment variables**: restore originals after each test. Leaked changes cause order-dependent failures

## Benchmark Methodology

When comparing implementations or measuring performance:

- **Use median (p50), not mean.** GC pauses, JIT warmup, and outliers distort the mean. Report p50, p95, and p99
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
