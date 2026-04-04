# WebSocket and Real-Time Communication

## When to Use What

| Technology | Use when | Avoid when |
|------------|----------|------------|
| WebSocket | Bidirectional, low-latency messaging: chat, multiplayer, collaborative editing, live dashboards with user interaction | Server-to-client-only updates, browser support constraints |
| Server-Sent Events (SSE) | Server-to-client-only streams: notifications, activity feeds, progress updates, live logs | Client must send frequent messages back to server |
| HTTP polling | Update frequency is low (> 30s), infrastructure does not support persistent connections | Sub-second latency required |
| HTTP long polling | Real-time needed but WebSocket/SSE are blocked by infrastructure | High connection count, resource-constrained servers |

**Default rule**: use SSE for server-to-client streams. Use WebSocket only when bidirectional messaging is required. WebSocket adds connection management complexity that SSE avoids.

## Connection Lifecycle

### Handshake and Authentication

Authenticate during the HTTP upgrade request, not after the WebSocket connection is open. The upgrade is the only point where standard HTTP middleware (cookies, headers, tokens) is available.

```typescript
import { IncomingMessage } from "node:http";
import { WebSocketServer } from "ws";

const wss = new WebSocketServer({ noServer: true });

server.on("upgrade", (request: IncomingMessage, socket, head) => {
  const token = extractToken(request);
  const user = verifyToken(token);

  if (!user) {
    socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
    socket.destroy();
    return;
  }

  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit("connection", ws, request, user);
  });
});
```

Rules:

- Reject unauthenticated upgrades with HTTP 401 before completing the handshake
- Never send credentials in a WebSocket text frame after connection. The upgrade request is the auth boundary
- Store the authenticated user identity on the connection object for the connection's lifetime
- Set a connection timeout of 5 seconds for the handshake phase. Connections that do not complete authentication within that window must be terminated

### Heartbeat

Dead connections consume server resources without producing errors. TCP keepalive alone is insufficient because intermediate proxies and load balancers may hold the TCP connection open after the remote peer is gone.

```typescript
const HEARTBEAT_INTERVAL_MS = 30_000;
const PONG_TIMEOUT_MS = 10_000;

wss.on("connection", (ws) => {
  let isAlive = true;

  ws.on("pong", () => {
    isAlive = true;
  });

  const interval = setInterval(() => {
    if (!isAlive) {
      ws.terminate();
      return;
    }
    isAlive = false;
    ws.ping();
  }, HEARTBEAT_INTERVAL_MS);

  ws.on("close", () => {
    clearInterval(interval);
  });
});
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Ping interval | 30 seconds | Balances detection speed with overhead |
| Pong timeout | 10 seconds | Allows for temporary network delays |
| Max missed pongs | 1 | Terminate immediately on first missed pong |

### Graceful Close

- The server must send a close frame with a status code before terminating
- Wait up to 5 seconds for the client's close frame response before forcing termination
- Clean up all resources associated with the connection: timers, subscriptions, room memberships

| Close code | Meaning | Who sends |
|------------|---------|-----------|
| 1000 | Normal closure | Either side |
| 1001 | Going away (server shutdown, page navigation) | Either side |
| 1008 | Policy violation (auth failure, rate limit) | Server |
| 1011 | Unexpected server error | Server |
| 4000-4999 | Application-specific codes | Either side |

Define application-specific close codes in the 4000-4999 range. Document each code and its meaning in a shared enum.

```typescript
const enum CloseCode {
  TokenExpired = 4001,
  RateLimited = 4002,
  DuplicateConnection = 4003,
  MaintenanceMode = 4004,
}
```

### Abnormal Close Handling

- Detect abnormal closures via the `close` event with `wasClean === false`
- Log every abnormal closure with: user ID, connection duration, last message timestamp, and close code if available
- Trigger cleanup as if the connection was closed normally. Never leave orphaned subscriptions or room memberships

## Reconnection

### Exponential Backoff with Jitter

Clients must reconnect automatically on abnormal closure. Use exponential backoff with full jitter to prevent thundering herd when a server restarts.

```typescript
interface ReconnectConfig {
  readonly baseDelayMs: number;
  readonly maxDelayMs: number;
  readonly maxRetries: number;
}

