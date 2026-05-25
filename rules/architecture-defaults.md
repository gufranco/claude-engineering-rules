# Architecture Defaults

Always-on architectural baseline. This rule defines what applies to every line of generated code, and what gates must run before non-trivial work. Depth lives in on-demand standards; this file is the entry point that guarantees they get loaded.

## Universal Principles (Apply to Every File)

| Principle | Rule | Source |
|-----------|------|--------|
| DRY | No duplicated logic across files. Extract shared logic into a single source of truth. Three similar lines is fine; the fourth is a function. | [`code-style.md`](code-style.md) Fundamentals |
| SOLID | Single responsibility per module. Open for extension, closed for modification. Liskov substitution. Interface segregation. Dependency inversion via constructor params or interfaces. | [`code-style.md`](code-style.md) Fundamentals |
| YAGNI | No speculative features, no abstractions for hypothetical futures, no hooks for unwritten callers. Implement only what the current task requires. | [`code-style.md`](code-style.md) Fundamentals + [`surgical-edits.md`](surgical-edits.md) |
| KISS | Simplest design that solves the problem. Reach for the next layer of abstraction only when the current one breaks down. | [`code-style.md`](code-style.md) Fundamentals |
| Immutability | Every value is readonly by default. `const` not `let`. `[...arr, x]` not `.push()`. `.toSorted()` not `.sort()`. No parameter mutation. No mutating Date setters. | [`lang/typescript-immutability.md`](lang/typescript-immutability.md) + mutation-method-blocker hook |
| Idempotency | Every mutating operation must be safe to run twice with the same input. Use unique constraints, dedup keys, or guard checks. | [`code-style.md`](code-style.md) Data Safety |
| Deduplication | Networks retry, queues redeliver, users double-click. Every endpoint accepting a write must extract a dedup key and persist it in a durable store. | [`code-style.md`](code-style.md) Data Safety + [`../standards/resilience.md`](../standards/resilience.md) |

## Architecture Gate (Pre-Implementation)

Before writing any non-trivial code, answer all five questions. Failure to ask any of them is a gate violation.

| Question | If yes, load | Action |
|----------|-------------|--------|
| Does this involve business rules, state transitions, or invariants beyond CRUD? | [`../standards/ddd-tactical-patterns.md`](../standards/ddd-tactical-patterns.md) | Model with entities, value objects, aggregates. Ubiquitous language in code |
| Are there two or more infrastructure dependencies, like DB plus queue, DB plus external API? | [`../standards/hexagonal-architecture.md`](../standards/hexagonal-architecture.md) | Define ports in domain, adapters in outer layer. Domain imports nothing from infra |
| Is the operation mutating shared state, persisting data, or producing side effects? | [`code-style.md`](code-style.md) Data Safety + [`../standards/resilience.md`](../standards/resilience.md) | Apply idempotency + dedup key + atomic transaction |
| Does the operation cross trust boundaries: HTTP, queue, external API, LLM output? | [`code-style.md`](code-style.md) Validation + LLM Trust Boundary | Validate at boundary with Zod, parse-don't-validate, brand the result type |
| Are there multiple states or transitions for a domain object? | [`../standards/state-machines.md`](../standards/state-machines.md) | Type-state pattern or explicit state machine. No boolean blindness |

If two or more apply, this is non-trivial work. Run `/plan` before implementing.

## Hard Rules (No Exceptions)

These violate immediately on sight, regardless of project conventions:

- No `let` that is never reassigned. Use `const` with ternary or lookup map
- No `.push()`, `.sort()`, `.splice()`, `.reverse()` on the receiver. Use spread or ES2023 copy methods
- No mutating Date setters. Use Temporal or `date-fns`
- No `any` type. Use `unknown` and narrow
- No raw SQL in application code. ORM only. Raw SQL is for migrations
- No direct ORM imports in controllers, routers, or API handlers. Service layer is mandatory
- No `console.log`, `console.error`, `console.warn` in production paths. Use the project logger
- No empty `catch {}`. Every catch logs with context, then rethrows or returns typed error
- No fire-and-forget without `.catch()`. Every `void promise` ends with `.catch(error => logger.error(...))`
- No `Record<string, unknown>` for ORM where/data/orderBy. Use generated input types
- No environment conditionals in business logic. Externalize via config, not via `if NODE_ENV ===`
- No module-level side effects. Side effects belong inside explicitly called functions
- No `Object.assign(target, ...)` with a non-fresh target. Use spread on a fresh object

## Domain Layer Contract

When the architecture gate fires DDD or Hexagonal:

