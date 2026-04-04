# Message Queues

## Topology Patterns

Pick the topology that matches the communication intent. Wrong topology forces workarounds that grow into maintenance liabilities.

| Pattern | How it works | When to use |
|---------|-------------|-------------|
| Point-to-point (queue) | One producer, one consumer group. Each message is delivered to exactly one consumer | Task distribution, job processing, command dispatch |
| Pub/sub (topic) | One producer, many independent subscriber groups. Each group gets a copy | Event broadcasting, domain events, notifications |
| Fanout | Message is copied to all bound queues unconditionally | Cache invalidation, audit logging, parallel processing of the same event |
| Content-based routing | Messages are routed based on attributes (headers, type field, payload fields) | Multi-tenant routing, priority-based processing, type-specific handlers |
| Request-reply | Producer sends a message with a reply-to address, consumer responds to that address | Async RPC, long-running operations with status callbacks |

### Decision Matrix

| Requirement | Use |
|-------------|-----|
| "Exactly one consumer must process this" | Point-to-point queue |
| "Multiple independent systems must react" | Pub/sub topic |
| "All consumers must receive every message" | Fanout exchange |
| "Route by message type without consumer filtering" | Content-based routing |
| "Consumer count will change independently of producer" | Pub/sub topic |
| "Strict ordering per entity" | Single partition/queue with ordering key |

**Default rule**: start with a simple queue for commands and a topic for events. Add fanout and content-based routing only when filtering at the consumer is too expensive or complex.

## Message Format

### Envelope Structure

Every message must carry metadata separate from the business payload. The envelope enables routing, deduplication, tracing, and schema evolution without parsing the payload.

```typescript
interface MessageEnvelope<T = unknown> {
  readonly id: string;              // unique message ID, UUID v7 or ULID
  readonly type: string;            // dot-separated event type: "order.created"
  readonly source: string;          // producing service: "order-service"
  readonly timestamp: string;       // ISO 8601 UTC: "2026-03-27T14:30:00.000Z"
  readonly correlationId: string;   // trace through the system, propagated from caller
  readonly causationId: string;     // ID of the message that caused this one
  readonly schemaVersion: number;   // integer, monotonically increasing
  readonly contentType: string;     // "application/json", "application/protobuf"
  readonly payload: T;              // the business data
}
```

Rules:

- `id` must be globally unique. Use UUID v7 or ULID for time-ordered IDs that work as deduplication keys.
- `type` must use a fixed vocabulary per bounded context. Document every type in a schema registry or shared constants file.
- `correlationId` must be propagated from the originating request through every message in the chain. Never generate a new one mid-chain.
- `causationId` must reference the `id` of the message that triggered this one. For user-initiated actions, `causationId` equals `correlationId`.
- `schemaVersion` must be an integer. Increment on every breaking change.

### Schema Versioning

| Strategy | How | When to use |
|----------|-----|-------------|
| Additive only | Add new optional fields, never remove or rename | Default for all changes |
| Version in envelope | `schemaVersion` field, consumer handles multiple versions | When breaking changes are unavoidable |
| Topic-per-version | `order.created.v1`, `order.created.v2` | When consumers cannot be updated simultaneously |
| Schema registry | Confluent Schema Registry, AWS Glue, or equivalent | Kafka-based systems, cross-team contracts |

**Default rule**: make all changes additive. New fields are optional with defaults. Consumers must ignore unknown fields. Breaking changes require a new schema version and a migration plan.

### Serialization Format

| Format | Size | Schema enforcement | Language support | When to use |
|--------|------|-------------------|-----------------|-------------|
| JSON | Largest | Runtime (Zod, JSON Schema) | Universal | Default for most systems, debugging friendly |
| Protocol Buffers | Smallest | Compile-time `.proto` files | Wide, codegen required | High-throughput systems, strict cross-language contracts |
| Avro | Small | Schema registry, binary | JVM-native, libraries for others | Kafka ecosystems, schema evolution with registry |