const DEFAULT_RECONNECT: ReconnectConfig = {
  baseDelayMs: 500,
  maxDelayMs: 30_000,
  maxRetries: 10,
};

function calculateDelay(attempt: number, config: ReconnectConfig): number {
  const exponentialDelay = config.baseDelayMs * Math.pow(2, attempt);
  const cappedDelay = Math.min(exponentialDelay, config.maxDelayMs);
  return Math.random() * cappedDelay; // Full jitter
}
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Base delay | 500ms | Fast first reconnect for transient failures |
| Max delay | 30 seconds | Upper bound prevents excessive wait |
| Max retries | 10 | Total window of ~5 minutes before giving up |
| Jitter | Full (0 to computed delay) | Spreads reconnections after server restart |

After exhausting retries, notify the user that the connection is lost and provide a manual reconnect action.

### State Reconciliation

After a successful reconnect, the client must reconcile state to fill any gaps from the disconnection period.

1. Record the timestamp or sequence number of the last received message before disconnect
2. On reconnect, request missed messages: `{ type: "sync", lastSequence: 1042 }`
3. The server must keep a bounded message buffer per channel. Buffer size: 1000 messages or 5 minutes of history, whichever is smaller
4. If the gap exceeds the buffer, respond with a full state snapshot instead of individual messages
5. Apply missed messages in order before resuming the live stream

```typescript
interface SyncRequest {
  readonly type: "sync";
  readonly lastSequence: number;
  readonly channels: readonly string[];
}

interface SyncResponse {
  readonly type: "sync_response";
  readonly strategy: "incremental" | "snapshot";
  readonly messages?: readonly ServerMessage[];
  readonly snapshot?: ChannelState;
}
```

### Offline Queue

Client-side sends that occur while disconnected must be queued and replayed after reconnection.

- Queue in memory with a max size of 100 messages. Drop oldest when full
- Each queued message must carry its original timestamp and an idempotency key
- On reconnect, flush the queue in FIFO order after state reconciliation completes
- Do not queue messages that are time-sensitive and meaningless after a delay, like typing indicators

## Message Protocol

### Envelope Format

Every WebSocket message must use a consistent envelope. No bare payloads.

```typescript
interface ClientMessage {
  readonly type: string;
  readonly id: string;        // Client-generated UUID for correlation
  readonly timestamp: number; // Unix milliseconds
  readonly payload: unknown;
}

interface ServerMessage {
  readonly type: string;
  readonly id: string;        // Server-generated message ID
  readonly ref?: string;      // Client message ID this is a response to
  readonly sequence: number;  // Per-channel monotonic sequence number
  readonly timestamp: number;
  readonly payload: unknown;
}
```

Rules:

- Every message must have a `type` field. This is the routing key for handlers
- Every client message must have an `id` for request-response correlation
- Server responses to client requests must include `ref` pointing to the client `id`
- The `sequence` field is mandatory on all server-originated messages within a channel. It enables gap detection and ordering

### Request-Response Correlation

WebSocket is asynchronous, but many operations need a request-response pattern. Use the `id`/`ref` pair for correlation.

```typescript
function sendAndWait(
  ws: WebSocket,
  message: ClientMessage,
  timeoutMs: number = 5_000,
): Promise<ServerMessage> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error(`Timeout waiting for response to ${message.id}`));
    }, timeoutMs);

    function handler(event: MessageEvent): void {
      const response: ServerMessage = JSON.parse(event.data as string);
      if (response.ref === message.id) {
        cleanup();
        resolve(response);
      }
    }

    function cleanup(): void {
      clearTimeout(timer);
      ws.removeEventListener("message", handler);
    }

    ws.addEventListener("message", handler);
    ws.send(JSON.stringify(message));
  });
}
```

- Set a response timeout of 5 seconds for request-response pairs. Treat timeouts as errors
- The server must respond to every client request, even if the response is an error

