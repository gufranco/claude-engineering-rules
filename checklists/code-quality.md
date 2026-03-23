# Code Quality Checklist

Shared by the completion gates (self-review during implementation), `/review` (code review), and `/assessment` (architecture audit). One source of truth for what to check at the code level.

For architecture, resilience, and infrastructure categories, see `engineering.md` in this directory.

## How to use

**During implementation (completion gates):** after writing code and before declaring done, read the full diff and run through every applicable category. Fix issues found. Re-read the diff. Repeat until clean.

**During review:** apply every applicable category to the diff. Issues found become review comments with explanation, impact, and a code example showing the fix.

Not every category applies to every change. Skip categories that are clearly irrelevant to the scope of the diff.

---

## 1. Correctness

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

## 2. Security

- [ ] Full OWASP top 10 lens applied: injection, broken auth, sensitive data exposure, XXE, broken access control, misconfig, XSS, insecure deserialization, known vulnerable components, insufficient logging
- [ ] No secrets, tokens, or credentials in the diff
- [ ] Auth and authorization enforced on every new route. No IDOR
- [ ] Input validated and sanitized at every system boundary
- [ ] No sensitive data in responses, logs, or error messages
- [ ] No open redirects from user-controlled URLs
- [ ] No SSRF: server-side fetches validate destination against allowlist
- [ ] CSRF protection on state-changing endpoints

## 3. Error Handling

- [ ] Every error path covered with context, not silently swallowed
- [ ] Error messages helpful for debugging without leaking internals
- [ ] Error propagation strategy consistent across modules
- [ ] No thrown exception that could crash a request handler unhandled
- [ ] Errors classified: transient (retry with backoff), permanent (fail immediately), or ambiguous (retry with limit, then fail)
- [ ] Error handler self-protecting: logging failure inside handler falls back to stdout

## 4. Concurrency

- [ ] No shared mutable state without synchronization
- [ ] No missing `await` on async calls
- [ ] No fire-and-forget promises that should be awaited
- [ ] No TOCTOU bugs: check-then-act sequences protected by database constraints, locks, or conditional writes
- [ ] No unhandled promise rejections

## 5. Data Integrity

- [ ] **Idempotent:** every write operation safe to execute twice with the same input. If not naturally idempotent, a guard prevents duplicate effects
- [ ] **Deduplicated:** natural dedup key identified with durable check-before-process. In-memory-only dedup is not acceptable
- [ ] **Atomic:** related writes wrapped in a transaction or conditional expression. No partial writes left to corrupt state
- [ ] Validation present at every system boundary: not just syntactic but semantic (positive amounts, valid date ranges, enum membership)
- [ ] Database constraints match application-level validation: unique constraints, foreign keys, check constraints
- [ ] Async processors have DLQ, partial batch failure reporting, dedup by message ID, and monitoring

## 6. Algorithmic Performance

- [ ] No O(n^2) or worse hidden in nested loops, repeated `.find()`, `.filter()` inside `.map()`
- [ ] Data structures appropriate: Set for lookups instead of array `.includes()` in a loop
- [ ] Sorting only when necessary, using the right algorithm for the data size
- [ ] No unbounded data loaded into memory. Streams used for large files
- [ ] No allocations inside hot loops (object creation, string concatenation)
- [ ] File handles, connections, and streams closed after use
- [ ] No synchronous I/O in async code paths
- [ ] No N+1 query patterns. Batch or join instead
- [ ] No blocking I/O in request handlers

## 7. Frontend Performance

Skip if no frontend code changed.

- [ ] No unnecessary re-renders. Dependencies in `useEffect`/`useMemo`/`useCallback` correct
- [ ] Large lists virtualized
- [ ] Images and assets optimized
- [ ] No blocking operations on the main thread
- [ ] Bundle size impact considered. No unnecessarily large dependencies added

## 8. Testing

### Coverage

- [ ] Every new function/method has tests
- [ ] Every code branch tested: success, each error case, each edge case
- [ ] Coverage on changed code at 80% or above
- [ ] Integration tests for database operations, not mocked unit tests

### Test quality

- [ ] Tests follow AAA pattern (Arrange, Act, Assert) with those exact comments
- [ ] Test names describe behavior, not implementation ("should reject expired token" not "test validateToken")
- [ ] Assertions specific enough to catch regressions. Not just `toBeTruthy()` when a specific value matters
- [ ] No test-only backdoors in production code
- [ ] Tests independent: no shared mutable state between tests, no ordering dependency
- [ ] Tests verify the behavior they claim to test, not just that no error was thrown
- [ ] Negative tests present: invalid input, unauthorized access, missing resources
- [ ] Boundary value tests: empty arrays, zero, max int, empty string, null
- [ ] Test data uses fake data generator with deterministic seed. No hardcoded static values
- [ ] Contract tests at service boundaries: consumer expectations verified against provider responses
- [ ] Property-based tests for complex logic: invariants hold across randomized inputs, not just hand-picked examples

### Mock policy (STRICT, blocking issue)

- [ ] Database, Redis, queues, and caches use real connections via docker-compose, with `beforeAll()` seed and `afterAll()` cleanup
- [ ] Own services and modules tested with real implementations, not mocks
- [ ] Only external third-party APIs, time, and randomness are mocked
- [ ] Any mock of internal infrastructure is a **blocking issue**

## 9. Code Quality and Design

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

## 10. Naming and Readability

