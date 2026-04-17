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
- **Database**: connect to a real database. Add it to docker-compose. Use `beforeAll()` to seed, `afterAll()` to clean up
- **Redis, caches, queues**: connect to real instances. Add them to docker-compose
- **Your own services and modules**: if the code calls an internal service, the test calls the real service. Mocking your own code proves the mock works, not the code

During code review, mocking internal infrastructure is a **blocking issue**.

## Test Structure (AAA Pattern)

Every test MUST use these exact comments:

```
// Arrange
// Act
// Assert
```

Never append descriptions or colons. No other comments are permitted anywhere in a test body. If a line between `// Arrange` and `// Act` needs a comment, the test setup is too complex: extract a helper or split the test.

## Assertion Specificity

Use the most specific assertion available.

| Avoid | Use instead |
|-------|-------------|
| `toBeTruthy()` | `toBeDefined()`, `toBe(true)`, or `toEqual(expected)` |
| `toBeFalsy()` | `toBeUndefined()`, `toBeNull()`, `toBe(false)` |
| `toEqual(expect.anything())` | `toEqual(expect.objectContaining({...}))` |
| `expect(arr.length).toBeGreaterThan(0)` | `expect(arr).toHaveLength(expectedCount)` |

When asserting on objects, assert specific field values, not just existence.

## Test Data

Never use hardcoded static values like `"test@example.com"`, `"John Doe"`, or `"password123"` in test setup. During code review, static test data is a **blocking issue**.

Seed the generator per test file or describe block. Same seed produces the same sequence on every run.

| Language | Library |
|----------|---------|
| TypeScript / JavaScript | `@faker-js/faker` |
| Python | `faker` |
| Go | `gofakeit` |
| Ruby | `faker` |
| Rust | `fake` |
| Java / Kotlin | `datafaker` |

```typescript
import { faker } from '@faker-js/faker';
faker.seed(12345);
const user = { name: faker.person.fullName(), email: faker.internet.email() };
```

## Zero Warnings in Test Output

Apply `checklists/checklist.md` category 17. A clean test run means zero failures AND zero warnings. Test runner warnings, deprecation notices, and console warnings all count.

## Test Naming

- Describe behavior, not implementation
- **NEVER** reference ticket/task IDs in test names
- Use: `should create user with valid email`

## Coverage

- New code: 95%+ coverage
- Changed files and files directly related to the changes: 95%+ coverage
- Existing code: do not reduce coverage
- **Coverage is a delivery gate.** No task is declared complete until every changed or related file meets 95%+ across statements, branches, functions, and lines. "Related" means files that import from, are imported by, or share a data contract with a changed file. Run the coverage tool scoped to changed files with fresh output
- **Agent-delegated work included.** The orchestrator must verify coverage after agent work completes, not assume it

## Test Scenario Planning

Generate test scenarios before implementing non-trivial tasks. Scenarios become acceptance criteria.

### Requirement Traceability

| Requirement | Test Scenario | Type | Priority |
|-------------|---------------|------|----------|
| User can create X | `should create X with valid data` | Integration | P0 |
| X validates email | `should reject invalid email format` | Unit | P0 |

### Priority Definitions

- **P0**: Critical path, core behavior. Every requirement needs at least one
- **P1**: Security, integration points, important edge cases
- **P2**: Performance, accessibility, backward compatibility. Add when the task touches that area

### Required Categories

1. **Happy path**: All success scenarios with valid inputs
2. **Edge cases**: Boundary values, empty/null/zero, special characters, max lengths
3. **Error handling**: Invalid inputs, missing fields, unauthorized access, resource not found
4. **Security**: Auth bypass attempts, injection, input sanitization. Include when touching APIs or auth
5. **Integration points**: External service failures, timeouts, contract changes. Include when calling external services

### Critical Scenarios Beyond Happy Path

| Scenario | What to test | When to include |
|----------|-------------|-----------------|
| Hidden effect | A failed operation does not mutate data. Assert error response AND database unchanged | Write operations with validation |
| Overdoing | An operation only affects its target. Create a control record, verify it is untouched | Bulk operations, deletes, updates |
| Zombie process | A startup failure causes process exit with proper logging, not a silent broken state | Service initialization, health checks |
| Slow collaborator | An external dependency times out. Verify retry, logging, and 503 response | External service integrations |
| Poisoned message | A malformed payload to a queue consumer is rejected gracefully, not retried infinitely | Message queue consumers |
| Contract drift | API responses match the documented schema (OpenAPI, GraphQL SDL) | API endpoints with published contracts |

### Skip for Trivial Changes

Typos, config values, single-line fixes: 1-3 scenarios or "no new scenarios, existing tests cover this" is enough.

## Deterministic Tests

Every test must produce the same result on every run, on every machine. A test that passes 99% of the time is a broken test.

| Source of flakiness | Fix |
|---------------------|-----|
| Current time | Inject a fixed clock or mock `Date.now()` |
| Random values | Seed the fake data generator per test file |
| Network calls | Mock external APIs (allowed by mock policy) |
| Shared database state | Isolate per test: unique IDs, transactions that rollback, or fresh schema |
| Test execution order | No shared mutable state between tests. Each test sets up its own data |
| Timing and delays | Never use `setTimeout` or `sleep` in assertions. Use deterministic signals |
| File system | Use temp directories, clean up in `afterEach` |

