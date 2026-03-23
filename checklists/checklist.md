# Checklist

Single source of truth for what to verify. Shared by completion gates (self-review during implementation), `/review` (code review), and `/assessment` (architecture audit).

Each consumer applies the checklist differently:

- **Completion gates:** after writing code and before declaring done, read the full diff and run through every applicable category. Fix issues found. Re-read. Repeat until clean.
- **`/review`:** checks items against the **diff**. Issues become review comments with explanation, impact, and fix example.
- **`/assessment`:** checks items against the **full implementation**. Evaluates whether patterns are present, partial, or missing.

Not every category applies to every change. Skip categories clearly irrelevant to the scope. A CLI tool does not need caching. A single-service app does not need saga.

---

## Code Level

### 1. Correctness

- [ ] Every function does exactly what its name promises
- [ ] Traced logic with at least three inputs: normal case, edge case, invalid case
- [ ] No off-by-one errors in loops, slices, or array access
- [ ] Null, undefined, and empty values handled on every code path
- [ ] Boolean logic correct: no inverted conditions, missing negations, or wrong operator precedence
- [ ] Return values checked on every call that can fail
- [ ] No type coercion traps: strict equality (`===`) where needed
- [ ] No unreachable code after early returns, throws, or breaks
- [ ] Switch statements have `break` and `default` where required
- [ ] Regex patterns correct, anchored, and safe from ReDoS
- [ ] Date/time handling timezone-aware with daylight saving edge cases considered
- [ ] Floating point comparisons use epsilon tolerance
- [ ] String handling encoding-safe with Unicode edge cases considered
- [ ] Recursive functions guaranteed to terminate with bounded stack depth

### 2. Security

- [ ] Full OWASP top 10 lens applied: injection, broken auth, sensitive data exposure, XXE, broken access control, misconfig, XSS, insecure deserialization, known vulnerable components, insufficient logging
- [ ] No secrets, tokens, or credentials in the diff
- [ ] Auth and authorization enforced on every new route. No IDOR
- [ ] Input validated and sanitized at every system boundary
- [ ] No sensitive data in responses, logs, or error messages
- [ ] No open redirects from user-controlled URLs
- [ ] No SSRF: server-side fetches validate destination against allowlist
- [ ] CSRF protection on state-changing endpoints

### 3. Error Handling

Error classification and typed error returns: `rules/code-style.md`. Retry parameters and HTTP status mapping: category 20.

- [ ] Every error path covered with context, not silently swallowed
- [ ] Error messages helpful for debugging without leaking internals
- [ ] Error propagation strategy consistent across modules
- [ ] No thrown exception that could crash a request handler unhandled
- [ ] Errors classified: transient (retry with backoff), permanent (fail immediately), or ambiguous (retry with limit, then fail)
- [ ] Error handler self-protecting: logging failure inside handler falls back to stdout

### 4. Concurrency

- [ ] No shared mutable state without synchronization
- [ ] No missing `await` on async calls
- [ ] No fire-and-forget promises that should be awaited
- [ ] No TOCTOU bugs: check-then-act sequences protected by database constraints, locks, or conditional writes
- [ ] No unhandled promise rejections

### 5. Data Integrity

- [ ] **Idempotent:** every write operation safe to execute twice with the same input. If not naturally idempotent, a guard prevents duplicate effects
- [ ] **Deduplicated:** natural dedup key identified with durable check-before-process. In-memory-only dedup is not acceptable
- [ ] **Atomic:** related writes wrapped in a transaction or conditional expression. No partial writes left to corrupt state
- [ ] Validation present at every system boundary: not just syntactic but semantic (positive amounts, valid date ranges, enum membership)
- [ ] Database constraints match application-level validation: unique constraints, foreign keys, check constraints
- [ ] Async processors have DLQ, partial batch failure reporting, dedup by message ID, and monitoring

### 6. Algorithmic Performance

Data structure selection guide and anti-pattern catalog: `standards/algorithmic-complexity.md`.

#### Complexity

- [ ] No O(n^2) or worse hidden in nested loops, repeated `.find()`, `.filter()` inside `.map()`
- [ ] No `.find()`, `.includes()`, or `.indexOf()` called inside a loop over another collection. Build a Map or Set first
- [ ] No string concatenation in loops. Collect in array, `.join()` at the end
- [ ] No `Array.shift()` in a while loop (O(n^2) from reindexing). Use a queue, pointer index, or reverse + pop
- [ ] No nested `.reduce()` with spread accumulator (O(n^2) from copying). Mutate the accumulator
- [ ] No sorting when only min/max/k-th element is needed. Use a heap or selection algorithm
- [ ] No re-sorting after single insertions. Use binary search + insert or a sorted data structure
- [ ] Sorting only when necessary, using the right algorithm for the data size

#### Data structures

- [ ] Data structures match the dominant operation. See `standards/algorithmic-complexity.md` decision guide
- [ ] Set for membership checks, Map for key-value lookups. Not array scans
- [ ] Queue or deque for FIFO processing. Not array + `.shift()`
- [ ] Heap or priority queue for priority ordering. Not sorted array with re-sort

#### Resource management

- [ ] No unbounded data loaded into memory. Streams or pagination for large datasets
- [ ] No allocations inside hot loops (object creation, string concatenation, closures)
- [ ] File handles, connections, and streams closed after use
- [ ] No synchronous I/O in async code paths
- [ ] No N+1 query patterns. Batch or join instead
- [ ] No blocking I/O in request handlers

#### Space complexity

- [ ] No unbounded caches. Every Map or object used as cache has a max size, TTL, or LRU eviction
- [ ] No closure leaks: closures in long-lived objects (event handlers, timers, singletons) do not capture large scopes
- [ ] No event listener accumulation: listeners registered in loops or hot paths have cleanup
- [ ] Recursive functions have bounded depth or use iteration with explicit stack
- [ ] `.map()` / `.filter()` chains on large datasets use a single loop or generators to avoid intermediate array allocations

### 7. Frontend Performance

Skip if no frontend code changed.