**Default rule**: use JSON unless message volume exceeds 10K/sec or payload size is a bottleneck. Protobuf for high-throughput cross-service contracts. Avro when the Kafka ecosystem already uses it.

## Consumer Patterns

### Pattern Selection

| Pattern | How it works | When to use |
|---------|-------------|-------------|
| Competing consumers | Multiple consumers share a queue. Each message goes to one consumer | Scale horizontally, distribute workload |
| Consumer groups | Named groups on a topic. Each group gets every message, each message goes to one member within the group | Multiple independent services subscribing to the same events |
| Single-active consumer | Only one consumer processes at a time. Failover to standby on failure | Ordered processing where parallelism breaks correctness |
| Batch consumption | Consumer pulls N messages at once, processes as a batch | High-throughput writes, bulk database inserts |

### Concurrency Limits

| Broker | How to limit concurrency |
|--------|-------------------------|
| SQS | `MaxNumberOfMessages` per receive (1-10), control polling frequency |
| RabbitMQ | `prefetchCount` per channel or per consumer |
| Kafka | Number of partitions bounds max parallelism per consumer group |
| NATS JetStream | `MaxAckPending` on the consumer |
| Redis Streams | `COUNT` on `XREADGROUP`, application-level semaphore |

Rules:

- Set `prefetchCount` or equivalent to match the consumer's processing capacity. A consumer with 10 prefetched messages and a 5-second processing time holds messages hostage for 50 seconds.
- Start with a concurrency limit of 1 per consumer instance. Increase only after measuring that processing is I/O-bound and ordering constraints allow it.
- For batch consumption, set batch size based on downstream write capacity. 100 inserts per batch is a reasonable starting point. Measure and adjust.

### Batch Consumer Implementation

```typescript
async function processBatch(messages: readonly SQSRecord[]): Promise<SQSBatchResponse> {
  const failures: SQSBatchItemFailure[] = [];

  for (const message of messages) {
    try {
      const envelope = parseEnvelope(message.body);
      await handleMessage(envelope);
    } catch (error) {
      failures.push({ itemIdentifier: message.messageId });
      logger.error("message processing failed", {
        messageId: message.messageId,
        error,
      });
    }
  }

  return { batchItemFailures: failures };
}
```

Report individual failures, not the entire batch. A single poison message must not block the rest of the batch.

## Ordering Guarantees

Total ordering across an entire topic is expensive and rarely necessary. Order within a business entity is what most systems need.

| Guarantee level | How | Trade-off |
|----------------|-----|-----------|
| No ordering | Default in most queues. Messages arrive in approximate FIFO | Maximum throughput and parallelism |
| Partition-level | Kafka partitions, SQS FIFO group IDs, Kinesis shard keys | Ordered within key, parallel across keys |
| Total FIFO | Single partition, single consumer | Minimum throughput, maximum ordering |

### Ordering Key Selection

| Business entity | Ordering key | Rationale |
|----------------|-------------|-----------|
| User actions | `userId` | All actions for a user are ordered, different users are parallel |
| Order lifecycle | `orderId` | Create, update, ship, deliver events for one order stay ordered |
| Inventory changes | `skuId` | Stock increments and decrements for one SKU are ordered |
| Payment processing | `paymentId` | Charge, capture, refund for one payment stay ordered |

Rules:

- Choose the ordering key at the entity level, not the aggregate level. `orderId`, not `customerId`, unless the business requires customer-level ordering.
- When using SQS FIFO, the `MessageGroupId` is the ordering key. One group = one ordered sequence.
- When using Kafka, the partition key determines the partition. Same key = same partition = ordered delivery.
- Never rely on cross-partition ordering. If two events must be ordered and have different keys, restructure them under a common key or use a saga.

### Out-of-Order Delivery

Even with ordering guarantees, consumers must handle redeliveries and restarts that can cause out-of-order processing.

