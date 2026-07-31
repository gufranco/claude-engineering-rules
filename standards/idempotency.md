# Idempotency and Deduplication

How to make a write safe to execute more than once. Loaded on demand. Triggers in [`../rules/index.yml`](../rules/index.yml).

## Scope

| Concern | Owner |
|---------|-------|
| Key sourcing, fingerprinting, storage schema, replay semantics, per-layer recipes | This file |
| Interleaving, locks, isolation levels, the correctness ladder | [`concurrency.md`](concurrency.md) |
| Retry policy, backoff, DLQ, circuit breakers | [`resilience.md`](resilience.md) |
| Outbox, saga, delivery guarantees | [`distributed-systems.md`](distributed-systems.md) |
| Consumer wiring, offsets, partitioning | [`message-queues.md`](message-queues.md) |
| Migration idempotency, `IF NOT EXISTS` | [`../rules/lang/orm-migrations.md`](../rules/lang/orm-migrations.md) |

## Two Different Things

- **An idempotent operation** produces the same state no matter how many times it runs. `SET balance = 100` is idempotent. `INCREMENT balance BY 10` is not.
- **An idempotency key** makes a non-idempotent operation safe by remembering that this exact request already ran.

Reach for the first before the second. A key is bookkeeping around a design that could not be made naturally safe, and bookkeeping can be lost, expired, or mismatched.

## Design for Natural Idempotency First

| Instead of | Prefer | Why |
|-----------|--------|-----|
| `INCREMENT balance BY amount` | `SET balance = computed`, guarded by a version or expected value | Repeating the write cannot compound |
| `POST /items` creating a row per call | `PUT /items/{client-generated-id}` | The client names the resource, so the second call updates rather than creates |
| `create` after a lookup | `upsert` on a unique key | One statement, decided by the engine |
| `status = 'paid'` unconditionally | `UPDATE ... WHERE status = 'pending'` | The second call affects zero rows and says so |
| Append to a list column | Insert a row with a unique constraint | The constraint absorbs the duplicate |
| `sendEmail()` then record | Record with a unique key, then send only when the insert won | The winner sends, the loser does not |

An operation that is naturally idempotent still needs a dedup key when a side effect leaves the database, such as an email, a charge, or a webhook.

## Key Sourcing

| Source | Use when | Stability |
|--------|----------|-----------|
| Client-supplied `Idempotency-Key` header | Public or internal HTTP write endpoints | Stable only if the client reuses it on retry. Document that requirement |
| Provider event ID, such as a Stripe event `id` | Webhook receivers | Stable across the provider's own re-sends. Verify in the provider docs |
| Message ID or a producer-assigned business key | Queue consumers | Stable across redelivery. Broker-assigned delivery IDs are not |
| Natural business key, such as `userId + action + date` | Scheduled jobs, backfills, anything without a caller-supplied key | Stable by construction. Preferred when it exists |
| Derived fingerprint of semantically stable fields | Last resort when nothing else is available | Stable only if every field in it is stable |

**The stability rule.** A key derived from transport metadata is not an idempotency key. Timestamps, nonces, signatures, request IDs, and delivery attempt IDs all change on retry, so a key built from them catches network-level duplicates only and misses every application-level retry. Before writing the key derivation, answer one question in the design: if the caller retries in ten minutes, does this expression produce the same string? If no, pick a different source.

**The scope rule.** Keys are namespaced by tenant and by operation. A bare `key` column invites a collision between two tenants that both send `retry-1`, and between two endpoints that share a caller. Store `(tenant_id, endpoint, key)` as the unique tuple.

## Request Fingerprint

The key says "this request again". The fingerprint proves it really is the same request.

Hash the semantic content of the request: the normalized body, the path parameters, and the authenticated subject. Exclude everything that legitimately changes between retries, such as timestamps, trace headers, and the signature itself.

| Situation | Response |
|-----------|----------|
| Same key, same fingerprint, completed | Replay the stored response |
| Same key, same fingerprint, still running | 409, or wait and replay. See the concurrency section |
| Same key, different fingerprint | 422. The client reused a key for different content, which is a client bug |
| New key | Execute |

Returning the stored response for a mismatched fingerprint is the worst available outcome, because the caller receives a success for an operation that never ran.

## Storage

```sql
CREATE TABLE IF NOT EXISTS idempotency_record (
  tenant_id        uuid        NOT NULL,
  endpoint         text        NOT NULL,
  key              text        NOT NULL,
  fingerprint      text        NOT NULL,
  state            text        NOT NULL,
  response_status  int,
  response_headers jsonb,
  response_body    jsonb,
  resource_id      text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  completed_at     timestamptz,
  expires_at       timestamptz NOT NULL,
  CONSTRAINT idempotency_record_pkey PRIMARY KEY (tenant_id, endpoint, key),
  CONSTRAINT idempotency_record_state_check CHECK (state IN ('started', 'succeeded', 'failed'))
);

CREATE INDEX IF NOT EXISTS idempotency_record_expires_at_idx
  ON idempotency_record (expires_at);
```