### Binary vs Text Frames

| Frame type | Use when | Format |
|------------|----------|--------|
| Text (opcode 0x1) | Structured data: commands, state updates, chat messages | JSON |
| Binary (opcode 0x2) | Large payloads, media, files, performance-critical data | MessagePack, Protobuf, or raw bytes |

**Default rule**: use text frames with JSON. Switch to binary only when profiling shows JSON serialization or payload size is a bottleneck. Binary adds complexity to debugging and logging.

## Backpressure

### Server-Side Send Buffer

When the server produces messages faster than a client can consume them, the send buffer grows and eventually exhausts memory.

```typescript
const MAX_BUFFERED_AMOUNT = 1_048_576; // 1 MB

function safeSend(ws: WebSocket, data: string): boolean {
  if (ws.bufferedAmount > MAX_BUFFERED_AMOUNT) {
    return false; // Client is a slow consumer
  }
  ws.send(data);
  return true;
}
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max send buffer per connection | 1 MB | Prevents OOM from a single slow client |
| Slow consumer check interval | 5 seconds | Aligned with heartbeat sub-interval |
| Grace period before disconnect | 30 seconds | Allow temporary slowdowns to recover |

### Slow Consumer Detection

A slow consumer is a connection whose `bufferedAmount` exceeds the threshold for longer than the grace period.

| Strategy | Behavior | Use when |
|----------|----------|----------|
| Drop oldest | Discard messages that were buffered before the threshold breach | Live data where only the latest state matters: stock tickers, sensor readings |
| Drop newest | Stop enqueuing new messages until the buffer drains | Ordered streams where gaps are worse than delay |
| Disconnect | Terminate the connection, let the client reconnect and resync | The client is unrecoverably slow or has silently died |
| Downgrade | Switch from full updates to periodic snapshots at a lower frequency | Dashboard clients that can tolerate reduced granularity |

**Default rule**: for most applications, use drop-oldest for live data channels and disconnect for ordered channels. Always log when messages are dropped, with the connection ID, channel, and drop count.

### Flow Control Signals

When the server detects a slow consumer, it must inform the client before taking action:

```typescript
interface FlowControlMessage {
  readonly type: "flow_control";
  readonly status: "throttled" | "resumed";
  readonly reason: string;
  readonly droppedCount: number;
}
```

## Scaling

### Sticky Sessions vs Stateless

| Approach | Pros | Cons |
|----------|------|------|
| Sticky sessions | Simple, connection state stays on one server | Uneven load distribution, failover loses all connections |
| Stateless with pub/sub backend | Even distribution, zero-downtime deploys, any server can handle any connection | Requires external message bus, adds latency |

**Default rule**: use stateless design with a pub/sub backend. Sticky sessions create operational problems at scale that outweigh the implementation simplicity.

### Pub/Sub Backend

Every WebSocket server instance subscribes to a shared message bus. When a message must reach connections on other servers, it goes through the bus.

| Backend | Throughput | Persistence | Use when |
|---------|-----------|-------------|----------|
| Redis Pub/Sub | ~500K msg/s per node | None (fire and forget) | Low-to-medium scale, Redis already in stack |
| Redis Streams | ~200K msg/s per node | Durable with consumer groups | Need message replay after server restart |
| NATS | ~10M msg/s per node | JetStream for durability | High throughput, low latency requirements |
| Kafka | ~1M msg/s per partition | Durable by default | High volume with ordering guarantees and audit trails |

```typescript
import { createClient } from "redis";

const subscriber = createClient();
const publisher = createClient();

// Server A: subscribe to channel updates
await subscriber.subscribe("chat:room:42", (message) => {
  const parsed: ServerMessage = JSON.parse(message);
  broadcastToLocalConnections("room:42", parsed);
});

