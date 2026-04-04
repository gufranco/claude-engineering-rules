# Event-Driven Architecture

## CQRS

Separate read and write models. The write model enforces invariants and emits events. The read model is optimized for queries and rebuilt from events.

| Concern | Write side | Read side |
|---------|-----------|-----------|
| Model shape | Normalized, invariant-enforcing aggregates | Denormalized, query-optimized projections |
| Storage | Relational or event store | Document store, materialized views, search index |
| Validation | Full domain validation | None, data is already validated |
| Scaling | Scale for write throughput | Scale independently for read throughput |
| Consistency | Strong within aggregate boundary | Eventually consistent with write side |

Only apply CQRS when read and write patterns diverge significantly. A simple CRUD resource does not benefit from the split.

## Event Sourcing

Store state as an immutable sequence of events. Current state is derived by replaying events from the beginning or from a snapshot.

- Every state change produces an event. No direct state mutation.
- Events are immutable after persistence. Never update or delete an event.
- Snapshots reduce replay cost. Take a snapshot every N events or on a time interval.
- Replay must be deterministic. Same events in same order must produce identical state.

```typescript
interface DomainEvent {
  readonly eventId: string;
  readonly aggregateId: string;
  readonly version: number;
  readonly occurredAt: Date;
  readonly type: string;
  readonly payload: Record<string, unknown>;
}

function replay(events: readonly DomainEvent[]): AggregateState {
  return events.reduce(
    (state, event) => applyEvent(state, event),
    initialState(),
  );
}
```

## Outbox Pattern

Store domain events in the same database transaction as the aggregate change. A separate process reads the outbox table and publishes events to the broker. This guarantees at-least-once delivery without distributed transactions.

1. Begin transaction.
2. Update aggregate state.
3. Insert event into the `outbox` table.
4. Commit transaction.
5. A poller or CDC process reads unpublished events and sends them to the broker.
6. Mark events as published after broker acknowledgment.

Never publish to the broker inside the domain transaction. A broker failure would roll back the domain change, or worse, the domain commits but the event is lost.

## Saga Pattern

Coordinate multi-service workflows where each step may need compensation on failure.

| Style | How it works | When to use |
|-------|-------------|-------------|
| Choreography | Each service listens for events and acts independently | Simple flows with 2-3 services, no central coordination needed |
| Orchestration | A central coordinator directs each step and handles compensation | Complex flows with 4+ services, conditional branching, or strict ordering |

Choreography scales better but becomes hard to trace. Orchestration is easier to debug but introduces a single coordinator. For flows with more than three steps, prefer orchestration.

Every saga step must have a compensating action. Document the compensation for each step before implementing.

## Event Versioning

Events persisted today must be readable years from now. Use backward-compatible evolution.

- Add new fields with defaults. Existing consumers ignore unknown fields.
- Never remove or rename fields in an existing event type.
- When a breaking change is unavoidable, create a new event type and version the name: `OrderPlacedV2`.
- Write upcasters that transform old event shapes into the latest version at read time.

```typescript
function upcast(event: DomainEvent): DomainEvent {
  if (event.type === "OrderPlaced" && event.version === 1) {
    return {
      ...event,
      version: 2,
      payload: { ...event.payload, currency: "USD" },
    };
  }
  return event;
}
```

## Idempotent Handlers

Every event consumer must handle the same event more than once without side effects. Networks retry. Brokers redeliver.

- Store processed event IDs in a durable dedup table.
- Check the dedup table before processing. Skip if already seen.
- Use the event's unique `eventId` as the dedup key.
- Set a TTL on dedup entries matching the broker's maximum redelivery window.

```typescript
async function handleEvent(event: DomainEvent): Promise<void> {
  const alreadyProcessed = await dedupStore.exists(event.eventId);
  if (alreadyProcessed) {
    logger.info("duplicate event, skipping", { eventId: event.eventId });
    return;
  }

  await processEvent(event);
  await dedupStore.mark(event.eventId, { ttl: SEVEN_DAYS });
}
```

## Partition Key Strategy

Choose partition keys that preserve ordering where it matters while distributing load.

| Strategy | Ordering guarantee | Distribution |
|----------|-------------------|-------------|
| Aggregate ID | All events for one aggregate arrive in order | Good for most domain events |
| Entity type + ID | Events for same entity type grouped | Useful when consumers handle one entity type |
| Random / round-robin | No ordering | Maximum throughput, only for independent events |

Default to aggregate ID. It guarantees that all events for a single aggregate are processed sequentially, which prevents race conditions in projections and sagas.

## Dead Letter Queue

Route events that fail processing after exhausting retries to a DLQ.

- Set a retry limit per consumer: 3-5 attempts with exponential backoff.
- After the limit, move the event to the DLQ with the failure reason attached.
- Monitor DLQ depth. A growing DLQ signals a systemic issue, not just bad messages.
- Provide a manual replay mechanism for DLQ events after the root cause is fixed.
- Never auto-retry DLQ events without human review. The failure may corrupt data on repeat.

## Consumer Lag Monitoring

Track how far behind each consumer is from the latest event in the stream.

| Metric | Alert threshold | Action |
|--------|----------------|--------|
| Consumer lag in events | Above 1000 for 5 minutes | Investigate consumer throughput |
| Consumer lag in time | Above 30 seconds sustained | Scale consumers or check for blocked processing |
| DLQ depth | Above 0 | Investigate failed events immediately |
| Processing latency p99 | Above 500ms | Profile consumer, check downstream dependencies |

Expose lag as a metric in the observability stack. Consumer lag is the primary indicator of event-driven system health.
