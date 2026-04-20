# Resilience

## Error Classification

Every error must be classified as **transient** or **permanent** before deciding how to handle it.

| Type | Examples | Action |
|------|----------|--------|
| Transient | Network timeout, 429 rate limit, 503 service unavailable, connection reset, lock contention | Retry with backoff |
| Permanent | 400 bad request, 404 not found, validation failure, schema mismatch, auth rejected | Fail immediately, do not retry |
| Ambiguous | 500 internal server error, unknown exception | Retry with limit, then treat as permanent |

Classify at the boundary where the error originates. Propagate the classification upstream so callers can make informed decisions.

```
// Bad: treats all errors the same
catch (error) {
  logger.error("failed", { error });
  throw error;
}

// Good: classifies and routes
catch (error) {
  if (isTransient(error)) {
    logger.warn("transient failure, will retry", { error, attempt });
    throw new RetryableError(error);
  }
  logger.error("permanent failure", { error });
  throw new PermanentError(error);
}
```

## Retry Strategy

Use exponential backoff with jitter for all retries. Never retry in a tight loop.

- **Base delay**: 100-500ms depending on the operation
- **Multiplier**: 2x per attempt
- **Jitter**: add random 0-50% of delay to prevent thundering herd
- **Max retries**: 3 for synchronous paths, 5 for async/background
- **Max delay cap**: never exceed 30s between retries
- **Timeout budget**: total retry time must fit within the caller's timeout

Only retry transient errors. Retrying permanent errors wastes resources and delays the real failure.

## Idempotency

### Principle

Every write operation must be safe to execute more than once with the same result. This applies at every layer, not just REST APIs.

### Patterns by Layer

| Layer | Pattern |
|-------|---------|
| REST API | `Idempotency-Key` header, stored with response, TTL 24h |
| Message/event handler | Deduplication by message ID before processing |
| Database write | Conditional put, upsert with unique constraint, optimistic locking |
| State machine | Transition only from expected state, reject duplicate transitions |
| File/object storage | Write with precondition (ETag, version ID) |

### Implementation Checklist

- [ ] Can this handler receive the same input twice? (network retry, queue redelivery, Lambda retry)
- [ ] If yes, what prevents duplicate side effects?
- [ ] Is the deduplication key durable? (not in-memory, survives restarts)
- [ ] What is the deduplication window? (TTL must exceed max retry/redelivery time)

## Deduplication

### Message Processing

For queue consumers, event handlers, and webhook receivers:

1. Extract a unique message identifier (message ID, event ID, idempotency key)
2. Check if already processed (database lookup, cache check)
3. Process the message
4. Record the message ID as processed (same transaction as the business write when possible)

The deduplication store must be durable. In-memory sets are lost on restart and cause reprocessing.

### Database-Level Deduplication

Prefer database constraints over application checks:

- Unique indexes prevent duplicate inserts without TOCTOU races
- `INSERT ... ON CONFLICT DO NOTHING` or `putItem` with condition expression
- Composite unique keys for natural deduplication (e.g., `user_id + action + date`)

## Dead Letter Queues

Every async processor must have a DLQ strategy:

1. **Configure a DLQ** on every queue and event source mapping
2. **Set maxReceiveCount** based on the retry policy (typically 3-5)
3. **Report partial batch failures** instead of failing the entire batch. Return individual failure IDs so successfully processed messages are not redelivered
4. **Monitor DLQ depth** with alerts. Messages in the DLQ mean data is not being processed
5. **Build a reprocessing path** so DLQ messages can be replayed after fixing the root cause

## Circuit Breakers

For calls to external services that may be degraded:

- **Closed** (normal): requests pass through, failures are counted
- **Open** (tripped): requests fail immediately without calling the service, checked periodically
- **Half-open** (probing): limited requests pass through to test recovery. Send a single probe request on a timer. If it succeeds, move to Closed. If it fails, return to Open and reset the timer with backoff

Track: failure count, failure rate, response time. Trip on sustained failure, not a single error. For database-specific failures (deadlocks, lock timeouts), apply the same circuit breaker pattern. See `standards/database.md` Connection Management for retry-worthy transient errors.

**Error-type thresholds**: use separate counters per error class. A spike in timeouts must not trip the circuit for 5xx errors, and vice versa. Set independent thresholds for: connection refused, timeout, and 5xx. A mixed spike trips on the most severe class that crosses its own threshold.

**Request hedging**: when a request to a primary instance exceeds the p95 latency threshold, send a duplicate request to a backup instance in parallel. Use whichever responds first and cancel the other. Apply only to idempotent reads. Hedging trades bandwidth for tail-latency reduction.