```typescript
async function handleOrderEvent(envelope: MessageEnvelope<OrderEvent>): Promise<void> {
  const { payload, schemaVersion } = envelope;

  const current = await orderRepository.findById(payload.orderId);
  if (current === undefined) {
    if (payload.type !== "order.created") {
      await sendToDeadLetter(envelope, "received non-create event for unknown order");
      return;
    }
  }

  if (current !== undefined && payload.sequenceNumber <= current.lastSequenceNumber) {
    logger.warn("out-of-order or duplicate event, skipping", {
      orderId: payload.orderId,
      eventSequence: payload.sequenceNumber,
      currentSequence: current.lastSequenceNumber,
    });
    return;
  }

  await orderRepository.update(payload.orderId, {
    ...applyEvent(current, payload),
    lastSequenceNumber: payload.sequenceNumber,
  });
}
```

Attach a monotonically increasing sequence number per entity. Consumers must compare against the last processed sequence and discard stale events.

## Error Handling

### Retry Policy

| Strategy | How | When to use |
|----------|-----|-------------|
| Immediate retry | Redeliver immediately, N times | Transient errors with instant recovery: brief network blip |
| Delayed retry | Redeliver after a backoff period | Rate limits, temporary downstream unavailability |
| Exponential backoff | Increase delay between retries: 1s, 2s, 4s, 8s | Default for all retries |
| Move to DLQ | After max attempts, move to a dead letter queue | Poison messages, permanent failures |

Rules:

- Every queue must have a DLQ configured. No exceptions.
- Set `maxReceiveCount` or equivalent to 3-5 attempts before DLQ routing.
- Use visibility timeout (SQS) or nack with requeue delay (RabbitMQ) for delayed retries. Never use `setTimeout` or `sleep` in the consumer.
- Classify errors before retrying. Permanent errors (validation failure, schema mismatch, missing required field) must go directly to the DLQ. Retrying permanent errors wastes time and delays the alert.

### Dead Letter Queue Configuration

```typescript
// SQS example: main queue with DLQ
const dlq = new sqs.Queue(this, "OrderDLQ", {
  retentionPeriod: Duration.days(14),
});

const mainQueue = new sqs.Queue(this, "OrderQueue", {
  deadLetterQueue: {
    queue: dlq,
    maxReceiveCount: 3,
  },
  visibilityTimeout: Duration.seconds(30),
});
```

DLQ retention must be at least 14 days. This gives the team time to investigate and replay.

### Poison Message Detection

A poison message is one that causes the consumer to fail on every attempt. Without detection, it blocks the queue for other messages.

Detection rules:

- Track the `ApproximateReceiveCount` (SQS) or delivery count (RabbitMQ, NATS) for each message.
- If the count exceeds 1 and the error is a validation or parse error, route to DLQ immediately without further retries.
- Log every DLQ routing with the full message envelope, the error, and the attempt count.

### DLQ Reprocessing

Build a reprocessing pipeline from the start, not after the first incident.

```typescript
async function reprocessDlq(dlqUrl: string, targetUrl: string): Promise<ReprocessResult> {
  let processed = 0;
  let failed = 0;

  while (true) {
    const response = await sqs.receiveMessage({
      QueueUrl: dlqUrl,
      MaxNumberOfMessages: 10,
      WaitTimeSeconds: 1,
    });

    if (response.Messages === undefined || response.Messages.length === 0) {
      break;
    }

    for (const message of response.Messages) {
      try {
        await sqs.sendMessage({
          QueueUrl: targetUrl,
          MessageBody: message.Body!,
        });
        await sqs.deleteMessage({
          QueueUrl: dlqUrl,
          ReceiptHandle: message.ReceiptHandle!,
        });
        processed++;
      } catch {
        failed++;
      }
    }
  }

  return { processed, failed };
}
```

## Backpressure

Uncontrolled message consumption leads to resource exhaustion in the consumer, cascading failures to downstream systems, and eventually message loss or service outage.