The primary key is the mechanism. Two concurrent requests with the same key race to insert, and exactly one wins. Everything else in the table is bookkeeping around that guarantee.

Storage choice: the same database as the business write, whenever the two can share a transaction. Redis is acceptable for pure dedup with no response replay, and only with persistence enabled. An in-memory `Set` or `Map` is never acceptable, because a restart makes every past request new again.

Expiry: delete by `expires_at` on a schedule. The row is worthless once no client will retry, and the table grows forever without the sweep.

## Concurrency Semantics

Two requests with the same key arriving at once is the normal case, not the edge case. It is what a double-click produces.

| Strategy | Behavior | Trade-off |
|----------|----------|-----------|
| Reject, the default | Insert wins or loses. The loser returns 409 with a retry hint | Simple, no held connections, the client retries and gets the replay |
| Wait and replay | The loser polls for the winner's completion, then returns the stored response | Better client experience, holds a connection, needs a bounded wait and a fallback to 409 |

Never let the loser proceed to execute. That is the duplicate the whole mechanism exists to prevent.

## HTTP Recipe

```typescript
export async function withIdempotency<T>(
  ctx: RequestContext,
  fingerprint: string,
  execute: (tx: Transaction) => Promise<IdempotentResult<T>>,
): Promise<IdempotentResult<T>> {
  const claim = await claimKey(ctx, fingerprint);

  if (claim.kind === 'FingerprintMismatch') {
    return { status: 422, body: { error: 'idempotency_key_reused_with_different_body' } };
  }

  if (claim.kind === 'Replay') {
    return { ...claim.stored, replayed: true };
  }

  if (claim.kind === 'InFlight') {
    return { status: 409, body: { error: 'request_in_progress' } };
  }

  try {
    const result = await db.$transaction(async (tx) => {
      const produced = await execute(tx);
      await markSucceeded(tx, ctx, produced);
      return produced;
    });
    return result;
  } catch (error: unknown) {
    await markFailed(ctx, error);
    throw error;
  }
}
```

Four properties make this correct, and dropping any one of them breaks it:

1. The claim is an insert against the primary key, never a read followed by an insert. The read-then-insert version is the check-then-act race from [`concurrency.md`](concurrency.md).
2. The business write and the transition to `succeeded` share one transaction. If they do not, a crash between them leaves a key that blocks retries of work that never happened.
3. A failure moves the row to `failed` rather than leaving it `started`, so a retry can proceed.
4. The stored response includes the status code and the body the first caller received, so the replay is indistinguishable from the original.

Signal the replay to the caller with a response header such as `Idempotent-Replayed: true`. Clients use it to distinguish a fresh effect from a repeat, and it makes the mechanism visible in logs.

## Failure Modes

| Failure | What happens without care | Required handling |
|---------|--------------------------|-------------------|
| Crash after claim, before the business write | The key is `started` forever, so every retry gets a 409 | A `started` row older than the lease window is treated as abandoned and reclaimed |
| Crash between the business write and the completion mark | Either the work is invisible to the replay, or it is repeated | Same transaction for both. This is the reason for property 2 above |
| Permanent failure, such as validation | Retries either loop forever or are blocked forever | Mark `failed` and store the error response, then replay it. The client stops retrying because the answer is stable |
| Transient failure, such as a downstream timeout | The key blocks the retry that would have succeeded | Mark `failed` and allow reclaim, or delete the row |
| Multi-step effect where step 2 fails | A consumed key plus a half-done mutation, permanently | All steps in one transaction. If a step leaves the database, use an outbox or a compensating action, see [`distributed-systems.md`](distributed-systems.md) |
| Two deliveries carrying different keys for one logical event | Both pass the key check and both execute | A second guard on the business identity: a unique constraint on the natural key |
| Key expired before the client's last retry | The retry executes again | TTL must exceed the caller's total retry window, including their backoff schedule |

The last row of that table is the one people get wrong by a factor of ten. A provider that retries a webhook for three days needs a dedup window longer than three days, and a 24-hour TTL silently permits a duplicate on day two.

## Per-Layer Recipes

### Queue consumer

Dedup on the producer-assigned message ID, inside the same transaction as the business write.

```typescript
await db.$transaction(async (tx) => {
  await tx.processedMessage.create({ data: { messageId: message.id, consumer: CONSUMER_NAME } });
  await applyEffect(tx, message.payload);
});
```

A unique violation on `processedMessage` means this message was already handled, so acknowledge it and move on. Acknowledging is mandatory: an unacknowledged duplicate returns forever.

