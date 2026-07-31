# Concurrency and Race Conditions

How to write code that stays correct when two actors execute it at the same instant. Loaded on demand. Triggers in [`../rules/index.yml`](../rules/index.yml).

## Scope

This standard owns the single-process and single-database race. It covers what goes wrong between two statements, how to close the window, and how to prove the window is closed.

| Concern | Owner |
|---------|-------|
| Race taxonomy, correctness ladder, isolation anomalies, per-language models, testing races | This file |
| Idempotency keys, request fingerprints, replay semantics | [`idempotency.md`](idempotency.md) |
| Retries, circuit breakers, backpressure, bulkheads, DLQs | [`resilience.md`](resilience.md) |
| Saga, outbox, distributed locking with fencing tokens, consistency models | [`distributed-systems.md`](distributed-systems.md) |
| Isolation level configuration, transaction syntax, connection pooling | [`database.md`](database.md) and [`postgresql.md`](postgresql.md) |
| Atomic Redis command composition | [`redis.md`](redis.md) |
| In-process value mutation | [`immutability.md`](immutability.md) |

## The One-Sentence Test

Between any two statements in your function, another copy of that function may run to completion.

Read the handler with that sentence in mind. Every place the answer changes the outcome is a race. This is true on a single-threaded runtime, because `await` yields; true on one replica, because the user double-clicks; and true on one process, because the retry arrives before the first attempt finishes.

## Actor Inventory

Name the actors before naming the fix. A write path is reachable from more of them than the code suggests.

| Actor | Why it appears |
|-------|----------------|
| Two user requests | Double-click, double-tap, two browser tabs, an impatient refresh |
| A retry | The client timed out, the proxy retried, the SDK has automatic retries on 5xx |
| A second replica | Horizontal scaling means your in-process mutex protects one third of the traffic |
| A queue redelivery | At-least-once delivery is the default everywhere. The first delivery may still be running |
| A webhook re-send | Providers re-send on any non-2xx and on timeouts, often with a new request ID |
| A cron tick | The previous run has not finished. Two runs now overlap |
| A backfill or admin script | Runs against production data with no knowledge of the online path |
| A cascading write | A trigger, an ORM hook, or an event handler that writes to the same row |

Two deliveries from one source count as two actors. Actors that write different rows still collide when they read the same aggregate to decide.

## Race Taxonomy

| Race | Shape | Canonical symptom | Fix rung |
|------|-------|-------------------|----------|
| Check-then-act, TOCTOU | `read; decide; write` where the read decides | Two rows where one was intended | Unique constraint, or upsert |
| Lost update | `read; compute; write` where the write overwrites | A balance that drops one of two credits | Row lock, or version column |
| Write skew | Two transactions read an overlapping set, each writes a disjoint row, and together they break an invariant | Two on-call doctors both go off shift | Serializable isolation, or lock the predicate row |
| Phantom | A row appearing between two reads of the same predicate | Aggregate totals that disagree inside one transaction | Repeatable read or serializable, or a range lock |
| Double submit | The same user intent arrives twice | Two orders, two charges | Idempotency key, see [`idempotency.md`](idempotency.md) |
| Duplicate delivery | The same message processed twice | Two emails, double credit | Durable dedup key inside the business transaction |
| Interleaved multi-step mutation | `delete; insert` or `void; create` where another actor runs between the steps | Rows that exist in neither state | One transaction across all steps, or an entity lock |
| Non-atomic compound operation | Two commands that must be one | A counter with no TTL, a key that never expires | Lua script or MULTI/EXEC, see [`redis.md`](redis.md) |
| Cache stampede | A hot key expires and every request recomputes | A database that falls over on cache expiry | Single-flight, plus TTL jitter |
| Stale writer | A slow actor finishes after its lock expired and writes anyway | The winner's write silently reverted | Fencing token, see [`distributed-systems.md`](distributed-systems.md) |
| Async reentrancy | A second call enters a function while the first is awaiting | A module-level cache populated twice, an in-flight flag that never resets | Single-flight promise map |
| Read-modify-write on a collection | Load a list, append, save the whole list | One item silently dropped | Append at the storage layer, or a lock |
| Filesystem race | `exists; write`, or a partially written file read by another process | Truncated config, half-written export | `O_EXCL` create, or write-temp-then-rename |
| Init race | Two callers initialize the same singleton | Two connection pools, two schedulers | Lazy init behind a single-flight promise |