### Prefetch and Flow Control

| Broker | Mechanism | Rule |
|--------|-----------|------|
| RabbitMQ | `prefetchCount` | Set to the number of messages the consumer can process concurrently. Never set to 0 (unlimited) |
| SQS | `MaxNumberOfMessages` + polling interval | Receive 1-10 messages per poll. Control throughput via polling frequency |
| Kafka | `max.poll.records` + `max.poll.interval.ms` | Set `max.poll.records` to what the consumer can process within `max.poll.interval.ms` |
| NATS JetStream | `MaxAckPending` | Limits unacknowledged messages per consumer |
| Redis Streams | `COUNT` parameter on `XREADGROUP` | Application-level control per read |

### Consumer Lag Monitoring

Consumer lag is the difference between the latest message in the queue and the latest message the consumer has processed. Rising lag means the consumer cannot keep up.

| Metric | Alert threshold | Action |
|--------|----------------|--------|
| Queue depth (absolute) | 10x normal steady-state depth | Scale consumers, investigate slow processing |
| Consumer lag (time) | Messages older than 5 minutes unprocessed | Scale consumers, check for stuck consumers |
| Lag growth rate | Increasing for 10+ minutes | Consumer throughput is below production rate, scale immediately |

### Auto-Scaling Consumers

```typescript
// Scaling policy based on queue depth
const scalingPolicy: ScalingConfig = {
  metric: "ApproximateNumberOfMessagesVisible",
  targetValue: 100,          // target messages per consumer
  scaleOutCooldown: 60,      // seconds between scale-out actions
  scaleInCooldown: 300,      // slower scale-in to avoid thrashing
  minInstances: 1,
  maxInstances: 20,
};
```

Rules:

- Scale out aggressively, scale in conservatively. Use asymmetric cooldown periods: 60 seconds for scale-out, 300 seconds for scale-in.
- Set a hard upper bound on consumer count. Unbounded scaling shifts the bottleneck to the database or downstream service.
- For Kafka, consumer count cannot exceed partition count. Plan partitions with scaling headroom.

### Circuit Breaker on Consumers

When a consumer depends on a downstream service, apply a circuit breaker. A consumer that retries against a failing service generates backpressure upstream and amplifies the failure.

```typescript
async function consumeWithCircuitBreaker(
  message: MessageEnvelope,
  breaker: CircuitBreaker,
): Promise<void> {
  if (breaker.isOpen()) {
    await nackWithDelay(message, breaker.resetTimeoutMs);
    return;
  }

  try {
    await processMessage(message);
    breaker.recordSuccess();
  } catch (error) {
    breaker.recordFailure();
    if (breaker.isOpen()) {
      logger.warn("circuit breaker opened, pausing consumption", {
        failureCount: breaker.failureCount,
        resetTimeout: breaker.resetTimeoutMs,
      });
    }
    throw error;
  }
}
```

When the circuit opens, nack messages with a delay matching the circuit breaker reset timeout. This prevents messages from accumulating in the consumer's prefetch buffer while the downstream recovers.

## Exactly-Once Processing

True exactly-once delivery does not exist across distributed systems. What you can achieve is effectively-once processing: at-least-once delivery combined with idempotent consumers.

### Idempotent Consumer

Every consumer must be idempotent. Processing the same message twice must produce the same result.

```typescript
async function handlePaymentCreated(
  envelope: MessageEnvelope<PaymentCreatedEvent>,
): Promise<void> {
  const { id: messageId, payload } = envelope;

  // Deduplication check: same transaction as the business write
  await database.transaction(async (tx) => {
    const alreadyProcessed = await tx.processedMessage.findUnique({
      where: { messageId },
    });

    if (alreadyProcessed !== null) {
      logger.info("duplicate message, skipping", { messageId });
      return;
    }

    await tx.payment.create({
      data: {
        id: payload.paymentId,
        amount: payload.amount,
        currency: payload.currency,
        status: "CREATED",
      },
    });

    await tx.processedMessage.create({
      data: {
        messageId,
        processedAt: new Date(),
      },
    });
  });
}
```