### Webhook receiver

- Use the provider's event ID, never your own request ID, and never the signature.
- Verify the signature before the dedup check, so an attacker cannot poison the dedup table with forged IDs.
- Return 2xx once the event is durably recorded, then process asynchronously. A receiver that processes inline times out and earns a re-send.
- Assume the provider will re-send a delivered event after any timeout, and assume ordering is not guaranteed.

### Scheduled job

- The natural key is the job name plus the period, such as `trial-expiry:2026-07-31`.
- Two overlapping runs are the norm when a run exceeds its interval. Serialize with an advisory lock or a unique row for the period, per [`concurrency.md`](concurrency.md).
- Per-item effects need their own key, such as `trial-expiry:2026-07-31:user-123`, so a partial run resumes without re-notifying the users it already handled.

### Calling someone else's API

- Send an `Idempotency-Key` on every non-idempotent outbound request, and reuse the same value across your retries of that request. A fresh key per attempt makes the header decorative.
- Derive it from your own operation identity, such as the payment attempt ID, so it survives a process restart mid-retry.
- Persist the key alongside the operation before the first attempt, never in memory only.

### Outbox publisher

The outbox row is the dedup record. Publish, then mark published, and accept that a crash between the two produces a duplicate delivery. That is why consumers dedup. Full mechanics in [`distributed-systems.md`](distributed-systems.md).

## TTL Selection

| Caller | Minimum window |
|--------|----------------|
| Browser or mobile client with manual retry | 24 hours |
| Internal service with a bounded retry policy | Longer than the total retry budget, so backoff multiplied by attempts, plus margin |
| Payment or billing provider webhooks | Match the provider's documented re-send window, commonly 3 days |
| Queue with a DLQ and manual replay | Longer than the maximum time a message can sit in the DLQ before replay |

State the chosen window and its reason where the record is created. A TTL nobody can justify gets shortened by the next person who sees the table size.

## Anti-Patterns

| Anti-pattern | Why it fails |
|--------------|--------------|
| Read the key, then insert if absent | The classic race. Use the insert and let the primary key decide |
| Key derived from a timestamp, nonce, or signature | Changes on every retry, so it never matches |
| In-memory `Set` or `Map` as the dedup store | Empty after every deploy and every crash |
| Dedup record committed in a separate transaction from the effect | A crash between them either loses the work or repeats it |
| Storing only the resource ID, not the response | The replay cannot reproduce the original status code or body |
| Returning the stored response when the fingerprint differs | Reports success for an operation that never ran |
| Deleting the key on any failure | A permanent failure then retries forever |
| Keeping the key on every failure | A transient failure blocks the retry that would have worked |
| One global key namespace | Two tenants collide, and one of them loses a write |
| Treating a 409 as a fatal client error | The correct client behavior is to retry and take the replay |

## Testing

Every write path ships both tests. The shapes are in [`../rules/testing.md`](../rules/testing.md), and the reason they belong together is that sequential and concurrent duplicates fail differently.

```typescript
it('creates one order and replays the response when called twice with the same key', async () => {
  const payload = buildOrderPayload();

  const first = await createOrder(payload);
  const second = await createOrder(payload);

  expect(second.status).toBe(first.status);
  expect(second.body.id).toBe(first.body.id);
  expect(second.headers['idempotent-replayed']).toBe('true');
  expect(await db.order.count({ where: { idempotencyKey: payload.idempotencyKey } })).toBe(1);
});
```

Also required:

- Ten parallel calls with the same key produce one row, and every caller receives either the response or a 409.
- The same key with a changed body returns 422.
- A restart between the two calls does not produce a second row. This is the test that catches an in-memory store.
- A permanent failure replays the failure rather than re-executing.
- A key past its TTL is treated as new.

## Status of the Idempotency-Key Header

`Idempotency-Key` is not standardized. The IETF HTTPAPI working group draft `draft-ietf-httpapi-idempotency-key-header` reached revision 07 on 2025-10-15 with an intended status of Standards Track, and the datatracker records it as expired and archived without publication as an RFC.

Use the header name and the semantics in this file because payment providers converged on them and clients already expect them. Never cite an RFC number for this behavior, and document the semantics in your own API reference rather than pointing callers at a specification that does not exist.

## Related Standards

- [`concurrency.md`](concurrency.md): the race that the claim-by-insert avoids, and the correctness ladder
- [`resilience.md`](resilience.md): retry policy, backoff, DLQ, the patterns-by-layer overview
- [`distributed-systems.md`](distributed-systems.md): outbox, saga, compensating actions
- [`message-queues.md`](message-queues.md): consumer wiring, offsets, poison messages
- [`api-design.md`](api-design.md): status code selection and error body shape
- [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md): the always-on Idempotency and Deduplication tables
