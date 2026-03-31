# gRPC Services

## When to Use gRPC

Use gRPC for internal service-to-service communication where performance, type safety, and streaming matter. Use REST/HTTP for public-facing APIs consumed by browsers or third-party clients.

| Use case | Protocol |
|----------|----------|
| Internal microservice calls | gRPC |
| Public API for web/mobile clients | REST |
| Real-time streaming between services | gRPC bidirectional streaming |
| Browser clients needing real-time | gRPC-Web with an Envoy proxy, or SSE/WebSocket |

## Proto File Design

- One `.proto` file per service. Co-locate with the service that owns the definition
- Version the package: `package myapp.orders.v1;`
- Use `google.protobuf.Timestamp` for dates, not strings or integers
- Use `google.protobuf.FieldMask` for partial updates
- Use wrapper types (`google.protobuf.StringValue`) when you need to distinguish between "not set" and "empty"
- Field numbers are permanent. Never reuse a deleted field number. Reserve removed fields: `reserved 5, 6;`

## Service Definition

```protobuf
syntax = "proto3";
package myapp.orders.v1;

service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (CreateOrderResponse);
  rpc GetOrder(GetOrderRequest) returns (Order);
  rpc ListOrders(ListOrdersRequest) returns (ListOrdersResponse);
  rpc WatchOrderStatus(WatchOrderStatusRequest) returns (stream OrderStatusUpdate);
}
```

Rules:
- One RPC per operation. Do not combine create and update into a single RPC with conditional logic
- Request and response messages are unique per RPC. Do not reuse `Order` as both `GetOrderResponse` and `CreateOrderResponse`
- Use server streaming for subscriptions and real-time updates
- Use client streaming for large uploads or batch operations
- Use bidirectional streaming sparingly. It adds significant complexity to error handling and flow control

## Error Handling

gRPC uses status codes, not HTTP status codes.

| gRPC Code | Meaning | REST equivalent |
|-----------|---------|-----------------|
| OK | Success | 200 |
| INVALID_ARGUMENT | Client sent bad data | 400 |
| NOT_FOUND | Resource does not exist | 404 |
| ALREADY_EXISTS | Duplicate creation | 409 |
| PERMISSION_DENIED | Auth passed but not authorized | 403 |
| UNAUTHENTICATED | Missing or invalid credentials | 401 |
| RESOURCE_EXHAUSTED | Rate limited or quota exceeded | 429 |
| INTERNAL | Server bug | 500 |
| UNAVAILABLE | Transient failure, retry | 503 |
| DEADLINE_EXCEEDED | Timeout | 504 |

- Always set a meaningful status message. "INTERNAL" alone is useless for debugging
- Use `google.rpc.Status` with detail messages for structured error data
- Classify errors for retry: UNAVAILABLE and DEADLINE_EXCEEDED are retryable. INVALID_ARGUMENT is permanent

## Deadlines and Timeouts

Every gRPC call must have a deadline. Without one, a hung server blocks the client indefinitely.

- Set deadlines on every client call. Never rely on the default (no deadline)
- Propagate deadlines across service boundaries. If Service A calls Service B with a 5s deadline and spends 2s on preprocessing, Service B gets at most 3s
- Check `context.Err()` (Go) or `ServerCallContext.CancellationToken` (.NET) before starting expensive work. If the deadline already passed, fail fast

## Interceptors

gRPC interceptors are middleware for cross-cutting concerns.

| Concern | Implementation |
|---------|---------------|
| Logging | Log request/response metadata, duration, status code |
| Authentication | Validate tokens from metadata, reject UNAUTHENTICATED |
| Rate limiting | Count per-client requests, reject RESOURCE_EXHAUSTED |
| Metrics | Record latency histograms, error rates per RPC |
| Retries | Client-side interceptor with backoff for UNAVAILABLE |

Chain interceptors in a consistent order: auth before rate limiting before logging.

## Health Checking

Use the standard gRPC health checking protocol (`grpc.health.v1.Health`).

- Implement the `Check` and `Watch` RPCs
- Return SERVING when the service is ready, NOT_SERVING during graceful shutdown
- Kubernetes readiness probes can use `grpc_health_probe` or native gRPC health check support

## Reflection

Enable server reflection in development and staging. It allows tools like `grpcurl` and `grpcui` to discover services without `.proto` files. Disable in production to reduce attack surface.

## Load Balancing

gRPC uses HTTP/2 with long-lived connections. L4 load balancers send all requests on one connection to one backend.

| Strategy | When to use |
|----------|-------------|
| Client-side (round-robin) | Default for internal services. gRPC clients support this natively |
| Lookaside (xDS, service mesh) | When you need weighted routing, circuit breaking, or observability |
| L7 proxy (Envoy, linkerd) | When clients cannot do client-side balancing (browser, legacy) |

Never use L4 load balancers alone for gRPC. All traffic goes to one backend.
