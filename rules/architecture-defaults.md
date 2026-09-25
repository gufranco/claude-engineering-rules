# Architecture Defaults

DRY, SOLID, KISS, YAGNI, immutability, idempotency, deduplication, and race freedom apply to every file. Before any non-trivial code, run the six-question gate.

## Architecture Gate

| Question | If yes |
|----------|--------|
| Business rules, state transitions, or invariants beyond CRUD? | DDD: entities, value objects, aggregates, ubiquitous language |
| Two or more infrastructure dependencies? | Hexagonal: ports in domain, adapters outside, domain imports nothing from infra |
| Mutates shared state, persists, or has side effects? | Idempotency, dedup key, atomic transaction |
| Crosses a trust boundary: HTTP, queue, external API, LLM output? | Validate with Zod, parse-don't-validate, brand the result |
| Multiple states or transitions? | Type-state or explicit state machine, no boolean blindness |
| Can two actors run it at once? | Name every actor, trace one interleaving, pick a correctness-ladder rung first |

Two or more yes answers means non-trivial: run `/plan` first. The concurrency question defaults to yes for anything with more than one entry point, user-triggerable twice, or network-retryable.

## Hard Rules

- No `let` never reassigned; no `.push()`, `.sort()`, `.splice()`, `.reverse()` on the receiver; no mutating Date setters
- No `any`; use `unknown` and narrow
- No raw SQL in application code; no ORM imports in controllers, routers, or handlers
- No `console.*` in production paths; no empty `catch {}`; every `void promise` ends with `.catch(...)` logging
- No `Record<string, unknown>` for ORM where/data/orderBy
- No `NODE_ENV` conditionals in business logic; no module-level side effects
- No `Object.assign(target, ...)` with a non-fresh target
- No check-then-act unless one transaction, an upsert or conditional write, or a unique constraint covers it
- No read-modify-write outside a transaction or row lock
- No network or filesystem I/O inside a transaction
- No in-memory dedup store: a `Set`, `Map`, or array is empty after restart
- No unbounded `Promise.all` over caller input; no shared mutable accumulation across concurrent promises

## Domain, Idempotency, Concurrency

- Domain layer imports no adapters, framework decorators, or I/O libraries; one repository per aggregate root, IDs across aggregates, eventual consistency between them
- Application services are flat sequential calls: no conditionals, loops, or try/catch
- Every write carries an idempotency key in a durable store with a TTL; same key and payload replays, same key with a different payload returns 409; a DB unique constraint matches the check
- Consumers extract a dedup key with an explicit window; first write wins; log dedup hits at info
- Correctness ladder, in order: constraint, conditional write or upsert, row lock, version column, distributed lock with fencing token, in-process mutex only for a single process
- The guard must span the read and the write it decides; name what the race loser receives; lock TTL and transaction timeout exceed p99, caller timeout exceeds both

## Skip List

Throwaway scripts under 50 lines, pure pipelines, build tools, and single-DB CRUD with no rules skip DDD and Hexagonal, never DRY, SOLID, YAGNI, or immutability. When in doubt, apply.

Full rule, examples, and rationale: [`standards/architecture-defaults.md`](../standards/architecture-defaults.md). Read it before designing a write path, an aggregate, or a port and adapter layer, and for the post-implementation verification gate.
