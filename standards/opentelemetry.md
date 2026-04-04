# OpenTelemetry

## SDK Initialization Order

Initialize the OpenTelemetry SDK before importing any instrumented library. Auto-instrumentation patches library prototypes at import time. If the library is imported first, the patches miss it.

```typescript
// instrumentation.ts - must be the first import in the application entry point
import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-grpc";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-grpc";

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter(),
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();

// main.ts
import "./instrumentation"; // MUST be first
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";
```

In Node.js, use the `--require` or `--import` flag to guarantee initialization order:

```bash
node --import ./instrumentation.ts dist/main.js
```

## Semantic Convention Attribute Naming

Use OpenTelemetry semantic conventions for all attributes. Custom attributes use the `app.` prefix.

| Category | Attribute examples |
|----------|-------------------|
| HTTP | `http.method`, `http.status_code`, `http.route`, `url.full` |
| Database | `db.system`, `db.name`, `db.operation`, `db.statement` |
| Messaging | `messaging.system`, `messaging.operation`, `messaging.destination.name` |
| RPC | `rpc.system`, `rpc.method`, `rpc.service` |
| Custom | `app.user_id`, `app.tenant_id`, `app.feature_flag` |

- All attribute names use `snake_case`, not `camelCase`.
- Check the semantic conventions registry before inventing a new attribute name. If a convention exists, use it.
- Never put user-supplied values like usernames, emails, or free-text inputs in attribute names. They go in attribute values.

## Composite Sampling

Capture 100% of error traces and a configurable percentage of normal traces.

```typescript
class ErrorAwareSampler implements Sampler {
  private readonly ratioSampler = new TraceIdRatioBasedSampler(0.05);

  shouldSample(
    context: Context, traceId: string, spanName: string,
    spanKind: SpanKind, attributes: Attributes,
  ): SamplingResult {
    if (attributes["error"] === true) {
      return { decision: SamplingDecision.RECORD_AND_SAMPLED };
    }
    return this.ratioSampler.shouldSample(
      context, traceId, spanName, spanKind, attributes,
    );
  }
}

const sampler = new ParentBasedSampler({
  root: new ErrorAwareSampler(),
});
```

- 5-10% sampling for normal traffic balances cost and observability.
- 100% error sampling ensures no error trace is lost.
- Adjust the ratio based on traffic volume and storage budget.

## Collector Deployment

Never send telemetry directly from applications to the observability backend. Route through an OpenTelemetry Collector.

| Deployment pattern | When to use |
|-------------------|-------------|
| Sidecar | Per-pod collection in Kubernetes, strong isolation |
| DaemonSet | One collector per node, lower resource overhead |
| Gateway | Centralized collection, cross-cluster aggregation |

The Collector handles batching, retry, export to multiple backends, and sampling decisions. Applications export to `localhost` or a cluster-local endpoint. Backend changes require only Collector reconfiguration, not application redeployment.

```yaml
# Collector pipeline: receivers -> processors -> exporters
receivers:
  otlp:
    protocols:
      grpc: { endpoint: "0.0.0.0:4317" }
processors:
  batch: { timeout: 5s, send_batch_size: 512 }
  memory_limiter: { limit_mib: 512 }
exporters:
  otlp/backend: { endpoint: "observability-backend:4317" }
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/backend]
```

## Trace-Log Correlation

Every log entry must include the active trace ID and span ID. This links logs to the distributed trace they belong to.

```typescript
import { trace } from "@opentelemetry/api";

function getTraceContext(): { traceId: string; spanId: string } {
  const span = trace.getActiveSpan();
  if (!span) {
    return { traceId: "", spanId: "" };
  }
  const context = span.spanContext();
  return { traceId: context.traceId, spanId: context.spanId };
}

// In the logger configuration
const logger = createLogger({
  mixin() {
    return getTraceContext();
  },
});
```

Log frameworks with OTel integration, such as pino, winston, and Bunyan, inject trace context automatically when configured. Verify the integration is active by checking a sample log entry.

## High-Cardinality Attribute Avoidance

Attributes with unbounded unique values explode metric storage and query costs.

| Attribute | Cardinality | Action |
|-----------|------------|--------|
| `http.route` | Bounded by route definitions | Safe as metric label |
| `user.id` | Unbounded, grows with user base | Span attribute only, never a metric label |
| `request.id` | Unique per request | Span attribute only |
| `http.status_code` | Bounded, roughly 40 values | Safe as metric label |
| `error.message` | Unbounded free text | Normalize into error categories |
| `db.statement` | Unbounded, includes parameters | Use parameterized form only |

Rule: metric labels must have bounded cardinality, under 1000 distinct values. Span attributes have no such limit because spans are not aggregated into time series.

## W3C Trace Context Propagation

Use W3C Trace Context as the propagation format. It is the industry standard and supported by all major platforms.

```typescript
const sdk = new NodeSDK({
  textMapPropagator: new W3CTraceContextPropagator(),
});
```

- Set the `traceparent` header on all outgoing HTTP requests.
- Parse the `traceparent` header on all incoming requests.
- Support `tracestate` for vendor-specific context.
- When calling services that use a different propagation format like B3, configure the Collector to translate.

## Span Closure Verification

Every span that is opened must be closed. Unclosed spans leak memory, produce incomplete traces, and corrupt parent-child relationships.

- Use `try/finally` to guarantee span closure.
- Prefer the `tracer.startActiveSpan` callback pattern, which closes the span when the callback returns.
- In tests, verify that all spans are exported and have an end time.

```typescript
// Correct: callback pattern guarantees closure
await tracer.startActiveSpan("process-order", async (span) => {
  try {
    await processOrder(order);
    span.setStatus({ code: SpanStatusCode.OK });
  } catch (error) {
    span.setStatus({ code: SpanStatusCode.ERROR, message: String(error) });
    span.recordException(error as Error);
    throw error;
  } finally {
    span.end();
  }
});
```

## Metric Types

Choose the correct metric instrument for each measurement.

| Instrument | Use case | Example |
|-----------|----------|---------|
| Counter | Monotonically increasing values | Total requests, total errors |
| UpDownCounter | Values that increase and decrease | Active connections, queue depth |
| Histogram | Distribution of values | Request latency, response size |
| Gauge | Point-in-time snapshot | CPU usage, memory usage |

- Counters reset on process restart. Use a rate function in queries to handle resets.
- Histograms use configurable bucket boundaries. Set boundaries based on expected value ranges.
- Use exponential histograms for latency measurements when supported. They adapt bucket boundaries automatically.

## Related Standards

- `standards/observability.md`: Observability
- `standards/sre-practices.md`: SRE Practices
- `standards/distributed-systems.md`: Distributed Systems
