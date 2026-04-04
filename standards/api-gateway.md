# API Gateway and BFF

## Gateway vs BFF Decision Framework

| Pattern | Purpose | When to use |
|---------|---------|-------------|
| API Gateway | Single entry point for all clients, cross-cutting concerns | Multiple services behind a unified API, consistent auth and rate limiting |
| Backend for Frontend | Client-specific aggregation and transformation | Different frontends need different data shapes or protocols |
| Direct service access | No intermediary | Internal service-to-service communication within a trust boundary |

Use a gateway when multiple services share the same cross-cutting requirements. Add a BFF when a specific frontend needs data aggregation or transformation that does not belong in the gateway or the backend services.

## Cross-Cutting Concerns at the Gateway

The gateway handles concerns that apply to all requests regardless of the destination service. Implement once at the gateway, not in every service.

| Concern | Gateway responsibility |
|---------|----------------------|
| Authentication | Validate tokens, reject unauthenticated requests |
| Rate limiting | Enforce per-client and per-endpoint limits |
| Request routing | Route to the correct backend service |
| Request logging | Log request metadata for observability |
| TLS termination | Handle HTTPS, forward plaintext to internal services |
| Request ID injection | Add a unique request ID to every request for tracing |
| CORS handling | Centralized CORS policy enforcement |
| Response compression | gzip/brotli compression for responses |

```yaml
# Example: Kong gateway configuration
services:
  - name: user-service
    url: http://user-service:3000
    routes:
      - paths: ["/api/users"]
    plugins:
      - name: rate-limiting
        config:
          minute: 60
          policy: redis
      - name: jwt
        config:
          claims_to_verify: ["exp"]
      - name: correlation-id
        config:
          header_name: X-Request-ID
          generator: uuid
```

## Protocol Translation

The gateway translates between client-facing and internal protocols.

| External protocol | Internal protocol | Gateway action |
|------------------|------------------|----------------|
| REST over HTTPS | gRPC | Transcode JSON to protobuf, route to gRPC service |
| REST over HTTPS | GraphQL | Forward to GraphQL service or act as GraphQL gateway |
| WebSocket | Internal event stream | Upgrade connection, bridge to message broker |
| REST over HTTPS | REST over HTTP | TLS termination, forward plaintext internally |

Keep protocol translation logic in the gateway configuration, not in custom code. Most gateway platforms support transcoding natively.

## Service Discovery Integration

The gateway must resolve backend service locations dynamically. Hard-coded service URLs break when services scale or redeploy.

| Discovery method | How it works | Best for |
|-----------------|-------------|----------|
| DNS-based | Services register DNS entries, gateway resolves | Kubernetes, simple setups |
| Registry-based | Services register with Consul, Eureka, or etcd | Multi-environment, advanced routing |
| Config-driven | Service URLs in gateway config, reloaded on change | Small deployments, managed services |

- Health check backend services. Remove unhealthy instances from the routing pool.
- Use weighted routing for canary deployments through the gateway.

## Circuit Breaking at Gateway Level

The gateway must protect the system when a backend service degrades. Without circuit breaking, a slow service cascades failures to all clients.

| Circuit state | Behavior |
|-------------|----------|
| Closed | Requests pass through normally |
| Open | Requests fail immediately with 503, no backend call |
| Half-open | A small number of probe requests test if the service recovered |

```yaml
# Example: circuit breaker configuration
circuit_breaker:
  failure_threshold: 5
  success_threshold: 3
  timeout: 30s
  failure_status_codes: [500, 502, 503, 504]
```

- Set circuit breaker parameters per backend service. A critical payment service has tighter thresholds than a recommendation service.
- Return a meaningful 503 response when the circuit is open. Include a `Retry-After` header.
- Log circuit state changes for operational awareness.

## Backend for Frontend

A BFF is a server-side component tailored to a specific frontend. It aggregates data from multiple services and transforms it into the shape the frontend needs.

### When to add a BFF

- The frontend needs data from 3+ services combined in one response.
- Different frontends need different data shapes for the same domain entity.
- The frontend cannot store secrets safely, such as web browsers and mobile apps.
- Response transformation is too complex for the gateway.

### BFF boundaries

| BFF does | BFF does not |
|----------|-------------|
| Aggregate responses from multiple services | Contain business logic |
| Transform data shapes for the frontend | Validate business rules |
| Hold client secrets like API keys and service tokens | Own any database tables |
| Cache responses for frontend performance | Process background jobs |
| Handle frontend-specific error formatting | Enforce domain invariants |

```typescript
// BFF endpoint: aggregate order details for mobile
async function getOrderDetails(orderId: string): Promise<MobileOrderView> {
  const [order, payment, shipping] = await Promise.all([
    orderService.getOrder(orderId),
    paymentService.getPayment(orderId),
    shippingService.getTracking(orderId),
  ]);

  return {
    id: order.id,
    status: order.status,
    total: formatCurrency(payment.amount, payment.currency),
    trackingUrl: shipping.trackingUrl,
    estimatedDelivery: formatDate(shipping.estimatedDelivery),
  };
}
```

### BFF per platform

Each frontend platform gets its own BFF when their needs diverge significantly.

| Platform | BFF responsibility |
|----------|-------------------|
| Web | Server-side rendering support, session management, CSRF tokens |
| Mobile | Payload size optimization, offline-first data structures |
| Third-party API | Stable versioned contract, rate limiting, API key management |

A shared BFF defeats the purpose. If two frontends share the same BFF, the BFF becomes a general-purpose API layer with no client-specific optimization.

### BFF holds secrets

Frontends running in browsers and mobile devices cannot store secrets securely. The BFF acts as a confidential client.

- API keys for third-party services live in the BFF, never in frontend code.
- OAuth client secrets live in the BFF.
- The BFF exchanges the frontend's session token for backend service tokens.
- The frontend communicates with the BFF only, never directly with backend services that require secrets.

## No Business Logic in BFF

The BFF is a thin orchestration and transformation layer. All business rules live in backend services.

| Acceptable in BFF | Not acceptable in BFF |
|-------------------|----------------------|
| `if (platform === 'mobile') return compactView` | `if (order.total > 100) applyDiscount()` |
| Merge responses from two services | Calculate shipping cost |
| Format dates for the client's locale | Validate business rules |
| Cache aggregated responses | Write to a database |

If the BFF grows beyond data aggregation and formatting, business logic is leaking into it. Move that logic to the appropriate backend service.

## Gateway Selection Criteria

| Criterion | What to evaluate |
|----------|-----------------|
| Protocol support | HTTP/1.1, HTTP/2, gRPC, WebSocket |
| Plugin ecosystem | Auth, rate limiting, transformation, observability |
| Performance | Latency overhead per request, throughput under load |
| Deployment model | Self-hosted, managed, sidecar |
| Configuration | Declarative config, API-driven, GitOps-friendly |
| Observability | Built-in metrics, tracing integration, access logging |

Common options: Kong, Envoy, AWS API Gateway, Traefik, NGINX. Evaluate against the project's specific needs rather than defaulting to the most popular option.