**Timeout jitter**: add ±10-20% random jitter to timeout values. Synchronized timeouts cause all callers to retry at the same moment after a transient slowdown, recreating the spike that caused the timeout in the first place.

## Partial Failure

When an operation involves multiple steps or items:

- Process each item independently. One failure must not abort the batch
- Track per-item success/failure status
- Return detailed results: which items succeeded, which failed, and why
- For multi-step workflows, ensure state is consistent after partial failure (compensating actions or saga pattern)

## Non-Critical Dependency Fallback

When a non-critical dependency is used inside a critical path, the critical path must survive the dependency's failure.

Classify each dependency call by its criticality to the current request:

| Classification | On failure | Examples |
|---------------|-----------|---------|
| Critical | Fail the request. Return error to caller | Auth token validation, payment processing, session lookup |
| Non-critical | Return safe default. Log warning. Continue | Price enhancement, view counter, recommendation, analytics |

**Rule: wrap non-critical dependency reads in try/catch with a safe default. Never let a non-critical feature crash a critical path.**

```typescript
// Bad: Redis failure crashes the API response
const scores = await getRecommendationScores(userId);

// Good: API responds without recommendations
let scores: Map<string, number>;
try {
  scores = await getRecommendationScores(userId);
} catch {
  logger.warn("recommendation scores unavailable, returning defaults");
  scores = new Map();
}
```

Log every fallback activation at `warn` level. Silent fallbacks hide chronic dependency issues.

See `standards/redis.md` "Non-Critical Redis Fallback" for Redis-specific patterns.

## Timeouts

Every external call must have an explicit timeout:

- HTTP requests: connect timeout + read timeout
- Database queries: statement timeout
- Queue operations: visibility timeout aligned with processing time
- Background jobs: execution timeout with cleanup

Never rely on defaults. Defaults are often too generous (30s, 60s) and cascade into system-wide slowdowns. Database connection and query timeout values: see `standards/database.md` for per-query-type limits and statement timeout configuration.

## Back Pressure

When a system receives more load than it can process, uncontrolled queuing leads to cascading failure: memory exhaustion, timeouts, and full outage.

| Strategy | How it works | When to use |
|----------|-------------|-------------|
| Bounded queues | Max size on every in-memory queue and channel. Reject or drop when full | Default for all async processing |
| Rate limiting (server-side) | Limit requests per client or per endpoint. Return 429 with `Retry-After` | API gateways, public endpoints |
| Load shedding | Drop low-priority requests early when load exceeds capacity | When not all requests have equal business value |
| Admission control | Measure current latency/utilization. Reject new requests before they consume resources | Latency-sensitive services |

**Default rule**: every queue must have a max size. Every service must have a plan for what happens at 10x normal load. "It will scale" is not a plan.

### Load Shedding Priority

When shedding load, classify requests:

1. **Critical**: auth, payments, data writes. Shed last
2. **Important**: core reads, search, notifications. Shed under heavy load
3. **Deferrable**: analytics, recommendations, prefetch. Shed first

Return 503 with `Retry-After` header so clients know when to come back.

## Bulkhead

Isolate failure domains so one misbehaving dependency does not take down the entire service.

| Level | Implementation |
|-------|---------------|
| Connection pool per dependency | If the payment service is slow, it exhausts its own pool, not the shared one |
| Process isolation | Critical and non-critical workloads in separate processes or containers |
| Service isolation | Separate deployments for critical vs non-critical traffic (read vs write services) |
| Queue isolation | Separate queues per priority or per tenant. One noisy tenant cannot starve others |

**Default rule**: at minimum, use separate connection pools for each external dependency. A single shared pool is a shared-fate failure waiting to happen.

## Concurrency Control

Limit how many operations run in parallel to protect downstream systems and your own resources.

| Pattern | Implementation | When to use |
|---------|---------------|-------------|
| Semaphore | Count-based gate, N concurrent operations max | Limiting parallel DB queries, API calls, file operations |
| Worker pool | Fixed number of workers pulling from a queue | Background job processing, fan-out tasks |
| Internal rate limiter | Token bucket or sliding window within the application | Protecting a fragile downstream with a known capacity |
| Batch + throttle | Collect items, process in batches with delay between batches | Bulk operations: backfills, migrations, mass notifications |

- Default fan-out limit: start conservative (5-10), measure, then increase
- Always instrument: track queue depth, active workers, and rejection count
- Set a timeout on each unit of work. A stuck worker must not permanently reduce pool capacity