If a test fails intermittently, fix or delete it.

## Test Tagging

| Tag | When to run | What it contains |
|-----|-------------|-----------------|
| `@unit` | Every save / pre-commit | Pure functions, no I/O |
| `@integration` | Pre-push / CI | Real database, real services |
| `@e2e` | CI only | Full user flows, browser or HTTP |
| `@slow` | CI only | Tests exceeding 5 seconds |
| `@smoke` | Post-deploy | Critical path verification |

## Test Environment Sync

When changing environment variable schemas, validation rules, or defaults, update ALL environment files in the same commit.

| Change | Files to update |
|--------|----------------|
| Add/remove env var in validation schema | `.env.example`, `.env.test`, CI workflow env section, Docker Compose env section |
| Change env var default | `.env.test` if tests relied on the old default |
| Change env var from optional to required | `.env.test` must provide a value |
| Remove env var | Grep all `.env*` files and CI configs for references |

When changing the database schema, push to both dev and test databases before running tests. Use the connection string from `.env.test`.

## Test Resource Isolation

Tests running in parallel must not compete for shared resources.

- **Ports**: use random or OS-assigned ports (port 0). Never hardcode
- **Database schemas**: use per-test or per-worker schemas, unique database names, or transactional rollback
- **File system**: use OS-provided temp directories with unique prefixes per test. Clean up in `afterEach`
- **Environment variables**: restore originals after each test

## Responsive and Viewport Testing

Every page and component must render correctly on the smallest supported viewport.

- Test on 320px width (iPhone SE) as the minimum
- E2E tests must include at least one mobile viewport test per page: `page.setViewportSize({ width: 375, height: 667 })`
- Verify: no horizontal overflow, no truncated buttons, no overlapping elements, no unreadable text
- Tables must scroll horizontally or collapse into a card layout on mobile
- Page headers must stack vertically on mobile (`flex-col gap-4 sm:flex-row`)

## Benchmark Methodology

- Use median (p50), not mean. Report p50, p95, and p99
- Include the runtime version and date. Results change across versions
- Verify the benchmark exercises the intended code path. A silent error produces misleading "fast" results
- Measure with realistic data sizes. Micro-benchmarks with 10 items do not predict behavior with 10,000 items

## Snapshot Testing

**When appropriate:** serialized output expensive to assert field-by-field, design system component trees, generated code or SQL.

**When inappropriate:** business logic, frequently-changing data structures with timestamps or IDs, large objects where diffs are unreadable.

**Rules:**
- Review every snapshot update in the diff. Blindly running `--update` defeats the purpose
- Keep snapshots small. Extract the relevant subset before snapshotting
- Use inline snapshots when the output is short enough to read in the test file
- Never snapshot non-deterministic values. Strip or mask timestamps, UUIDs, and random tokens
- When a snapshot test fails during refactoring, check if it should be an explicit assertion instead

## Contract Testing

When services communicate across network boundaries with independent deployment cadences, use consumer-driven contract testing.

- The consumer defines expected interactions and generates a contract file
- The provider verifies against the contract in its own CI pipeline
- Run `can-i-deploy` checks in CI before deploying any service update
- Use contract testing when: microservices with multiple consumers, independent release cadences
- Use integration testing when: monolithic application, tightly coupled services, single deployment unit

## Performance Regression Testing

- Establish baselines for API latency, page load time, and bundle size
- Alert on p95 latency increase >10% or bundle size increase >5% on every PR
- Report p50, p95, and p99 with runtime version and date
- Verify benchmarks exercise the intended code path

## Chaos Engineering

Verifies that a system tolerates failures it is designed to handle. Apply only to services that declare fault tolerance (retries, circuit breakers, fallbacks).

**Process:**
1. **Define steady state.** Measurable: p99 latency, error rate, queue consumer lag
2. **Form a hypothesis.** Example: "If the primary database is unavailable for 10 seconds, the service serves cached reads and recovers within 30 seconds"
3. **Limit blast radius.** Run in staging. Never in production without a kill switch and on-call engineer
4. **Inject the fault.** Network latency (50-500ms), packet loss, unavailability, disk full, CPU saturation, clock skew
5. **Observe.** Did steady-state hold? If not, the declared fault tolerance does not exist
6. **Fix, then re-run.** A gap is a failing test. Fix it, confirm with another run

**Rules:**
- Each experiment must have a documented hypothesis, stop condition, and rollback procedure before it runs
- Never target data integrity. Scope to availability and latency faults only
- A service with no retry logic, no circuit breaker, and no fallback needs those features first, not chaos tests
- Automate only after validating manually at least twice

| Fault | Validates |
|-------|-----------|
| Dependency timeout (3x p99 latency) | Timeout configuration, circuit breaker open threshold |
| Dependency unavailable | Circuit breaker, fallback logic, error classification |
| Slow dependency | Timeout + retry interaction, deadline propagation |
| High CPU | Worker pool limits, request queuing behavior |
| Memory pressure | GC impact on latency, OOM behavior |
| Clock skew | JWT expiry handling, distributed lock TTL behavior |