Rules:

- The deduplication check and the business write must be in the same transaction. Separate checks create a TOCTOU race.
- The deduplication store must be durable. In-memory sets are lost on restart.
- Set a TTL on the deduplication records. 7 days is a safe default, covering most redelivery windows.

### Transactional Outbox

When a service must write to its database and publish a message atomically, use the transactional outbox pattern. Writing to the database and publishing to the broker in sequence is not atomic: the publish can fail after the write succeeds, or vice versa.

```typescript
// Step 1: write business data + outbox entry in one transaction
await database.transaction(async (tx) => {
  const order = await tx.order.create({
    data: {
      id: orderId,
      customerId: payload.customerId,
      status: "CREATED",
    },
  });

  await tx.outboxMessage.create({
    data: {
      id: generateULID(),
      type: "order.created",
      payload: JSON.stringify(order),
      createdAt: new Date(),
      publishedAt: null,
    },
  });
});

// Step 2: a separate poller/CDC process reads unpublished outbox entries and publishes
async function publishOutbox(): Promise<void> {
  const pending = await database.outboxMessage.findMany({
    where: { publishedAt: null },
    orderBy: { createdAt: "asc" },
    take: 100,
  });

  for (const entry of pending) {
    await broker.publish(entry.type, entry.payload);
    await database.outboxMessage.update({
      where: { id: entry.id },
      data: { publishedAt: new Date() },
    });
  }
}
```

The outbox poller must be idempotent. If it crashes between publishing and marking as published, it will publish again on the next run. The consumer's deduplication handles this.

For high-throughput systems, use change data capture (Debezium, DynamoDB Streams) instead of polling. CDC reads the transaction log directly, eliminating polling delay and reducing database load.

### Consumer Offset Management

For Kafka and similar log-based brokers, commit offsets after processing, not before.

| Strategy | Behavior | Risk |
|----------|----------|------|
| Auto-commit | Offsets committed on a timer, regardless of processing | Message loss: offset committed before processing completes |
| Manual commit after processing | Offset committed only after successful processing | Duplicates on crash: reprocessing from last committed offset |
| Transactional commit | Offset committed in the same transaction as the business write | Effectively-once, requires Kafka transactions |

**Default rule**: disable auto-commit. Commit offsets manually after the business write succeeds. Accept that redelivery on crash is normal and make consumers idempotent.

## Monitoring

### Required Metrics

| Metric | What it measures | Alert threshold |
|--------|-----------------|----------------|
| Queue depth | Messages waiting to be consumed | 10x steady-state for 5+ minutes |
| Consumer lag | Time or offset difference between head and consumer position | Time lag > 5 minutes or offset lag > 10K messages |
| DLQ depth | Messages that failed processing | Any message in DLQ triggers an alert |
| Message age | Time since oldest unconsumed message was published | > 10 minutes for real-time queues, > 1 hour for batch |
| Publish rate | Messages published per second | Drop > 50% from baseline for 5+ minutes |
| Consume rate | Messages consumed per second | Drop > 50% from baseline for 5+ minutes |
| Processing duration (p50, p95, p99) | Time from receive to acknowledge | p99 > visibility timeout means messages will be redelivered |
| Error rate | Failed message processing attempts per second | > 5% of consume rate |

### Alert Priority

| Condition | Priority | Action |
|-----------|----------|--------|
| DLQ depth > 0 | P2 | Investigate within 4 hours. Messages are not being processed |
| DLQ depth growing | P1 | Investigate immediately. Ongoing data loss or processing failure |
| Consumer lag growing for 10+ minutes | P1 | Scale consumers or fix the bottleneck |
| All consumers down | P0 | Immediate action. No messages are being processed |
| Queue depth exceeding retention | P0 | Messages are being dropped. Emergency scale or pause producers |

