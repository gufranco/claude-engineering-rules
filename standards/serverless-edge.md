# Serverless and Edge Computing

## When to Use Serverless

| Workload characteristic | Serverless fit | Traditional compute fit |
|------------------------|---------------|----------------------|
| Sporadic traffic with idle periods | Yes, pay per invocation | No, idle servers waste money |
| Predictable, sustained high throughput | No, cost scales linearly | Yes, reserved capacity is cheaper |
| Sub-second response time required | Depends on cold start tolerance | Yes, always warm |
| Event-driven processing | Yes, native trigger integration | Possible but more wiring |
| Long-running jobs over 15 minutes | No, timeout limits | Yes |
| Stateful processing | No, functions are ephemeral | Yes |
| Rapid prototyping | Yes, minimal infrastructure | More setup overhead |

## Stateless Design

Functions are ephemeral. Any invocation may run on a fresh instance. Externalize all state.

| State type | Where to store |
|-----------|---------------|
| Session data | Redis, DynamoDB, or managed session store |
| File uploads | Object storage with pre-signed URLs |
| Cache | Redis, Memcached, or edge KV store |
| Configuration | Environment variables or parameter store |
| Queue state | Managed queue service |

Never write to the local filesystem expecting persistence. Never store state in global variables expecting them to survive across invocations.

```typescript
// Wrong: state in global variable
let requestCount = 0;

export async function handler(event: APIGatewayEvent): Promise<Response> {
  requestCount++; // unreliable, resets on cold start
  return { statusCode: 200, body: String(requestCount) };
}

// Correct: state externalized
export async function handler(event: APIGatewayEvent): Promise<Response> {
  const count = await redis.incr("request-count");
  return { statusCode: 200, body: String(count) };
}
```

## Cold Start Optimization

Cold starts add latency when a new function instance initializes. Minimize their impact.

| Technique | Impact | Effort |
|----------|--------|--------|
| Use lightweight runtimes: Go, Rust, or Node.js over JVM | High, 10-50ms vs 500ms+ | Medium |
| Minimize dependencies | High, fewer modules to load | Low |
| Lazy-load heavy dependencies | Medium, defer cost to first use | Low |
| Use provisioned concurrency or function warming | High, eliminates cold starts | Medium cost |
| Keep deployment packages small | Medium, faster download and extraction | Low |
| Use esbuild bundling to tree-shake | Medium, smaller package | Low |

```typescript
// Lazy-load heavy dependencies
let heavyLib: typeof import("heavy-lib") | undefined;

async function getHeavyLib(): Promise<typeof import("heavy-lib")> {
  if (!heavyLib) {
    heavyLib = await import("heavy-lib");
  }
  return heavyLib;
}
```

For latency-critical paths, use provisioned concurrency. For cost-sensitive paths, accept cold starts and optimize their duration.

## Concurrency Limits

Each function invocation consumes a concurrency slot. Uncontrolled concurrency can overwhelm downstream services.

- Set per-function concurrency limits to prevent a single function from consuming the entire account quota.
- Match the limit to what downstream services can handle. 1000 concurrent Lambda invocations hitting a database with 100 max connections will fail.
- Use reserved concurrency for critical functions to guarantee capacity.
- Use throttling and queuing to smooth traffic spikes.

| Downstream resource | Function concurrency limit |
|--------------------|--------------------------|
| Database with 100 connections | 80 concurrent invocations max |
| Third-party API with 50 RPS limit | 50 concurrent invocations max |
| Internal service with auto-scaling | Match the service's scaling speed |

## Infrastructure as Code

Define all serverless resources in code. No manual console configuration.

- Use Terraform, CDK, SAM, or Serverless Framework.
- Include function configuration, triggers, IAM roles, environment variables, and VPC settings.
- Version the IaC with the application code.
- Apply least-privilege IAM policies. A function that reads from S3 does not need S3 write permissions.

## Edge Functions

Run code at CDN edge locations for low-latency operations that do not need a round trip to the origin.

| Use case | Edge function fit |
|----------|------------------|
| Authentication and token validation | Yes, reject unauthorized requests early |
| Geolocation-based routing | Yes, route to nearest region |
| A/B test assignment | Yes, consistent assignment at the edge |
| Request/response header manipulation | Yes, add security headers |
| Full API logic | No, limited runtime and execution time |
| Database queries | No, edge locations lack direct DB access |

Edge function constraints vary by platform:

| Platform | Max execution time | Max memory | Runtime |
|----------|-------------------|-----------|---------|
| Cloudflare Workers | 30s | 128MB | V8 isolates |
| Vercel Edge Functions | 30s | 128MB | V8 isolates |
| AWS CloudFront Functions | 1ms | 2MB | JavaScript only |
| AWS Lambda@Edge | 30s | 128-3008MB | Node.js, Python |

## Timeout Budgets

Set function timeouts with a 20% buffer above the expected maximum execution time.

- Measure actual execution times before setting timeouts.
- Include downstream call latency in the budget. If the function calls an API with a 3-second timeout, the function timeout must be at least 3.6 seconds.
- Set downstream client timeouts shorter than the function timeout. The function must have time to handle a downstream timeout gracefully.
- Alert when execution time exceeds 80% of the timeout.

## Monitoring

| Metric | Target | Alert threshold |
|--------|--------|----------------|
| Invocation error rate | Under 0.1% | Above 0.5% for 5 minutes |
| Cold start rate | Under 5% | Above 10% sustained |
| Duration p99 | Under 80% of timeout | Above 90% of timeout |
| Throttled invocations | 0 | Any throttling |
| Dead letter queue depth | 0 | Above 0 |
| Concurrent executions | Under 80% of limit | Above 90% of limit |

- Use structured logging with request IDs for traceability.
- Correlate function logs with API Gateway or trigger logs.
- Track cost per invocation and per function. Serverless costs can grow unexpectedly with traffic spikes.

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|------------|------------|
| No concurrency limit | Database connection exhaustion | Set limits per function |
| Fat deployment packages | Slow cold starts | Tree-shake, minimize dependencies |
| Synchronous chains of functions | Cascading timeouts, high latency | Use async patterns with queues |
| Logging sensitive data | Privacy and compliance violation | Sanitize before logging |
| Ignoring retry behavior | Duplicate processing | Implement idempotent handlers |
| Hard-coded region | Single point of failure | Multi-region with failover |

## Related Standards

- `standards/api-gateway.md`: API Gateway and BFF
- `standards/observability.md`: Observability