// Server B: publish to channel
async function publishToChannel(
  channel: string,
  message: ServerMessage,
): Promise<void> {
  await publisher.publish(channel, JSON.stringify(message));
}
```

### Room and Channel Management

- Store room memberships in the pub/sub backend, not in server-local memory. Any server must be able to answer "who is in this room?"
- Limit room membership to 10,000 connections per room. Beyond that, partition into sub-rooms with a fan-out relay
- Clean up empty rooms automatically after 60 seconds of inactivity
- Broadcast connection count changes as a control message so clients can display presence

## Message Ordering

### Per-Channel Sequence Numbers

The server must assign a monotonically increasing sequence number to every message within a channel. Sequence numbers are per-channel, not global.

```typescript
// Server-side: atomic increment per channel
async function nextSequence(channelId: string): Promise<number> {
  return await redis.incr(`seq:${channelId}`);
}
```

Rules:

- Sequence numbers start at 1 for each channel
- Gaps in sequence numbers must never occur during normal operation. Gaps signal message loss
- The server must never reorder messages within a channel. If multiple sources produce messages for the same channel, serialize through a single writer or use the pub/sub backend's ordering guarantees

### Client-Side Gap Detection

The client must track the last received sequence number per channel and detect gaps.

```typescript
const lastSequence = new Map<string, number>();

function onMessage(channel: string, message: ServerMessage): void {
  const expected = (lastSequence.get(channel) ?? 0) + 1;

  if (message.sequence > expected) {
    requestMissedMessages(channel, expected, message.sequence - 1);
    bufferUntilGapFilled(channel, message);
    return;
  }

  if (message.sequence < expected) {
    // Duplicate or out-of-order, discard
    return;
  }

  lastSequence.set(channel, message.sequence);
  processMessage(channel, message);
}
```

| Situation | Client action |
|-----------|---------------|
| `received.sequence === expected` | Process normally, advance expected |
| `received.sequence > expected` | Buffer the message, request the gap fill from server |
| `received.sequence < expected` | Discard as duplicate |

### Out-of-Order Handling

When the client receives a message ahead of sequence, it must buffer and request the gap. The buffer must have a max size of 500 messages and a max age of 10 seconds. If the gap is not filled within those bounds, request a full state snapshot.

## Duplicate Detection

### Idempotency Keys

Every client message must include a unique `id` field that serves as an idempotency key. The server must deduplicate by this key before processing.

```typescript
const processedIds = new Map<string, number>(); // id -> timestamp

function isDuplicate(messageId: string): boolean {
  if (processedIds.has(messageId)) {
    return true;
  }
  processedIds.set(messageId, Date.now());
  return false;
}
```

### Server-Side Deduplication

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Dedup window TTL | 5 minutes | Must exceed max reconnect + queue flush time |
| Storage | Redis with TTL or in-memory with eviction | In-memory is acceptable for single-server, Redis for multi-server |
| Key format | `dedup:{channelId}:{messageId}` | Scoped per channel to reduce key space |

- Use Redis `SET ... NX EX 300` for atomic dedup check + insert with TTL
- Evict expired entries every 60 seconds if using in-memory storage
- Log every deduplicated message at debug level with: channel, message ID, original receive time

### Client-Side Deduplication

The client must also deduplicate based on server message `id` and `sequence`. The sequence-based check from the ordering section covers most cases. An additional `id`-based check catches edge cases where the server replays messages during reconnect sync that the client already received.

- Maintain a set of the last 1000 received message IDs per channel
- Evict entries older than 5 minutes

## Security

### Origin Validation

The server must validate the `Origin` header during the HTTP upgrade.

```typescript
const ALLOWED_ORIGINS = new Set([
  "https://app.example.com",
  "https://staging.example.com",
]);