- [ ] Variable names describe what the value IS, not how it was computed
- [ ] Function names describe what the function DOES, using verbs
- [ ] Boolean variables use `is`, `has`, `can`, `should` prefixes
- [ ] No single-letter variables outside of trivial loops (`i`, `j`)
- [ ] No misleading names (e.g. `getUser` that also modifies state)
- [ ] Abbreviations avoided unless universally understood (`url`, `id`, `html` are fine; `usr`, `mgr`, `cfg` are not)
- [ ] File and module names consistent with the project's naming convention
- [ ] Code readable without comments. Comments explain WHY, not WHAT

## 11. Architecture and Patterns

- [ ] Change follows existing patterns in the codebase, except when existing patterns violate rules in `~/.claude/`. Rules always win over existing code style
- [ ] If a new pattern is introduced, it is justified and better than the existing one
- [ ] Coupling between modules appropriate. Changed code testable in isolation
- [ ] No circular dependencies introduced
- [ ] Configuration externalized. No environment-specific behavior hardcoded
- [ ] Decision reversibility considered: one-way doors (public API shape, database schema, data deletion) get extra scrutiny
- [ ] Fan-out low: module depends only on abstractions it needs

## 12. Backward Compatibility

- [ ] Change does not break existing callers, consumers, or clients. Function signatures, API responses, event payloads, and configuration formats checked
- [ ] If a public function signature changed, all callers in the codebase are updated
- [ ] If an API response shape changed, frontend consumers and external integrations are updated
- [ ] If a database column was renamed, removed, or retyped, the migration follows the safe pattern (add new, dual-write, migrate readers, drop old)
- [ ] If a message or event schema changed, existing consumers can still process old messages in flight
- [ ] If environment variables were renamed or removed, deployment configs, CI pipelines, and documentation are updated
- [ ] If a feature was removed, a deprecation path or migration guide exists

## 13. Dependencies

- [ ] New dependency justified. Could this be done with existing code or stdlib?
- [ ] Dependency actively maintained with recent commits and no known vulnerabilities
- [ ] Version pinned exactly in lockfile
- [ ] License compatible with the project
- [ ] Bundle size impact acceptable for frontend dependencies
- [ ] Dev dependencies correctly separated from production dependencies

## 14. Documentation

- [ ] README updated if setup, env vars, API, or architecture changed
- [ ] New env vars documented in `.env.example`
- [ ] Breaking changes documented with migration steps
- [ ] PR description explains what changed and why (review mode only)
- [ ] PR scope focused: one logical change, not a grab-bag of unrelated fixes (review mode only)

## 15. Cross-File Consistency

Review the diff as a whole after per-file checks. Look for contradictions between files.

- [ ] Design assumptions consistent across files. No file assumes graceful degradation while another enforces a hard dependency on the same resource
- [ ] Module-level side effects traced. New imports do not trigger connections, env validation throws, or scheduled tasks that change startup behavior
- [ ] Configuration complete. Every new env var, dependency, or infrastructure requirement is also added to `.env.example`, Docker configs, CI pipelines, and documentation
- [ ] Contracts aligned across boundaries. Frontend sends data in the exact format backend expects: header names, field names, parameter types, and positions all match
- [ ] Error types flow correctly. Errors thrown in one module are caught and handled correctly by callers
- [ ] Symmetry maintained. Resources acquired are released on all paths. Features enabled can be disabled

## 16. Cascading Fix Analysis

For every issue found in categories 1-15 and 17, evaluate the downstream effects of the fix.

- [ ] Would the fix introduce a new dependency, env var, or startup requirement?
- [ ] Would the fix change a function signature or public interface, breaking callers not in this diff?
- [ ] Would the fix require coordinated changes in files not touched by this PR?
- [ ] Would the fix change error behavior that other code relies on?
- [ ] Would the fix need new tests that are not mentioned?

When any answer is yes, the fix must include a note about downstream effects. The goal: every issue and its cascading consequences are addressed in a single iteration.

## 17. Zero Warnings

Treat every warning as an error. A warning ignored today becomes a broken build after the next dependency update. Zero tolerance, no exceptions.

### Tooling warnings

- [ ] Compiler and type checker output has zero warnings. `tsc`, `-Wall`, `mypy --strict`, `clippy`: all clean
- [ ] Linter output has zero warnings, not just zero errors. Warning-severity findings are findings
- [ ] Formatter reports zero changes needed. Run in check mode before committing
- [ ] Build output has zero warnings. Unused imports, implicit-any, deprecated API calls: all resolved
- [ ] Test runner output has zero warnings. Deprecation notices, experimental API notices, plugin compatibility warnings: all resolved
- [ ] CI pipeline output has zero non-fatal annotations. Deprecation notices, version warnings, action warnings: all resolved

### Runtime warnings

- [ ] No `console.warn` calls from code under test or during development. If the code warns, either fix the cause or remove the warning if it is no longer relevant
- [ ] No framework or driver warnings during startup, test execution, or normal operation
- [ ] No deprecation warnings from dependencies used in the code being changed

### Suppression policy

- [ ] No warning suppression without a documented justification. `// eslint-disable`, `@ts-ignore`, `#pragma warning disable`, `@SuppressWarnings`, `# type: ignore`: each requires an inline comment explaining why the warning is a false positive
- [ ] Suppression comments never say just "it works" or "not needed". State the specific reason
- [ ] When modifying a file with existing suppressions, verify each suppression is still necessary. Remove stale ones

### Warning baseline

- [ ] Warning count in changed files is equal to or lower than before the change. Never increase it
- [ ] When modifying a file that already has warnings, fix the warnings in the code you touch. Existing warnings are not permission to add more
- [ ] After all tools run, scan the full output for: `warn`, `warning`, `deprecated`, `deprecation`, `notice`, `WARN`, `WARNING`. If any appear, the task is not done