- [ ] No unnecessary re-renders. Dependencies in `useEffect`/`useMemo`/`useCallback` correct
- [ ] Large lists virtualized
- [ ] Images and assets optimized
- [ ] No blocking operations on the main thread
- [ ] Bundle size impact considered. No unnecessarily large dependencies added

### 8. Testing

Full testing philosophy, policies, and guidelines: `rules/testing.md`.

#### Coverage

- [ ] Every new function/method has tests
- [ ] Every code branch tested: success, each error case, each edge case
- [ ] Coverage on changed code at 80% or above
- [ ] Integration tests for database operations, not mocked unit tests

#### Test quality

- [ ] Tests follow AAA pattern with those exact comments: `// Arrange`, `// Act`, `// Assert`. No other comments in test bodies. See `rules/testing.md` for the full AAA policy
- [ ] Test names describe behavior, not implementation ("should reject expired token" not "test validateToken")
- [ ] Assertions specific enough to catch regressions. Not just `toBeTruthy()` when a specific value matters
- [ ] No test-only backdoors in production code
- [ ] Tests independent: no shared mutable state between tests, no ordering dependency
- [ ] Tests verify the behavior they claim to test, not just that no error was thrown
- [ ] Negative tests present: invalid input, unauthorized access, missing resources
- [ ] Boundary value tests: empty arrays, zero, max int, empty string, null
- [ ] Test data uses fake data generator with deterministic seed. No hardcoded static values. See `rules/testing.md` for the library table and seeding guidelines
- [ ] Contract tests at service boundaries: consumer expectations verified against provider responses
- [ ] Property-based tests for complex logic: invariants hold across randomized inputs, not just hand-picked examples

#### Determinism

- [ ] No dependency on current time, unseeded random values, network calls, shared database state, execution order, timing delays, or file system state. See `rules/testing.md` for the full flakiness table
- [ ] Snapshot tests strip non-deterministic values: timestamps, UUIDs, random tokens

#### Mock policy (STRICT, blocking issue)

See `rules/testing.md` for the full mock policy with rationale.

- [ ] Database, Redis, queues, and caches use real connections via docker-compose, with `beforeAll()` seed and `afterAll()` cleanup
- [ ] Own services and modules tested with real implementations, not mocks
- [ ] Only external third-party APIs, time, and randomness are mocked
- [ ] Any mock of internal infrastructure is a **blocking issue**

#### Snapshot policy

- [ ] Snapshots used only for serialized output, rendered component trees, or generated code. Not for business logic
- [ ] Snapshot updates reviewed in the diff, not blindly accepted
- [ ] Snapshots small and focused. No 500-line snapshots
- [ ] Non-deterministic values stripped or masked before comparing

#### Scenario planning and isolation

- [ ] Test scenario planning: each requirement mapped to test scenarios with P0/P1/P2 priority before implementation
- [ ] Test tagging for selective execution: `@unit`, `@integration`, `@e2e`, `@slow`, `@smoke`
- [ ] Test resource isolation: random ports, per-worker DB schemas, OS temp directories, env var restore after each test
- [ ] Hidden effect tests for write operations: failed operations do not mutate data. Assert both the error AND that the database is unchanged
- [ ] Overdoing tests for targeted operations: control records remain untouched after operating on a different record

### 9. Code Quality and Design

- [ ] Functions under 30 lines. If not, decomposable
- [ ] Single responsibility: each function does one thing
- [ ] No code duplication. DRY respected without premature abstraction
- [ ] No magic numbers or hardcoded strings. Constants named and extracted
- [ ] No dead code, commented-out code, or leftover debug statements
- [ ] Dependencies flow inward. Business logic does not import framework-specific modules
- [ ] Composition over inheritance
- [ ] Side effects isolated and explicit
- [ ] No over-engineering: no unnecessary abstractions, factories, or patterns for a single use case
- [ ] No under-engineering: no inline SQL strings, no god functions, no 500-line files
- [ ] All loops and retries have explicit upper bounds
- [ ] No ignored return values. Every non-void result used or explicitly discarded with justification
- [ ] Preconditions asserted before irreversible operations and at trust boundaries
- [ ] Single export per file. One module, one responsibility, one export
- [ ] No module-level side effects: no I/O, network calls, global state mutations, or event listener registration at import time
- [ ] Command-query separation: functions either change state or return data, never both
- [ ] No raw SQL when the project has an ORM or query builder
- [ ] Parse, don't validate: validation returns a typed value, not a boolean
- [ ] No deep nesting: max 3 levels of indentation. Guard clauses and early returns to flatten

### 10. Naming and Readability

- [ ] Variable names describe what the value IS, not how it was computed
- [ ] Function names describe what the function DOES, using verbs
- [ ] Boolean variables use `is`, `has`, `can`, `should` prefixes
- [ ] No single-letter variables outside of trivial loops (`i`, `j`)
- [ ] No misleading names (e.g. `getUser` that also modifies state)
- [ ] Abbreviations avoided unless universally understood (`url`, `id`, `html` are fine; `usr`, `mgr`, `cfg` are not)
- [ ] File and module names consistent with the project's naming convention
- [ ] Code readable without comments. Comments explain WHY, not WHAT
- [ ] File ordering: main export first, then subcomponents, helpers, static content, types
- [ ] File naming follows domain convention: `name-of-content.type.ext`

### 11. Architecture and Patterns

- [ ] Change follows existing patterns in the codebase, except when existing patterns violate rules in `~/.claude/`. Rules always win over existing code style
- [ ] If a new pattern is introduced, it is justified and better than the existing one
- [ ] Coupling between modules appropriate. Changed code testable in isolation
- [ ] No circular dependencies introduced
- [ ] Configuration externalized. No environment-specific behavior hardcoded
- [ ] Decision reversibility considered: one-way doors (public API shape, database schema, data deletion) get extra scrutiny
- [ ] Fan-out low: module depends only on abstractions it needs
- [ ] Law of Demeter: only call methods on direct dependencies, parameters, and objects you create
- [ ] Use-case functions for multi-step business flows: zero conditionals, zero loops, flat sequential calls to domain services
- [ ] No environment conditionals: never branch business logic on `NODE_ENV` or equivalent
- [ ] Domain exception boundary: domain logic throws domain-specific errors, not framework HTTP exceptions. Mapping happens at the boundary