### Dashboard Layout

Every message queue system must have a dashboard with these panels:

1. Queue depth over time (per queue)
2. Consumer lag over time (per consumer group)
3. Publish rate vs consume rate (shows divergence)
4. Processing duration percentiles
5. Error rate and DLQ depth
6. Consumer instance count (correlate with lag)

## Testing

### Unit Tests: In-Memory Broker

Use an in-memory broker implementation for unit tests. Tests must not depend on a running broker instance.

```typescript
class InMemoryBroker implements MessageBroker {
  private readonly queues = new Map<string, MessageEnvelope[]>();
  private readonly handlers = new Map<string, MessageHandler[]>();

  async publish(topic: string, envelope: MessageEnvelope): Promise<void> {
    const queue = this.queues.get(topic) ?? [];
    this.queues.set(topic, [...queue, envelope]);

    const topicHandlers = this.handlers.get(topic) ?? [];
    for (const handler of topicHandlers) {
      await handler(envelope);
    }
  }

  subscribe(topic: string, handler: MessageHandler): void {
    const topicHandlers = this.handlers.get(topic) ?? [];
    this.handlers.set(topic, [...topicHandlers, handler]);
  }

  getMessages(topic: string): readonly MessageEnvelope[] {
    return this.queues.get(topic) ?? [];
  }

  clear(): void {
    this.queues.clear();
    this.handlers.clear();
  }
}
```

### Integration Tests: Real Broker with Testcontainers

For integration tests, run a real broker via testcontainers. Tests must verify actual broker behavior: acknowledgment, redelivery, DLQ routing.

```typescript
import { GenericContainer, StartedTestContainer } from "testcontainers";

describe("OrderConsumer", () => {
  let container: StartedTestContainer;
  let broker: RabbitMQClient;

  beforeAll(async () => {
    container = await new GenericContainer("rabbitmq:3-management")
      .withExposedPorts(5672)
      .start();

    broker = new RabbitMQClient({
      host: container.getHost(),
      port: container.getMappedPort(5672),
    });
  }, 60_000);

  afterAll(async () => {
    await broker.close();
    await container.stop();
  });

  it("must process order.created and persist to database", async () => {
    // Arrange
    const envelope = createOrderCreatedEnvelope();

    // Act
    await broker.publish("order.created", envelope);
    await waitForConsumption("order.created", envelope.id);

    // Assert
    const order = await database.order.findUnique({
      where: { id: envelope.payload.orderId },
    });
    expect(order).not.toBeNull();
    expect(order!.status).toBe("CREATED");
  });
});
```

### Test Scenarios

| Scenario | What to verify | Type |
|----------|---------------|------|
| Happy path processing | Message consumed, business logic executed, message acknowledged | Integration |
| Duplicate message | Same message ID processed twice, no duplicate side effects | Integration |
| Poison message to DLQ | Invalid message retried N times, then moved to DLQ | Integration |
| Out-of-order delivery | Later event arrives first, consumer handles gracefully | Unit |
| Consumer crash mid-processing | Message redelivered after visibility timeout, no data corruption | Integration |
| DLQ reprocessing | Messages in DLQ replayed to main queue, processed successfully | Integration |
| Batch partial failure | Some messages in batch fail, only failed ones are retried | Integration |
| Schema version mismatch | Consumer receives unknown schema version, routes to DLQ with clear error | Unit |
| Backpressure behavior | Consumer slows down when downstream is degraded | Integration |
| Ordering within key | Messages with same ordering key processed in order | Integration |

### Message Ordering Verification