server.on("upgrade", (request, socket, head) => {
  const origin = request.headers.origin;

  if (!origin || !ALLOWED_ORIGINS.has(origin)) {
    socket.write("HTTP/1.1 403 Forbidden\r\n\r\n");
    socket.destroy();
    return;
  }

  // Proceed with auth and upgrade
});
```

### Rate Limiting

Apply rate limits per connection and per authenticated user.

| Limit | Value | Action on breach |
|-------|-------|------------------|
| Messages per second per connection | 20 | Reject with error frame, log |
| Messages per second per user (across connections) | 50 | Reject, send flow control warning |
| Connections per user | 5 | Reject new connection with close code 4003 |
| Connection attempts per IP per minute | 30 | Reject upgrade with HTTP 429 |

- Use a sliding window counter, not a fixed window. Fixed windows allow bursts at the window boundary
- Send a warning message at 80% of the limit before hard rejecting at 100%

### Message Size Limits

| Limit | Value | Action on breach |
|-------|-------|------------------|
| Max message size (text) | 64 KB | Close connection with code 1009 |
| Max message size (binary) | 1 MB | Close connection with code 1009 |
| Max messages per batch | 10 | Reject batch, send error |

Configure `maxPayload` on the WebSocket server. Do not rely on application-level checks alone.

```typescript
const wss = new WebSocketServer({
  noServer: true,
  maxPayload: 1_048_576, // 1 MB
});
```

### Token Refresh Over Existing Connection

Tokens expire. The client must refresh the auth token without dropping the connection.

```typescript
// Client sends a re-auth message before the token expires
interface ReauthMessage {
  readonly type: "reauth";
  readonly id: string;
  readonly timestamp: number;
  readonly payload: {
    readonly token: string;
  };
}

// Server validates and updates the connection's auth context
interface ReauthResponse {
  readonly type: "reauth_response";
  readonly ref: string;
  readonly timestamp: number;
  readonly payload: {
    readonly success: boolean;
    readonly expiresAt: number; // Unix ms, so client knows when to refresh again
  };
}
```

Rules:

- The client must initiate re-auth at least 60 seconds before token expiration
- If re-auth fails, close the connection with code 4001 (TokenExpired) and trigger reconnect with a fresh token
- During re-auth, continue processing messages normally. Do not pause the connection
- The server must reject all messages from a connection whose token has expired and not been refreshed

## Server-Sent Events

### When SSE Is Preferable

SSE is the right choice when:

- Communication is server-to-client only
- You need automatic reconnection built into the browser (SSE handles this natively)
- You need to work through HTTP/2 without special infrastructure (SSE multiplexes over a single TCP connection)
- Clients are behind corporate proxies that block WebSocket upgrades

SSE is wrong when:

- The client must send frequent messages to the server (use WebSocket)
- Binary data transfer is required (SSE is text-only)
- You need sub-10ms latency (SSE adds HTTP framing overhead)

### Implementation

```typescript
import { IncomingMessage, ServerResponse } from "node:http";

function handleSSE(req: IncomingMessage, res: ServerResponse): void {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no", // Disable nginx buffering
  });

  // Send a comment every 15 seconds to keep the connection alive
  const keepalive = setInterval(() => {
    res.write(": keepalive\n\n");
  }, 15_000);

  function send(event: string, data: unknown, id?: string): void {
    if (id) {
      res.write(`id: ${id}\n`);
    }
    res.write(`event: ${event}\n`);
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  }

  req.on("close", () => {
    clearInterval(keepalive);
    // Clean up subscriptions
  });
}
```

### Reconnection with Last-Event-ID

SSE has built-in reconnection. The browser sends a `Last-Event-ID` header on reconnect, enabling the server to resume from where the client left off.

```typescript
function handleSSE(req: IncomingMessage, res: ServerResponse): void {
  const lastEventId = req.headers["last-event-id"];

  if (lastEventId) {
    const missedMessages = getMissedMessages(lastEventId);
    for (const msg of missedMessages) {
      send(msg.event, msg.data, msg.id);
    }
  }

  // Subscribe to live updates
}
```

Rules:

- Every SSE event must include an `id` field. Without it, reconnection cannot resume from the correct position
- Set the `retry` field to control the client's reconnection delay: `retry: 3000\n` for 3 seconds
- The server must maintain a message buffer for at least 5 minutes to serve reconnecting clients
- Use a monotonically increasing ID, not a random ID. The server must be able to query "all messages after ID X"

## Testing

### Connection Lifecycle Tests

| Scenario | What to verify |
|----------|----------------|
| Successful handshake | Server accepts valid token, connection opens, server assigns user context |
| Rejected handshake | Invalid token returns 401, socket is destroyed, no WebSocket connection is created |
| Expired token during session | Server sends close code 4001, client initiates reconnect with fresh token |
| Server-initiated close | Client receives close frame with correct code, cleanup executes |
| Client-initiated close | Server receives close frame, cleans up resources within 5 seconds |
| Heartbeat timeout | Server terminates connection after one missed pong, client reconnects |

```typescript
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { WebSocket } from "ws";