### 12. Backward Compatibility

- [ ] Change does not break existing callers, consumers, or clients. Function signatures, API responses, event payloads, and configuration formats checked
- [ ] If a public function signature changed, all callers in the codebase are updated
- [ ] If an API response shape changed, frontend consumers and external integrations are updated
- [ ] If a database column was renamed, removed, or retyped, the migration follows the safe pattern (add new, dual-write, migrate readers, drop old)
- [ ] If a message or event schema changed, existing consumers can still process old messages in flight
- [ ] If environment variables were renamed or removed, deployment configs, CI pipelines, and documentation are updated
- [ ] If a feature was removed, a deprecation path or migration guide exists

### 13. Dependencies

- [ ] New dependency justified. Could this be done with existing code or stdlib?
- [ ] Dependency actively maintained with recent commits and no known vulnerabilities
- [ ] Version pinned exactly in lockfile
- [ ] License compatible with the project
- [ ] Bundle size impact acceptable for frontend dependencies
- [ ] Dev dependencies correctly separated from production dependencies

### 14. Documentation

- [ ] README updated if setup, env vars, API, or architecture changed
- [ ] New env vars documented in `.env.example`
- [ ] Breaking changes documented with migration steps
- [ ] PR description explains what changed and why (review mode only)
- [ ] PR scope focused: one logical change, not a grab-bag of unrelated fixes (review mode only)

### 15. Cross-File Consistency

Review the diff as a whole after per-file checks. Look for contradictions between files.

- [ ] Design assumptions consistent across files. No file assumes graceful degradation while another enforces a hard dependency on the same resource
- [ ] Module-level side effects traced. New imports do not trigger connections, env validation throws, or scheduled tasks that change startup behavior
- [ ] Configuration complete. Every new env var, dependency, or infrastructure requirement is also added to `.env.example`, Docker configs, CI pipelines, and documentation
- [ ] Contracts aligned across boundaries. Frontend sends data in the exact format backend expects: header names, field names, parameter types, and positions all match
- [ ] Error types flow correctly. Errors thrown in one module are caught and handled correctly by callers
- [ ] Symmetry maintained. Resources acquired are released on all paths. Features enabled can be disabled

### 16. Cascading Fix Analysis

For every issue found in all other categories, evaluate the downstream effects of the fix.

- [ ] Would the fix introduce a new dependency, env var, or startup requirement?
- [ ] Would the fix change a function signature or public interface, breaking callers not in this diff?
- [ ] Would the fix require coordinated changes in files not touched by this PR?
- [ ] Would the fix change error behavior that other code relies on?
- [ ] Would the fix need new tests that are not mentioned?

When any answer is yes, the fix must include a note about downstream effects. The goal: every issue and its cascading consequences are addressed in a single iteration.

### 17. Zero Warnings

Treat every warning as an error. A warning ignored today becomes a broken build after the next dependency update. Zero tolerance, no exceptions.

#### Strictness configuration

- [ ] Compiler, type checker, and linter configured at maximum strictness. See `rules/code-style.md` "Maximum Compiler and Checker Strictness" for per-language requirements
- [ ] No strictness flags intentionally disabled without a documented reason in the config file
- [ ] When joining an existing project with missing strictness flags, add them and fix resulting errors in the same PR

#### Tooling warnings

- [ ] Compiler and type checker output has zero warnings. `tsc`, `-Wall`, `mypy --strict`, `clippy`: all clean
- [ ] Linter output has zero warnings, not just zero errors. Warning-severity findings are findings
- [ ] Formatter reports zero changes needed. Run in check mode before committing
- [ ] Build output has zero warnings. Unused imports, implicit-any, deprecated API calls: all resolved
- [ ] Test runner output has zero warnings. Deprecation notices, experimental API notices, plugin compatibility warnings: all resolved
- [ ] CI pipeline output has zero non-fatal annotations. Deprecation notices, version warnings, action warnings: all resolved

#### Runtime warnings

- [ ] No `console.warn` calls from code under test or during development. If the code warns, either fix the cause or remove the warning if it is no longer relevant
- [ ] No framework or driver warnings during startup, test execution, or normal operation
- [ ] No deprecation warnings from dependencies used in the code being changed

#### Suppression policy

- [ ] No warning suppression without a documented justification. `// eslint-disable`, `@ts-ignore`, `#pragma warning disable`, `@SuppressWarnings`, `# type: ignore`: each requires an inline comment explaining why the warning is a false positive
- [ ] Suppression comments never say just "it works" or "not needed". State the specific reason
- [ ] When modifying a file with existing suppressions, verify each suppression is still necessary. Remove stale ones

#### Warning baseline

- [ ] Warning count in changed files is equal to or lower than before the change. Never increase it
- [ ] When modifying a file that already has warnings, fix the warnings in the code you touch. Existing warnings are not permission to add more
- [ ] After all tools run, scan the full output for: `warn`, `warning`, `deprecated`, `deprecation`, `notice`, `WARN`, `WARNING`. If any appear, the task is not done

---

## Architecture and Infrastructure

Only apply categories relevant to the system type. A CLI tool does not need caching. A single-service app does not need saga.

### 18. Idempotency and Deduplication

- [ ] Every write operation (API, event handler, database) safe to execute twice with the same input?
- [ ] Guard mechanism identified per layer?
  - API: `Idempotency-Key` header with cached response
  - Event handler: dedup by message ID before processing
  - Database: upsert, `ON CONFLICT DO NOTHING`, or conditional expression
  - State machine: check current state before transitioning
- [ ] Natural deduplication key identified (request ID, event ID, user+action+date)?
- [ ] Dedup state stored durably (database, not in-memory)? Survives restarts?
- [ ] Dedup window (TTL) exceeds maximum retry/redelivery time?
- [ ] POST endpoints that create resources support `Idempotency-Key` header?

Reference: `rules/code-style.md` (Data Safety), `standards/resilience.md` (Idempotency, Deduplication)

### 19. Atomicity and Transactions