## Correctness Ladder

Pick the highest rung that fits the problem. Every rung below the top trades a guarantee for reach. State the reason for not using the rung above.

| Rung | Mechanism | Guarantees | Cost | Fails when |
|------|-----------|-----------|------|-----------|
| 1 | Database constraint, such as `UNIQUE` or `CHECK` or an exclusion constraint | The bad state cannot exist, whoever writes it | An error path to handle | The invariant spans rows the constraint cannot see |
| 2 | Conditional write, such as upsert, `ON CONFLICT`, an `updateMany` guarded by the expected state, or a DynamoDB condition expression | The engine decides atomically | Handle the zero-rows-affected result | The decision needs data the engine cannot express |
| 3 | Row lock held across read and write, `SELECT ... FOR UPDATE` | Serializes actors on that row | Lock wait, deadlock risk if ordering is inconsistent | The row does not exist yet, so there is nothing to lock |
| 4 | Optimistic version column | Detects the conflict, never blocks | The loser must retry, so the operation must be retryable | High contention turns into a retry storm |
| 5 | Advisory lock, such as PostgreSQL `pg_advisory_xact_lock` on a hashed key | Serializes on an arbitrary key, including keys with no row | Held for the transaction, invisible to other databases | Multiple databases, or a key space that collides after hashing |
| 6 | Distributed lock with a fencing token | Serializes across processes | Needs a token check at the write, plus TTL tuning | The token is not checked, which makes the lock advisory-only |
| 7 | Entity-keyed serialization, such as a queue partitioned by entity ID | One writer per entity by construction | Latency, and ordering becomes your problem | Cross-entity invariants |
| 8 | In-process mutex or single-flight | Cheap, no infrastructure | None beyond memory | A second replica exists. Correct only while exactly one process runs |

Rung 8 is the default reflex and is almost always wrong in production. A mutex in a service running two pods protects nothing.

## Isolation Levels and Anomalies

Under a given isolation level, an anomaly is either prevented by the engine or left to you.

| Anomaly | Read committed | Repeatable read, PostgreSQL snapshot | Serializable |
|---------|----------------|--------------------------------------|--------------|
| Dirty read | Prevented | Prevented | Prevented |
| Non-repeatable read | Possible | Prevented | Prevented |
| Phantom | Possible | Prevented in PostgreSQL, possible in the ANSI definition | Prevented |
| Lost update | Possible | Detected, the transaction aborts with a serialization failure | Prevented |
| Write skew | Possible | Possible | Prevented |

Engine notes that change the answer:

- PostgreSQL `REPEATABLE READ` is snapshot isolation. It stops phantoms but permits write skew, and it raises a serialization failure rather than blocking. Every transaction at this level or higher needs a retry loop around the serialization failure code `40001`.
- MySQL InnoDB `REPEATABLE READ` is the default and uses next-key locking, so it behaves differently from PostgreSQL under the same name. Reads inside a transaction see the snapshot, while `SELECT ... FOR UPDATE` sees the latest committed row.
- Raising the isolation level does not remove the need for a retry loop. It converts silent corruption into a loud, retryable error, which is the trade you want.
- Isolation protects transactions against each other. It does nothing about two actors in application code that never opened a transaction.

## Patterns

### Unique constraint plus conflict handling, rung 1

The constraint is the only mechanism that holds no matter who writes: your handler, a migration, a backfill, another service, or a person in a SQL console.

```typescript
export async function claimHandle(userId: UserId, handle: string): Promise<Result<Claim, ClaimError>> {
  try {
    const claim = await db.handleClaim.create({ data: { userId, handle } });
    return ok(claim);
  } catch (error: unknown) {
    if (isUniqueViolation(error, 'HandleClaim_handle_key')) {
      return err({ kind: 'HandleTaken', handle });
    }
    throw error;
  }
}
```

The catch is not error handling bolted on. It is the branch the race actually takes, so it needs a test.

