# Redis

## When to Use Redis

| Use case | Pattern | Alternative to consider |
|----------|---------|------------------------|
| Ephemeral counters, rate limiters | INCRBY + TTL | Database counter with scheduled cleanup |
| Cache for read-heavy data | Cache-aside with TTL | See [`standards/caching.md`](caching.md) |
| Pub/sub for real-time messaging | PUBLISH/SUBSCRIBE | See [`standards/websocket-realtime.md`](websocket-realtime.md) |
| Distributed locks | SET NX EX | See [`standards/distributed-systems.md`](distributed-systems.md) |
| Session storage | GET/SET with TTL | Database-backed sessions if durability matters |

Redis is ephemeral by default. If the data must survive a restart or eviction, it belongs in a database.

## Atomic Compound Operations

Redis commands are individually atomic. Two commands issued sequentially are not. If the process crashes, the connection drops, or another client interleaves between them, the intermediate state is visible.

**Rule: when two or more Redis commands must execute as a unit, use a Lua script or `MULTI/EXEC` pipeline.**

### Common violations

| Pattern | Risk | Fix |
|---------|------|-----|
| `INCRBY` then `EXPIRE` | Key loses TTL on crash between commands. Counter never resets | Lua script that does both |
| `GET` then conditional `SET` | Race: another client writes between read and write | Lua script or `WATCH/MULTI/EXEC` |
| `SETNX` then `EXPIRE` | Key created without TTL on crash. Lock never releases | Single `SET key value NX EX seconds` |
| `DEL` then `SET` | Other client reads non-existence between delete and set | `SET` overwrites, no need for `DEL` first |
| `EXISTS` then `INCR` | Race: key expires between check and increment | `INCR` creates the key if missing. Check after |

### Lua scripts

Lua scripts execute atomically on the Redis server. No other command runs between the script's Redis calls.

**Bad:** two commands, not atomic.

```typescript
const newTotal = await redis.incrby(key, amount);
await redis.expire(key, ttlSeconds);
```

**Good:** a Lua script, atomic.

```typescript
const INCR_WITH_TTL =
  "local t = redis.call('INCRBY', KEYS[1], ARGV[1]) " +
  "if redis.call('TTL', KEYS[1]) == -1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end " +
  "return t";

const newTotal = (await redis.eval(
  INCR_WITH_TTL, 1, key, amount, ttlSeconds,
)) as number;
```

The script sets the TTL only when the key has none, so the window starts at the first increment and the counter resets when it expires. An `EXPIRE` on every increment pushes the expiry forward on each write, and a counter that keeps receiving writes never resets.

Rules for Lua scripts:

- Define the script as a module-level constant. Do not construct scripts dynamically
- Use `KEYS[]` for key names and `ARGV[]` for values. Never interpolate strings into the script body
- Keep scripts short. Complex business logic belongs in the application, not in Lua
- Use `EVALSHA` with `SCRIPT LOAD` for frequently executed scripts to avoid resending the script text

### MULTI/EXEC pipeline

Use `MULTI/EXEC` when atomicity is needed but the commands are independent. No command depends on the result of a previous one within the transaction.

```typescript
const results = await redis.multi()
  .incrby(key, amount)
  .expire(key, ttlSeconds, "NX")
  .exec();
```

The `NX` option, available from Redis 7.0, sets the expiry only when the key has none, for the same reason as the Lua script above.

Use Lua when a command depends on a previous result within the same atomic block.

## Key Design

- Prefix keys by purpose: `cache:`, `lock:`, `counter:`, `session:`, `pubsub:`
- Include the entity type and ID: `counter:volume_vig:{lineId}`
- Separate segments with colons: `cache:user:42:profile`
- Keep key names short but readable. Redis stores keys in memory
- Never use user-controlled input directly in key names without validation. Colons and special characters in user input can collide with key structure

## TTL Management

- Every key must have a TTL unless it represents permanent configuration. Keys without TTL accumulate until Redis runs out of memory
- Set TTL at creation time, not as a separate command (see Atomic Compound Operations above)
- Use jitter on TTL to prevent synchronized expiration: `ttl + random(0, ttl * 0.1)`
- Monitor keys without TTL in production. A growing count of TTL-less keys is a memory leak

## Connection Management

- Use a connection pool. One connection per request exhausts Redis under load
- Separate connections for pub/sub: a client in subscriber mode cannot issue regular commands. Create a dedicated subscriber connection and a dedicated publisher connection
- Lazy-initialize connections that are not needed on every request. A module that exports pure functions must not create a Redis connection at import time. See the "No side effects at module level" item under "Fundamentals" in [`code-style.md`](code-style.md)
- Set `connectTimeout` and `commandTimeout`. A hanging Redis connection blocks the caller indefinitely without a timeout
- Handle `ECONNREFUSED` and `ETIMEDOUT` as transient errors. Retry with backoff, not immediate retry

## Non-Critical Redis Fallback

When Redis serves a non-critical feature, such as price enhancement, recommendation scoring, or view counters, inside a critical path, such as serving API responses or processing payments, the critical path must survive Redis failure.

**Rule: wrap non-critical Redis reads in a try/catch that returns a safe default.**

**Bad:** a Redis failure crashes the odds endpoint.

```typescript
const volumeMap = await getVolumes(propLineIds);
```

**Good:** odds still serve without volume vig.

```typescript
const volumeMap = await getVolumes(propLineIds).catch(
  (error: unknown): Map<string, number> => {
    logger.warn({ err: error, operation: "getVolumes" }, "volume lookup unavailable, serving odds without volume vig");
    return new Map();
  },
);
```

Classify each Redis usage:

| Classification | Behavior on failure | Examples |
|---------------|--------------------|---------|
| Critical | Fail the request. Return error to caller | Session lookup, rate limit check, distributed lock |
| Non-critical | Return safe default. Log warning. Continue | Price enhancement, view counter, recommendation score |

Log every fallback activation at `warn` level with the operation name and error. Silent fallbacks hide chronic Redis issues.

## Pub/Sub

- Use a dedicated publisher client, separate from the main Redis client and from any subscriber clients
- Publisher connections must not be created at module level if the module also exports pure functions. Use lazy initialization
- Messages are fire-and-forget. Redis pub/sub has no delivery guarantee. If the subscriber is disconnected, the message is lost
- For messages that must not be lost, use Redis Streams instead of pub/sub
- Set a timeout on `publish()` calls. A blocked publish holds the caller

## Testing

- Integration tests for Redis operations must connect to a real Redis instance, not a mock. Add Redis to the test environment's docker-compose
- Test TTL behavior without waiting on the clock. Right after the write, assert that `PTTL` returns a value inside the expected bound. To test the expired path, remove the key at once with `PEXPIRE key 0`, then assert the code treats it as missing. Never sleep in a test
- Test atomic operations under concurrency: spawn multiple promises that race on the same key, verify the final state is consistent
- Pure functions that compute values from Redis data, such as thresholds, steps, or pricing, can be unit tested without Redis

## Related Standards

- [`concurrency.md`](concurrency.md): where a Redis lock sits on the correctness ladder, and why an expired lock needs a fencing token
- [`idempotency.md`](idempotency.md): Redis as a dedup store, including the persistence and TTL requirements