- [ ] Related writes wrapped in a single transaction?
- [ ] Conditional writes used to prevent lost updates (optimistic locking, version field)?
- [ ] Transaction scope kept short (validation and I/O before, not inside)?
- [ ] Explicit rollback on failure, not relying on implicit cleanup?
- [ ] NoSQL: `TransactWriteItems` or conditional expressions for multi-item atomicity?
- [ ] Conditional write failures classified: conflict (retry with fresh read) vs duplicate (skip)?
- [ ] Multi-step workflows handle partial failure with rollback or compensating actions?

Reference: `standards/database.md` (Transactions and Atomic Writes, Conditional Writes)

### 20. Error Classification and Retry

- [ ] Every `catch` classifies the error as transient or permanent?
- [ ] Transient errors (timeout, 429, 503, connection reset): logged as warn, retried with exponential backoff + jitter?
- [ ] Permanent errors (400, 404, validation, auth): logged as error, failed immediately, never retried?
- [ ] Ambiguous errors (500, unknown): retried up to 3 times, then treated as permanent?
- [ ] Classification propagated upstream so callers can make informed decisions?
- [ ] No bare catch blocks that log and rethrow without classification?
- [ ] Retry parameters explicit: base delay (100-500ms), multiplier (2x), jitter (0-50%), max retries (3 sync, 5 async)?
- [ ] Max delay cap set (never exceeds 30s between retries)?
- [ ] Total retry time fits within the caller's timeout budget?
- [ ] Caught errors include context: what operation failed, with what input, and why?
- [ ] Async errors handled? No unhandled promise rejections? No missing `await`?
- [ ] Error propagation consistent? Not mixing thrown exceptions with returned error codes in the same layer?
- [ ] HTTP status codes correct for each error type (400, 401, 403, 404, 409, 422, 500)?
- [ ] Partial failure: if step 3 of 5 fails, are steps 1-2 rolled back or is the state consistent?
- [ ] Batch processing: individual item failures reported without aborting the batch?
- [ ] Errors in cleanup code (finally blocks, defer) handled separately?

Reference: `rules/code-style.md` (Error Classification), `standards/resilience.md` (Error Classification, Retry Strategy)

### 21. Caching

- [ ] Reads from slow or expensive sources: caching considered?
- [ ] Cache strategy chosen explicitly (cache-aside, write-through, read-through)?
- [ ] Invalidation strategy explicit (TTL, event-driven, explicit on write)?
- [ ] TTL set with jitter to prevent synchronized expiration?
- [ ] Popular keys protected from thundering herd (lock-based recomputation, stale-while-revalidate)?
- [ ] Cache warming strategy for cold starts after deploy?
- [ ] Max memory limit set? Eviction policy chosen (LRU, LFU)?
- [ ] Hit rate monitored?

Reference: `standards/caching.md`

### 22. Consistency Model

- [ ] Consistency model chosen explicitly (strong, eventual, read-your-writes, causal)?
- [ ] Weakest tolerable model used (strong only for finance, auth, inventory)?
- [ ] Read-your-writes implemented where users mutate and immediately read their own data?
- [ ] Implementation of read-your-writes explicit (read from primary after write, version token, or optimistic UI update)?
- [ ] Eventual consistency communicated to consumers (not silently stale)?

Reference: `standards/distributed-systems.md` (Consistency Models)

### 23. Back Pressure and Load Management

- [ ] Every in-memory queue and channel has a max size?
- [ ] Behavior defined when queue is full (reject, drop oldest, block)?
- [ ] Load shedding strategy: requests classified by priority (critical > important > deferrable)?
- [ ] Overload responses use 503 with `Retry-After` header?
- [ ] Rate limiting on public endpoints?
- [ ] Plan for 10x traffic explicitly considered?

Reference: `standards/resilience.md` (Back Pressure)

### 24. Bulkhead Isolation

- [ ] Separate connection pool per external dependency?
- [ ] One slow dependency cannot exhaust the shared pool?
- [ ] Critical and non-critical workloads isolated (separate processes, queues, or deployments)?
- [ ] Per-tenant or per-priority queue isolation where applicable?

Reference: `standards/resilience.md` (Bulkhead)

### 25. Concurrency Control

- [ ] Fan-out operations bounded by semaphore or worker pool?
- [ ] No unbounded `Promise.all` over large arrays?
- [ ] Worker pool size configured, not left at defaults?
- [ ] Timeout set on each unit of work (stuck worker does not permanently reduce capacity)?
- [ ] Queue depth, active workers, and rejection count instrumented?
- [ ] Shared mutable state protected by locks, mutexes, or atomic operations?
- [ ] No TOCTOU (time-of-check-to-time-of-use) bugs? Check-then-act patterns use database constraints or CAS?
- [ ] Async operations awaited where the result matters? No fire-and-forget without error handler?
- [ ] No deadlock potential from acquiring multiple locks?

Reference: `standards/resilience.md` (Concurrency Control)

### 26. Saga and Cross-Service Coordination

- [ ] Multi-service transactions use saga pattern (not distributed transactions/2PC)?
- [ ] Each saga step has an explicit compensating action?
- [ ] Compensating actions are idempotent?
- [ ] Saga state persisted durably (can resume after crash)?
- [ ] Saga timeout defined, compensation triggered if exceeded?
- [ ] Database write + event publish uses outbox pattern (single transaction)?
- [ ] Outbox delivery mechanism chosen (polling, CDC, log tailing)?
- [ ] No dual writes (DB + message broker in separate operations)?

Reference: `standards/distributed-systems.md` (Saga Pattern, Outbox Pattern)

### 27. Event Ordering and Delivery Guarantees

- [ ] Delivery guarantee chosen explicitly (at-most-once, at-least-once, exactly-once)?
- [ ] At-least-once delivery paired with idempotent consumers?
- [ ] Ordering scope chosen (per-entity, global, causal, none)?
- [ ] Partition key set for per-entity ordering (Kafka partition key, SQS FIFO group ID)?
- [ ] Out-of-order events handled (version check, last-write-wins, or buffer and reorder)?
- [ ] Consumers handle message redelivery without duplicate side effects?