```prisma
model HandleClaim {
  id     String @id @default(uuid())
  userId String
  handle String

  @@unique([handle], map: "HandleClaim_handle_key")
}
```

An application-level `findFirst` before the `create` adds nothing the constraint does not already give, and it reads as protection while providing none.

### Conditional write, rung 2

```typescript
const updated = await db.invoice.updateMany({
  where: { id: invoiceId, status: InvoiceStatus.Pending },
  data: { status: InvoiceStatus.Paid, paidAt: now },
});

if (updated.count === 0) {
  return err({ kind: 'AlreadySettled', invoiceId });
}
```

An update whose `where` clause carries the expected state is a compare-and-set. The zero-count branch is the loser of the race, and it must be handled rather than ignored.

### Row lock, rung 3

```sql
BEGIN;
SELECT balance FROM account WHERE id = $1 FOR UPDATE;
UPDATE account SET balance = $2 WHERE id = $1;
COMMIT;
```

The lock is taken by the read and released at commit, so no other transaction can read that row to decide until this one finishes. Expressed through a query builder that supports it natively:

```typescript
await db.transaction(async (tx) => {
  const [account] = await tx.select().from(accounts).where(eq(accounts.id, accountId)).for('update');
  const next = applyDebit(account, amount);
  await tx.update(accounts).set({ balance: next.balance }).where(eq(accounts.id, accountId));
});
```

Prisma has no typed `FOR UPDATE`. Use rung 2 or rung 5 there rather than reaching for raw SQL in application code, per [`../rules/lang/orm-migrations.md`](../rules/lang/orm-migrations.md).

Lock ordering matters. Two transactions that lock rows in opposite order deadlock. Always acquire in a deterministic order, such as ascending primary key.

### Optimistic version, rung 4

```typescript
const updated = await db.document.updateMany({
  where: { id, version: expectedVersion },
  data: { ...changes, version: expectedVersion + 1 },
});

if (updated.count === 0) {
  return err({ kind: 'ConcurrentModification', id, expectedVersion });
}
```

Prefer this when conflicts are rare and the caller can redo the work. Prefer a row lock when conflicts are common, because a retry storm costs more than a short wait.

### Advisory lock, rung 5

```sql
SELECT pg_advisory_xact_lock(hashtext($1));
```

Use when the thing you must serialize on has no row to lock, such as a nightly job name, a tenant-wide rebuild, or a key that will exist only after the write. The transaction-scoped variant releases on commit or rollback, so no leak is possible. The session-scoped variant leaks on a crashed connection and needs an explicit unlock.

### Single-flight, rungs 7 and 8

Collapses N concurrent callers for the same key into one execution, and gives all of them the same result. This is the fix for cache stampede, for duplicated lazy initialization, and for async reentrancy.

```typescript
const inFlight = new Map<string, Promise<Config>>();

export function loadConfig(key: string): Promise<Config> {
  const existing = inFlight.get(key);
  if (existing) {
    return existing;
  }

  const pending = fetchConfig(key).finally(() => {
    inFlight.delete(key);
  });

  inFlight.set(key, pending);
  return pending;
}
```

That `Map` is process-local coordination state, not a deduplication store. Deduplication of business effects must be durable, per [`idempotency.md`](idempotency.md). Losing this map on restart costs one extra fetch; losing a dedup store costs a duplicate charge.

### Bounded fan-out

```typescript
import pLimit from 'p-limit';

const limit = pLimit(10);
const results = await Promise.allSettled(
  records.map((record) => limit(() => processRecord(record))),
);
```

Three rules for fan-out. Bound the concurrency whenever the input length comes from a caller or a database. Use `allSettled` and classify afterwards, so one rejection does not discard work already done. Never accumulate into a shared array or counter from inside the concurrent callbacks; return values and combine after the fan-out settles.

## Per-Language Concurrency Models

### JavaScript and TypeScript

The single thread protects you from torn reads, and from nothing else. The unit of atomicity is the synchronous run between two `await` points.

```typescript
// Bad: two requests both pass the check before either writes
const existing = await db.seat.findFirst({ where: { showId, row, number } });
if (!existing) {
  await db.seat.create({ data: { showId, row, number, userId } });
}
```