describe("connection lifecycle", () => {
  it("must reject connection with invalid token", async () => {
    // Arrange
    const ws = new WebSocket("ws://localhost:3000", {
      headers: { Authorization: "Bearer invalid-token" },
    });

    // Act
    const closeEvent = await new Promise<CloseEvent>((resolve) => {
      ws.on("error", () => {});
      ws.on("close", (code, reason) => {
        resolve({ code, reason: reason.toString() });
      });
    });

    // Assert
    expect(closeEvent.code).toBe(1006); // Abnormal closure (upgrade rejected)
  });
});
```

### Reconnection Behavior Tests

| Scenario | What to verify |
|----------|----------------|
| Server restart | Client reconnects with backoff, state reconciliation fetches missed messages |
| Network interruption | Client detects via missed pong, reconnects, offline queue flushes |
| Max retries exhausted | Client stops reconnecting, notifies the user, provides manual reconnect |
| Rapid disconnect/reconnect | Backoff increases correctly, no thundering herd |
| Reconnect with stale token | Client refreshes token before reconnecting |

### Message Ordering Verification

```typescript
it("must deliver messages in sequence order", async () => {
  // Arrange
  const received: number[] = [];
  const messageCount = 100;

  client.on("message", (data: string) => {
    const msg: ServerMessage = JSON.parse(data);
    received.push(msg.sequence);
  });

  // Act
  for (let i = 0; i < messageCount; i++) {
    await publishToChannel("test-channel", {
      type: "test",
      payload: { index: i },
    });
  }
  await waitForMessages(client, messageCount);

  // Assert
  const expected = Array.from({ length: messageCount }, (_, i) => i + 1);
  expect(received).toEqual(expected);
});
```

### Load Testing

Test concurrent connections to find the server's capacity ceiling before production.

| Metric | Target | Tool |
|--------|--------|------|
| Max concurrent connections | Measure, do not guess | k6, Artillery, or custom script |
| Message throughput (msg/s) | Measure at 50%, 80%, and 100% of connection capacity | k6 WebSocket protocol |
| Reconnection storm recovery | All clients reconnected within 60 seconds of server restart | Custom scenario |
| Memory per connection | Under 50 KB idle, under 200 KB active | Server-side profiling |
| Latency p50/p95/p99 | p50 < 5ms, p95 < 20ms, p99 < 100ms for intra-datacenter | k6 with histogram output |

Run load tests against a single server instance first to establish a baseline. Then test with the full horizontally-scaled setup including the pub/sub backend.

```typescript
// k6 WebSocket load test
import ws from "k6/ws";
import { check } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 1000 },
    { duration: "2m", target: 5000 },
    { duration: "30s", target: 0 },
  ],
};

export default function (): void {
  const url = "ws://localhost:3000";
  const params = { headers: { Authorization: `Bearer ${__ENV.TOKEN}` } };

  const res = ws.connect(url, params, (socket) => {
    socket.on("open", () => {
      socket.send(JSON.stringify({ type: "subscribe", id: crypto.randomUUID(), payload: { channel: "load-test" } }));
    });

    socket.on("message", (data) => {
      const msg = JSON.parse(data);
      check(msg, {
        "has sequence": (m) => typeof m.sequence === "number",
        "has type": (m) => typeof m.type === "string",
      });
    });

    socket.setTimeout(() => {
      socket.close();
    }, 120_000);
  });

  check(res, { "status is 101": (r) => r && r.status === 101 });
}
```

## Related Standards

- `standards/resilience.md`: Resilience
- `standards/api-design.md`: API Design
- `standards/distributed-systems.md`: Distributed Systems