Reference: `standards/distributed-systems.md` (Event Ordering and Delivery Guarantees)

### 28. Distributed Locking

- [ ] Coordination required between instances (scheduled jobs, leader election, exclusive access)?
- [ ] Lock implementation chosen (Redis, database advisory, ZooKeeper/etcd)?
- [ ] Lease expiry set so crashed holders release locks?
- [ ] Fencing tokens used to prevent stale writes after lease expiry?
- [ ] Every write includes the fencing token, storage rejects stale tokens?

Reference: `standards/distributed-systems.md` (Distributed Locking)

### 29. Schema Evolution

- [ ] Events and messages include a `schemaVersion` field?
- [ ] All schema changes backward and forward compatible?
- [ ] No removed or renamed fields without migration plan?
- [ ] No changed field types (new field with new type added instead)?
- [ ] Consumers handle at least current and previous schema version?

Reference: `standards/distributed-systems.md` (Schema Evolution)

### 30. Immutability

- [ ] Functions do not mutate their arguments? Copy-in, copy-out?
- [ ] `const` by default, `let` only when reassignment needed?
- [ ] State transitions produce new state, never mutate previous?
- [ ] Derived values computed from state via selectors, not cached as mutable fields?
- [ ] Audit-sensitive data append-only (versioned rows, not in-place updates)?
- [ ] Events stored as immutable facts in event-driven systems?

Reference: `rules/code-style.md` (Immutability)

### 31. Query Optimization

- [ ] No `SELECT *`, only needed columns fetched?
- [ ] No N+1 queries? Eager loading or joins used?
- [ ] Pagination on all list endpoints (default + max page size)?
- [ ] Indexes on WHERE, JOIN, ORDER BY columns?
- [ ] Filtering at database level, not in application code?
- [ ] Aggregation at database level, not fetching rows and aggregating in app?
- [ ] Time-range queries: timezone-aware? Not assuming UTC alignment for daily buckets?
- [ ] Time-range boundaries computed at query time from user's local timezone?
- [ ] NoSQL key design distributes writes evenly? No hot partitions?
- [ ] Connection pooling configured? No connection leak (opening without closing)?
- [ ] Query plans reviewed with EXPLAIN for new or changed queries? No full table scans on large tables?
- [ ] Write amplification understood? Indexes add write cost proportional to their count.
- [ ] Read replicas used for read-heavy queries that tolerate slight staleness?

Reference: `standards/database.md` (Query Optimization, Time-Range Queries)

### 32. Observability

- [ ] Structured JSON logging with required fields (level, message, timestamp, requestId, service)?
- [ ] Log levels correct (error for failures, warn for handled-but-unexpected, info for business events)?
- [ ] Correlation ID (requestId) propagated across all service calls via `X-Request-Id` header?
- [ ] No sensitive data logged (passwords, tokens, PII)? Redaction patterns applied?
- [ ] No logging inside tight loops?
- [ ] Health check endpoints present: liveness (process alive, no deps) + readiness (all deps reachable with latency)?
- [ ] Metrics for request rate, error rate, latency (p50/p95/p99), saturation?
- [ ] Metric labels low-cardinality (never user IDs, request IDs, timestamps)?
- [ ] Distributed tracing: W3C Trace Context headers, spans for inbound/outbound calls, DB queries, and queue ops?
- [ ] Alerts on symptoms, not causes? Tied to SLO violations? Runbook links on every alert?
- [ ] SLIs defined (availability, latency, error rate)? SLOs set based on measured data, not guesses?
- [ ] Error budget tracked? Reliability prioritized over features when budget is spent?
- [ ] Every alert has a runbook with: what it means, how to diagnose, how to mitigate, and who to escalate to?
- [ ] Distributed debugging path documented? Given a requestId, can an engineer trace the full request across services?
- [ ] On-call handoff includes: known fragile areas, recent incidents, pending deployments, and alert context?
- [ ] Business metrics instrumented? Conversion rates, feature adoption, funnel drop-off tracked alongside technical metrics.
- [ ] A/B test observability? Experiment assignment logged, metrics split by variant, statistical significance tracked.
- [ ] Incident severity classification defined? SEV1-SEV4 with response time expectations and escalation paths.
- [ ] Communication protocol during incidents? Status page updates, stakeholder notifications, war room coordination.
- [ ] Blameless postmortem conducted within 48h of SEV1/SEV2? Timeline, root cause, contributing factors, action items with owners.

Reference: `standards/observability.md`

### 33. Security and Access Control

#### Injection and input handling
- [ ] SQL injection: all queries parameterized or using ORM? No string concatenation in queries?
- [ ] XSS: all user input escaped before rendering? Framework auto-escaping not bypassed?
- [ ] Command injection: no user input passed to `exec`, `spawn`, or shell commands without sanitization?
- [ ] Path traversal: no user input used in file paths without validation? `../` sequences blocked?
- [ ] SSRF: no user-controlled URLs fetched without allowlist validation?
- [ ] Header injection: no user input in HTTP headers without sanitization?
- [ ] Template injection: no user input in template strings evaluated server-side?
- [ ] Input sanitization at all system boundaries (user input, external APIs)?

#### Authentication and authorization
- [ ] Passwords hashed with bcrypt or argon2, never MD5 or SHA?
- [ ] Rate limiting on auth endpoints (login, register, password reset)?
- [ ] Token expiration configured? Refresh token rotation?
- [ ] Tokens validated for expiration, signature, and audience?
- [ ] Session management: tokens rotated after auth state changes? Proper invalidation on logout?
- [ ] CSRF protection on state-changing endpoints (SameSite cookies, CSRF tokens, or origin validation)?
- [ ] Access control: default deny? Permissions explicitly granted, never explicitly denied?
- [ ] Per-resource authorization checked, not just per-role (IDOR prevention)?
- [ ] Authorization logic centralized, not scattered across controllers?