The `await` on the read yields. A second request enters, sees no row, and both create. This is the single most common generated-code race, and rung 1 or rung 2 removes it.

Other JavaScript-specific shapes:

- A module-level cache or in-flight flag mutated across `await` points is shared state between concurrent requests within one process.
- `worker_threads` with a `SharedArrayBuffer` is real parallelism. Coordinate with `Atomics`, and note that `Atomics.wait` blocks, so it is forbidden on the main thread.
- Node cluster mode, PM2, and any replica count above one all mean process-local coordination is not coordination.

### Python

- `asyncio` yields at every `await`, giving the same interleaving as JavaScript. `asyncio.Lock` serializes coroutines within one event loop and nothing beyond it.
- The GIL makes individual bytecodes atomic and compound operations not. `counter += 1` across threads still loses updates. Use `threading.Lock`, or `itertools.count`, or a queue.
- Free-threaded builds, PEP 703, remove the GIL protection that some code accidentally relies on. Never rely on GIL atomicity for correctness.
- `multiprocessing` gives separate memory, so shared state must be explicit through a `Manager`, a queue, or the database.

### Go

- Run tests and CI with `-race`. The detector finds real bugs and finds them cheaply.
- A mutex protects state; a channel transfers ownership. Pick by which one the code is doing.
- `errgroup.WithContext` plus `SetLimit` is the bounded fan-out with cancellation.
- A captured loop variable is no longer a footgun as of Go 1.22, where each iteration gets its own variable. Older codebases still carry the bug.

### JVM

- `synchronized` and `java.util.concurrent.locks` for mutual exclusion, `ConcurrentHashMap.compute` for atomic read-modify-write on a key.
- `AtomicLong` and `LongAdder` for counters, with `LongAdder` preferred under contention.
- Virtual threads change the cost of blocking, never the need for coordination. Pinning inside `synchronized` blocks is a performance trap, not a correctness one.

### Rust

- The type system prevents data races: `Send` and `Sync` are the proof, and a shared mutable value requires `Mutex`, `RwLock`, or an atomic.
- Logical races survive the borrow checker. A check-then-act against a database is still a race in Rust.

## Timeouts, Retries, and Locks

These three interact, and the interaction is where correct-looking systems fail.

| Relationship | Rule |
|--------------|------|
| Lock TTL against operation duration | TTL must exceed the p99 of the protected operation, with margin. Too short and the lock expires mid-operation, creating a stale writer |
| Caller timeout against lock TTL | The caller must wait longer than the lock TTL, or it retries into a lock still held by its own first attempt |
| Retry against idempotency | A retry without an idempotency key is a duplicate request by definition. See [`idempotency.md`](idempotency.md) |
| Retry against lock acquisition | Retrying lock acquisition needs jitter, otherwise the losers synchronize and collide again |
| Expired lock against the write | An expired lock does not stop the write that follows. Only a fencing token checked at write time stops it |

## Filesystem Races

- Create exclusively with `O_EXCL`, or the `wx` flag in Node, when the file's existence is the lock.
- Write to a temporary file in the same directory and `rename` it into place. `rename` is atomic within a filesystem, so readers see the old file or the new one and never a partial one.
- `fsync` the file before rename when durability matters, and `fsync` the directory afterwards.
- Never use `exists` followed by `write`. Another process writes in the gap.
- A lock file without a TTL or an owner PID becomes a permanent outage after one crash.

## Caching Races

- Stampede on expiry: single-flight per key, plus jittered TTLs so keys do not expire together.
- Write-through invalidation ordering: write the database first, then invalidate. Invalidate-then-write leaves the cache holding a value that a concurrent read repopulated from the pre-write state.
- Negative caching needs the same discipline, or a miss storm replaces the hit storm.
- A cache that hides a race does not remove it. Correctness lives in the database.

## Testing Races

A race that is not tested will regress. These tests are deterministic despite testing nondeterminism, because they assert on the invariant rather than on the timing.

**N-parallel duplicate calls, the standard shape for any write path:**