```typescript
it("must process events for the same order in sequence order", async () => {
  // Arrange
  const orderId = generateULID();
  const events = [
    createEnvelope("order.created", { orderId, sequenceNumber: 1 }),
    createEnvelope("order.confirmed", { orderId, sequenceNumber: 2 }),
    createEnvelope("order.shipped", { orderId, sequenceNumber: 3 }),
  ];

  // Act
  for (const event of events) {
    await broker.publish("order.events", event, { orderingKey: orderId });
  }
  await waitForAllConsumed(events);

  // Assert
  const order = await database.order.findUnique({ where: { id: orderId } });
  expect(order!.status).toBe("SHIPPED");
  expect(order!.lastSequenceNumber).toBe(3);

  const processingLog = await database.processingLog.findMany({
    where: { orderId },
    orderBy: { processedAt: "asc" },
  });
  expect(processingLog.map((l) => l.eventType)).toEqual([
    "order.created",
    "order.confirmed",
    "order.shipped",
  ]);
});
```

## Platform Comparison

### Feature Matrix

| Feature | SQS | RabbitMQ | Kafka | NATS JetStream | Redis Streams |
|---------|-----|----------|-------|----------------|---------------|
| Delivery model | Pull | Push (with pull option) | Pull | Push and pull | Pull |
| Ordering | FIFO queues (per group ID) | Per-queue FIFO | Per-partition FIFO | Per-stream, per-subject | Per-stream FIFO |
| Message retention | Up to 14 days | Until acknowledged | Configurable (days/size), default 7 days | Configurable (time/size/count) | Configurable (maxlen/minid) |
| Consumer groups | Single consumer group per queue | Competing consumers on one queue | Native consumer groups | Durable consumers, queue groups | Native consumer groups (XREADGROUP) |
| DLQ | Native (redrive policy) | Via exchange routing (x-dead-letter-exchange) | No native DLQ, implement with error topic | No native DLQ, implement manually | No native DLQ, implement manually |
| Exactly-once | FIFO deduplication (5-min window) | No native support | Transactional producers and consumers | No native support | No native support |
| Max message size | 256 KB (up to 2 GB via S3 pointer) | No hard limit (128 MB practical) | Default 1 MB (configurable) | Default 1 MB (configurable) | No hard limit |
| Throughput (per partition/queue) | ~3K msg/s standard, ~300 msg/s FIFO | ~20K msg/s | ~100K msg/s per partition | ~50K msg/s | ~100K msg/s |
| Managed offering | AWS SQS | Amazon MQ, CloudAMQP | Amazon MSK, Confluent Cloud | Synadia Cloud | Amazon ElastiCache, Redis Cloud |
| Operational complexity | None (fully managed) | Medium (clustering, shovel, federation) | High (ZooKeeper/KRaft, partitions, ISR) | Low (embedded, simple clustering) | Low (if already running Redis) |
| Replay/rewind | No (message deleted after processing) | No (message deleted after ack) | Yes (offset reset per consumer group) | Yes (consumer can seek by time or sequence) | Yes (read from any ID) |
| Pub/sub | SNS + SQS fan-out | Exchanges (direct, topic, fanout, headers) | Native topics | Native subjects with wildcards | No native pub/sub, use multiple groups |

### Selection Guide

| Scenario | Recommended platform | Rationale |
|----------|---------------------|-----------|
| AWS-native, low ops budget | SQS + SNS | Zero infrastructure management, pay per message |
| Need message replay and event sourcing | Kafka | Log-based retention, consumer offset reset, high throughput |
| Complex routing rules, RPC patterns | RabbitMQ | Flexible exchange types, routing keys, request-reply built-in |
| Lightweight, low latency, request-reply | NATS JetStream | Minimal overhead, built-in request-reply, simple operations |
| Already running Redis, simple queuing needs | Redis Streams | No additional infrastructure, good enough for moderate throughput |
| Multi-region, global ordering | Kafka with MirrorMaker or Confluent Cluster Linking | Cross-region replication with ordering preservation |
| Serverless, event-driven, AWS Lambda | SQS | Native Lambda event source mapping, built-in batch and DLQ support |

## Related Standards

- `standards/event-driven-architecture.md`: Event-Driven Architecture
- `standards/resilience.md`: Resilience
- `standards/distributed-systems.md`: Distributed Systems