#### Data protection
- [ ] Encryption in transit: TLS 1.2+ on all external connections?
- [ ] Encryption at rest for sensitive data (platform-managed keys)?
- [ ] Constant-time comparison for secrets (no timing side-channel)?
- [ ] No secrets, API keys, tokens, or credentials in code, comments, or config files?
- [ ] No sensitive data in logs, error messages, or stack traces?
- [ ] No PII leaked through API responses beyond what the caller needs?
- [ ] Error messages generic in production, no internal paths or query details?
- [ ] CORS configured correctly? Not using `*` with credentials?

#### Cryptography
- [ ] No custom crypto implementations? Using well-known libraries?
- [ ] No weak algorithms (MD5, SHA1 for security purposes, DES)?
- [ ] Random values generated with cryptographically secure source?

#### Data privacy
- [ ] Data minimization: only collecting what's needed?
- [ ] Retention policy defined per data type? Automated deletion after retention period?
- [ ] Right to erasure: path to delete all of a user's personal data on request?
- [ ] Audit logging for sensitive actions (login, password change, role change, record deletion, PII access)?

#### Supply chain
- [ ] Dependencies locked with exact versions? Lockfile committed? Audit in CI?

#### Infrastructure security
- [ ] IAM follows least privilege? Service accounts scoped per service, no shared credentials across services.
- [ ] Secrets managed through a vault (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager)? Rotated automatically on schedule.
- [ ] Network segmentation enforced? Services only reachable from expected sources. No flat network where everything can talk to everything.
- [ ] Zero trust applied? No implicit trust based on network location. Every request authenticated and authorized regardless of origin.
- [ ] Certificate management automated? TLS certificates rotated before expiry. No manual cert renewal in production.

Reference: `rules/security.md`, `standards/infrastructure.md` (Networking and Service Discovery)

### 34. API Contract Design