- Domain layer imports zero adapter code, zero framework decorators, zero I/O libraries
- Ports are interfaces in the domain layer. Adapters implement them in the outer layer
- Aggregates enforce their own invariants. An aggregate in an invalid state is a bug
- Cross-aggregate consistency is eventual, never transactional. Use domain events or sagas
- One repository per aggregate root. References between aggregates use IDs, not object references
- Repositories return fully reconstituted aggregates, never database rows or partial objects
- Application services orchestrate use cases as flat, sequential calls. No conditionals, no loops, no try/catch
- Validation of business rules lives in domain objects. Adapters only validate structure: types, required fields

Full guidance: [`../standards/ddd-tactical-patterns.md`](../standards/ddd-tactical-patterns.md) and [`../standards/hexagonal-architecture.md`](../standards/hexagonal-architecture.md).

## Idempotency Specifics

For every write endpoint, message consumer, or scheduled job:

| Element | Rule |
|---------|------|
| Idempotency key | Required on every write. Header `Idempotency-Key`, message attribute, or job ID |
| Storage | Durable store with TTL matching expected retry window. Redis with TTL or DB table |
| Scope | Per-tenant, per-user, or global based on the resource. Document the scope |
| Retry semantics | Same key with same payload returns the stored result. Same key with different payload returns 409 |
| Constraint match | Database unique constraint matches the validator's idempotency check. No daydream consistency |

For multi-step flows: each step is independently idempotent. Failure in step 3 of 5 must not corrupt steps 1 to 2 nor block re-running.

Full guidance: [`../standards/resilience.md`](../standards/resilience.md).

## Deduplication Specifics

For every queue consumer, event handler, or webhook receiver:

| Element | Rule |
|---------|------|
| Dedup key | Extract from message body, headers, or compute deterministically from payload |
| Window | Time-bounded. State the window explicitly: 5 minutes, 1 hour, 24 hours |
| Storage | Same durable store as idempotency. Same TTL discipline |
| First-write-wins | Subsequent writes with the same key are no-ops, never overwrites |
| Audit | Log dedup hits at info level. A flood of dedup hits indicates a producer bug |

Full guidance: [`../standards/resilience.md`](../standards/resilience.md) and [`../standards/message-queues.md`](../standards/message-queues.md).

## Verification Gate (Post-Implementation)

After implementation, verify each:

1. Every public function: pure where possible, side effects pushed to the outermost layer
2. Every mutation: documented dedup key if persisted, idempotency guard if retried
3. Every aggregate boundary: transactional consistency only within, eventual across
4. Every port: domain types only, no SQL types, no HTTP types, no library-specific types
5. Every use case: flat orchestration, no conditionals, no loops, no exception handling
6. Every domain event: past tense, immutable, contains all data consumers need
7. Every entity: identity established at creation and never mutated
8. Every value object: smart constructor that validates invariants

A `git diff` that violates any of these is not done.

## Skip List

These principles are overhead, not value, when:

| Scenario | What to skip |
|----------|-------------|
| Throwaway script under 50 lines | DDD, Hexagonal. Keep DRY, SOLID, YAGNI, immutability |
| Pure data pipeline with no business logic | DDD aggregates. Keep hexagonal if multiple data sources |
| Static site generator, build tool, CLI utility | DDD, Hexagonal. Keep DRY, SOLID, YAGNI, immutability |
| One-database CRUD with no domain rules | Hexagonal. DDD only if invariants exist |

When in doubt, apply. Removing later is cheaper than retrofitting.

## Cross-References

- [`code-style.md`](code-style.md): SOLID/DRY/YAGNI/KISS fundamentals, immutability baseline, error classification, data safety, validation
- [`lang/typescript-immutability.md`](lang/typescript-immutability.md): TS-specific mutation surface, hook coverage, ES2024+ replacements
- [`pre-flight.md`](pre-flight.md): Pre-implementation duplicate check, architecture fit, interface verification
- [`design-philosophy.md`](design-philosophy.md): Ousterhout complexity heuristics, deep modules, design it twice
- [`../standards/ddd-tactical-patterns.md`](../standards/ddd-tactical-patterns.md): Entities, value objects, aggregates, repositories, domain events
- [`../standards/hexagonal-architecture.md`](../standards/hexagonal-architecture.md): Ports, adapters, dependency direction, layer testing
- [`../standards/resilience.md`](../standards/resilience.md): Idempotency, deduplication, retries, circuit breakers
- [`../standards/railway-oriented-programming.md`](../standards/railway-oriented-programming.md): Result types, error composition
- [`../standards/state-machines.md`](../standards/state-machines.md): Type-state pattern, transitions, guards