```typescript
it('creates exactly one order when the same request arrives ten times at once', async () => {
  const payload = buildOrderPayload();

  const results = await Promise.allSettled(
    Array.from({ length: 10 }, () => createOrder(payload)),
  );

  const orders = await db.order.findMany({ where: { idempotencyKey: payload.idempotencyKey } });
  expect(orders).toHaveLength(1);
  expect(results.filter((result) => result.status === 'fulfilled')).toHaveLength(10);
});
```

**Interleaving with a barrier**, when the window is narrow and N-parallel misses it. Hold one actor between its read and its write, run the other to completion, then release.

```typescript
it('rejects the second transfer when both read the same balance', async () => {
  const account = await seedAccount({ balance: 100 });
  const barrier = createBarrier();

  const first = transferWithHook(account.id, 100, { afterRead: () => barrier.wait() });
  const second = await transfer(account.id, 100);
  barrier.release();
  const firstResult = await first;

  const settled = [firstResult, second].filter((result) => result.ok);
  expect(settled).toHaveLength(1);
  expect((await getAccount(account.id)).balance).toBe(0);
});
```

Other required checks:

- Restart the process between the two calls in the deduplication test. An in-memory dedup store passes without this and fails in production.
- Assert the loser's response, not only the winner's. A race test that ignores what the second caller received tolerates a 500.
- Run the suite against the real database. Isolation-level behavior is the thing under test, and no mock reproduces it.
- Go: `go test -race`. C and C++: ThreadSanitizer. Java: the `jcstress` harness for memory-model claims.
- Seed the fake data generator so the parallel calls carry identical payloads, per [`../rules/testing.md`](../rules/testing.md).

## Observability

A race in production announces itself before it corrupts data, if the counters exist.

| Signal | What it means |
|--------|---------------|
| Unique-violation rate on a constraint | The race is happening and the constraint is holding. A spike means a client is retrying wrong |
| Serialization failure rate, `40001` | Contention at the isolation level. Watch alongside the retry counter |
| Zero-rows-affected on conditional updates | The loser count. A rise means contention, or a bug in the expected state |
| Lock wait time p99 | Approaching the lock TTL means stale writers are next |
| Deduplication hit rate | Steady is healthy, since duplicates are normal. A jump means a producer is misbehaving |
| Idempotent replay rate | The same reading, from the API side |

Log the losing branch at info with the key and the actor. A race you cannot see is a race you cannot fix.

## Anti-Patterns

| Anti-pattern | Why it fails |
|--------------|--------------|
| A read that decides, followed by a create | The window between them is the bug. Nothing about the code shows it |
| `if (!exists) { create }` with no constraint behind it | The check reads as protection and provides none |
| In-process mutex in a service with more than one replica | Protects a fraction of traffic proportional to one over the replica count |
| Isolation level raised without a retry loop | Turns silent corruption into an unhandled `40001` in production |
| Lock acquired, work done, lock released, no token checked | An expired lock allows the stale writer to overwrite the winner |
| `Promise.all` over caller-supplied input | Unbounded fan-out takes down the dependency and yourself |
| Accumulating into a shared array inside concurrent callbacks | Interleaved mutation, lost entries, order that changes per run |
| Sleeping to avoid a race | Makes the window smaller and the failure rarer, which makes it harder to diagnose |
| Retrying on a unique violation without changing the input | An infinite loop against a constraint that will never yield |
| Serializing everything behind one global lock | Correct and unshippable. Serialize per entity, never per service |

## Related Standards

- [`idempotency.md`](idempotency.md): key sourcing, fingerprints, replay, per-layer recipes
- [`resilience.md`](resilience.md): retries, DLQs, circuit breakers, bulkheads
- [`distributed-systems.md`](distributed-systems.md): saga, outbox, fencing tokens, consistency models
- [`database.md`](database.md): isolation configuration, transaction syntax, locking strategy
- [`postgresql.md`](postgresql.md): engine specifics, advisory locks, `pg_stat_activity`
- [`redis.md`](redis.md): atomic compound operations, Lua, MULTI/EXEC
- [`message-queues.md`](message-queues.md): ordering guarantees, idempotent consumers, partitioning
- [`immutability.md`](immutability.md): the race classes immutable data removes outright
- [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md): the always-on gate that loads this file