- [ ] Resources are plural nouns, actions use HTTP methods, max 2 levels of nesting?
- [ ] Status codes correct: 201 for creates with Location header, 204 for no-content, 409 for conflicts, 422 for validation?
- [ ] Error response shape consistent: machine-readable code, human message, requestId, optional field details?
- [ ] No stack traces or internal paths exposed in production error responses?
- [ ] Request/response shapes consistent with existing endpoints?
- [ ] Pagination on all list endpoints? Strategy chosen (cursor-based default, offset-based for random access)?
- [ ] Default and maximum page size set?
- [ ] Filtering and sorting on list endpoints?
- [ ] Versioning strategy: URL path (`/v1/...`), at most two major versions active?
- [ ] Deprecation lifecycle: `Deprecation` and `Sunset` headers, monitoring, documented migration path?
- [ ] Rate limiting headers on every response (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`)?
- [ ] `Retry-After` header on 429 responses?
- [ ] POST endpoints that create resources support `Idempotency-Key` header?
- [ ] Bulk operations return per-item results with individual status codes?
- [ ] ISO 8601 dates, UTC timestamps, `Content-Type` header set?
- [ ] Collections wrapped in `data` field? Consistent response envelope?
- [ ] Response includes only necessary data? No over-fetching?

Reference: `standards/api-design.md`

### 35. External Dependency Resilience

- [ ] Explicit timeout on every external call (connect + read for HTTP, statement for DB, visibility for queues)?
- [ ] No reliance on framework defaults (often 30-60s, too generous)?
- [ ] Circuit breakers for services that may be degraded (closed, open, half-open)?
- [ ] Circuit breaker trips on sustained failure, not a single error?
- [ ] Connection pooling: separate pool per external dependency?
- [ ] Pool size based on expected concurrency, not defaults or guesses?
- [ ] Idle timeout configured to reclaim unused connections?
- [ ] For serverless: connection proxy (RDS Proxy, PgBouncer) to prevent exhaustion from cold starts?
- [ ] Graceful degradation: fallback behavior defined when a dependency is unavailable?
- [ ] Health check readiness endpoint reflects dependency status?

Reference: `standards/resilience.md` (Circuit Breakers, Timeouts), `standards/database.md` (Connection Management)

### 36. Async Processing Resilience

- [ ] Dead letter queue configured on every queue and event source mapping?
- [ ] `maxReceiveCount` set based on retry policy (typically 3-5)?
- [ ] Partial batch failures reported: return individual failure IDs so successful messages are not redelivered?
- [ ] DLQ depth monitored with alerts? Messages in DLQ mean data is not being processed.
- [ ] Reprocessing path built: DLQ messages can be replayed after root cause fix?
- [ ] Consumer processes each item independently? One failure does not abort the batch?
- [ ] Per-item success/failure tracked and reported?
- [ ] State consistent after partial failure (compensating actions or rollback)?
- [ ] Background jobs have execution timeout with cleanup?
- [ ] Message visibility timeout aligned with expected processing time?

Reference: `standards/resilience.md` (Dead Letter Queues, Partial Failure, Timeouts)

### 37. Deployment Readiness

- [ ] Backward compatibility: old and new versions coexist during rollout (rolling update, blue/green, canary)?
- [ ] Database migrations run before deployment? Old code works with new schema?
- [ ] Safe migration patterns used: nullable columns first, no renames or type changes in one step?
- [ ] Liveness probe: returns 200 if process is running, no dependency checks?
- [ ] Readiness probe: returns 200 only when all critical dependencies are reachable?
- [ ] Graceful shutdown: stop accepting new requests, finish in-flight within timeout, then exit?
- [ ] Feature flags for user-facing behavior changes that need gradual rollout?
- [ ] Rollback plan: can revert deployment without data loss or manual intervention?
- [ ] No hardcoded config: all environment-specific values from env vars or config service?
- [ ] Canary promotion criteria defined? Metrics checked before widening rollout (error rate, latency, business KPIs)?
- [ ] Rollback tested, not just planned? The rollback path has been exercised at least once?
- [ ] Deployment frequency sustainable? Can the team ship this change independently without coordinating with other teams?

Reference: `standards/distributed-systems.md` (Zero-Downtime Deployments), `standards/database.md` (Safe Migrations)

### 38. Graceful Degradation

- [ ] Each external dependency has a defined fallback UX when unavailable?
- [ ] Core user flows work without non-critical dependencies (recommendations, analytics, notifications)?
- [ ] Fallback responses identified per dependency: cached data, default values, or reduced functionality?
- [ ] Degraded state communicated to the user? No silent failures that look like empty data.
- [ ] Degraded paths tested? Chaos testing or dependency kill switches exercised?
- [ ] Blast radius analyzed? A single dependency failure does not cascade to unrelated features.
- [ ] Timeout-based degradation: if a dependency is slow but not down, the system switches to fallback before the user notices?
- [ ] RTO (Recovery Time Objective) and RPO (Recovery Point Objective) defined per service? How fast must it recover, and how much data loss is tolerable?
- [ ] Backup strategy validated? Backups tested with actual restore, not just "backups run nightly."
- [ ] Cross-region failover plan exists for critical services? Traffic can shift to a secondary region if the primary is unavailable.
- [ ] Chaos engineering practiced? Failure injection tested in non-production or controlled production environments.
- [ ] Game days scheduled? Team exercises simulating outages to validate runbooks, monitoring, and incident response.

Reference: `standards/resilience.md` (Circuit Breakers, Timeouts)

### 39. Data Modeling

- [ ] Aggregate boundaries defined? Each aggregate is the unit of consistency and transactional integrity.
- [ ] Entity vs value object distinction clear? Entities have identity, value objects are compared by attributes.
- [ ] Normalization level chosen deliberately? 3NF for write-heavy, denormalized for read-heavy, with documented trade-offs.
- [ ] Relationship ownership explicit? One side owns the FK, the other side queries through it.
- [ ] Domain events identified? State transitions that other parts of the system need to react to.
- [ ] Natural keys vs surrogate keys: chosen per table with justification? Natural keys where stable, surrogate where not.
- [ ] Schema designed for access patterns, not just data structure? Indexes, partitions, and key design serve the queries.
- [ ] Enums and status fields use explicit string values, not magic integers? Readable in raw queries and logs.
- [ ] Bounded contexts identified? Each context has its own model of shared concepts, no single "God object" used everywhere.
- [ ] Anti-corruption layer at context boundaries? Translation between external models and internal domain models happens at the edge, not throughout the codebase.
- [ ] Ubiquitous language consistent? The same term means the same thing in code, database, API, and conversation. No synonyms for the same concept.

Reference: `standards/database.md` (Access Pattern Design, Schema Rules)

### 40. Capacity Planning

- [ ] Storage growth rate estimated? Data volume projected for 1 year, 3 years.
- [ ] Read/write ratio understood? Informs caching strategy, replica topology, and index design.
- [ ] Bottleneck identified? CPU-bound, memory-bound, I/O-bound, or network-bound under expected load.
- [ ] Horizontal scaling path exists? No single-instance assumptions baked into the design (local file storage, in-memory state, sticky sessions).
- [ ] Hot spots identified? Uneven distribution of load across partitions, shards, or instances.
- [ ] Data retention and archival strategy defined? Old data moved to cold storage or deleted on schedule.
- [ ] Connection and thread pool limits sized for expected concurrency, with headroom for spikes?
- [ ] Cost of the current design at 10x scale estimated? No surprise bills from unbounded resources.
- [ ] Auto-scaling validated under load? Scale-up and scale-down behavior tested, not just configured.
- [ ] Storage IOPS and throughput sized for peak? Not just capacity but performance under concurrent access.

Reference: `standards/database.md` (Connection Management, NoSQL Key Design), `standards/resilience.md` (Back Pressure), `standards/infrastructure.md` (Cloud Architecture)

### 41. Testability

- [ ] Dependencies injected, not instantiated inline? Every external dependency replaceable in tests without mocking frameworks.
- [ ] Pure functions extracted from I/O? Business logic testable without databases, networks, or file systems.
- [ ] Functional core, imperative shell? Core domain logic is pure and tested exhaustively, I/O is thin and tested via integration.
- [ ] Contract tests at service boundaries? Consumer-driven contracts verify that provider changes do not break consumers.
- [ ] Load test coverage for critical paths? Performance regressions caught before production, not after.
- [ ] Feature flags testable? Both sides of every flag exercised in tests.
- [ ] Test data builders or factories used? No brittle test setup with hardcoded object literals duplicated across tests.
- [ ] Time and randomness injectable? Tests do not depend on the current clock or random output.

Reference: `rules/testing.md` (Philosophy, Mock Policy), `rules/code-style.md` (Immutability)

### 42. Cost Awareness

- [ ] Query cost understood? Expensive queries identified and optimized or cached.
- [ ] Compute right-sized? Instance types, Lambda memory, and container resources match actual usage, not guesses.
- [ ] Storage tiers used appropriately? Hot data on fast storage, cold data on archive (S3 IA, Glacier, equivalent).
- [ ] Batch vs real-time chosen deliberately? Real-time processing only when the use case requires it.
- [ ] Egress costs considered? Cross-region and cross-AZ traffic minimized. CDN for static assets.
- [ ] Cache ROI positive? The cost of the cache infrastructure is less than the cost of hitting the origin.
- [ ] Unused resources cleaned up? No orphaned volumes, snapshots, or idle load balancers accumulating charges.
- [ ] Cost alerts configured? Budget thresholds with notifications before spending spirals.

Reference: `standards/caching.md` (When to Cache), `standards/database.md` (Query Optimization)

### 43. Multi-Tenancy

- [ ] Tenant data isolation enforced? Row-level (shared DB, tenant_id column), schema-level (tenant per schema), or instance-level (tenant per DB)?
- [ ] Every query scoped to the tenant? No accidental cross-tenant data leakage through missing WHERE clauses or cache key collisions?
- [ ] Noisy neighbor prevention? One tenant's heavy usage cannot degrade performance for others (per-tenant rate limits, queue isolation, connection limits).
- [ ] Per-tenant resource limits defined? Storage quotas, API rate limits, concurrent connection caps.
- [ ] Tenant context propagated across service boundaries? Every downstream call carries the tenant identifier.
- [ ] Tenant-aware caching? Cache keys include tenant ID. Invalidation scoped to the affected tenant.
- [ ] Tenant onboarding and offboarding automated? Provisioning and deprovisioning do not require manual steps or code changes.
- [ ] Tenant-specific configuration supported? Feature flags, plan limits, and custom settings per tenant without code deploys.

Reference: `rules/security.md` (Access Control), `standards/database.md` (Access Pattern Design)

### 44. Migration Strategy

- [ ] Migration approach chosen? Strangler fig (gradual replacement), parallel run (old + new simultaneously), or big bang (with rollback plan)?
- [ ] Feature parity validated? Automated comparison between old and new system outputs for the same inputs.
- [ ] Data migration plan defined? Backfill strategy, data transformation, validation checksums, rollback path for data.
- [ ] Dark launching used for high-risk migrations? New path runs in shadow mode, results compared but not served to users.
- [ ] Cutover criteria explicit? What metrics must hold for the migration to be considered complete?
- [ ] Rollback during migration possible? Can traffic be routed back to the old system at any point without data loss?
- [ ] Migration progress observable? Percentage of traffic or data migrated, error rates on old vs new, latency comparison.
- [ ] Old system decommission planned? Timeline for shutting down the previous implementation after migration completes.

Reference: `standards/distributed-systems.md` (Zero-Downtime Deployments), `standards/database.md` (Safe Migrations)

### 45. Infrastructure as Code

- [ ] All infrastructure defined in code (Terraform, Pulumi, CloudFormation)? No manually provisioned resources?
- [ ] Provisioning idempotent? Running the same code twice produces the same infrastructure with no orphaned resources.
- [ ] State managed remotely with locking? No local state files for shared infrastructure.
- [ ] State isolation: separate state per environment and per service? One blast radius per state file.
- [ ] Immutable infrastructure: dependencies baked into images, instances replaced not patched?
- [ ] Environment parity: dev, staging, production from the same templates with environment-specific variables?
- [ ] Drift detection automated? Scheduled `plan` runs alert on manual changes to infrastructure.
- [ ] Modules versioned and pinned? No unintentional module updates during apply.
- [ ] Secrets not stored in IaC state or templates? Sensitive values from a vault or secrets manager.
- [ ] Plan reviewed before apply? No blind applies in production.

Reference: `standards/infrastructure.md` (Infrastructure as Code)

### 46. Networking and Service Discovery

- [ ] Service discovery mechanism chosen? DNS-based, client-side, server-side LB, or service mesh?
- [ ] Load balancing algorithm appropriate? Round-robin for stateless, least-connections for variable duration, consistent hashing for stateful.
- [ ] DNS TTL configured for failover requirements? Low enough for fast failover, not so low it hammers DNS.
- [ ] mTLS between services? Service-to-service traffic encrypted, not relying on network trust.
- [ ] Network policies / security groups follow least privilege? Default deny, explicit allow only for required traffic.
- [ ] VPC / subnet design isolates tiers? Public, private, and data subnets. Databases never in public subnets.
- [ ] CDN configured for static assets and cacheable responses? Cache invalidation strategy defined.
- [ ] Ingress and egress controls defined? Known set of external endpoints. Unexpected egress investigated.

Reference: `standards/infrastructure.md` (Networking and Service Discovery)

### 47. Container Orchestration

- [ ] Resource requests and limits set on every container? Requests based on actual usage, limits with headroom for peaks.
- [ ] Horizontal pod autoscaling configured? Metric (CPU, custom) chosen, min/max replicas set, cooldown tuned.
- [ ] Pod disruption budgets defined? Minimum available during voluntary disruptions (node drain, upgrade).
- [ ] Anti-affinity spreads replicas across nodes and availability zones? No single-point-of-failure co-location.
- [ ] Rolling update strategy tuned? maxUnavailable and maxSurge set for zero-downtime deploys.
- [ ] Health probes configured correctly? Liveness (restart on hang), readiness (remove from LB on unready), startup (slow-starting apps).
- [ ] Graceful shutdown: preStop hook, terminationGracePeriodSeconds long enough to drain connections?
- [ ] Resource quotas and limit ranges per namespace? One team cannot consume the entire cluster.
- [ ] Sidecar pattern used for cross-cutting concerns (mesh proxy, log collector, secrets injector)?

Reference: `standards/infrastructure.md` (Container Orchestration)

### 48. CI/CD Pipeline Design

- [ ] Pipeline stages ordered by feedback speed? Lint and static analysis first, deploy last.
- [ ] Artifact built once and promoted through environments? No rebuilding for production.
- [ ] Artifacts tagged with git SHA? No `latest` as a deployment strategy.
- [ ] Artifacts signed and verified before deployment?
- [ ] Environment promotion strategy explicit? Push-based, GitOps, or manual promotion?
- [ ] Progressive delivery configured? Canary with auto-promote/rollback based on metrics, feature flags, or dark launching.
- [ ] Pipeline security: secrets injected at runtime, not in repo or build logs? Least-privilege credentials per stage.
- [ ] DORA metrics tracked? Deployment frequency, lead time, change failure rate, MTTR.
- [ ] Rollback automated or one-click? Not a multi-step manual process.

Reference: `standards/infrastructure.md` (CI/CD Pipeline Design)

### 49. Cloud Architecture

- [ ] Multi-region strategy chosen? Single, active-passive, or active-active? Trade-offs (cost, complexity, RTO) understood.
- [ ] Blast radius contained at infrastructure level? Account/project isolation per environment and workload class.
- [ ] AZ-independent? Losing one availability zone does not degrade service. Resources spread across 2+ AZs.
- [ ] Cell-based architecture where appropriate? Independent cells by geography, customer segment, or shard.
- [ ] Service quotas known and monitored? Hitting a cloud provider limit in production is an outage.
- [ ] Auto-scaling validated? Scale-up and scale-down tested under load. Predictive scaling for known patterns.
- [ ] DDoS mitigation: WAF, rate limiting at edge, cloud-native shield on public load balancers?
- [ ] Data residency requirements met? Storage and processing regions comply with regulations (GDPR, LGPD).
- [ ] Cost allocation tags on all resources? Environment, team, service, cost center.
- [ ] Reserved capacity or savings plans for stable workloads? Spot/preemptible for fault-tolerant jobs.

Reference: `standards/infrastructure.md` (Cloud Architecture)
