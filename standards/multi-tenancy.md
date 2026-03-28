# Multi-Tenancy

Apply `checklists/checklist.md` category 43 to every multi-tenant system. This standard provides the implementation details behind those checklist items.

## Isolation Strategies

Three levels of tenant isolation exist. The choice depends on compliance requirements, scale, and operational complexity.

### Decision Matrix

| Factor | Row-level (shared DB) | Schema-level (per-tenant schema) | Database-level (per-tenant DB) |
|--------|----------------------|----------------------------------|-------------------------------|
| Data isolation | Logical, enforced by `tenant_id` column + RLS | Logical, enforced by schema search path | Physical, strongest guarantee |
| Compliance suitability | Standard workloads, no regulatory mandate | Industry regulations requiring logical separation | Financial, healthcare, government, or contracts requiring physical separation |
| Operational complexity | Low. One schema, one connection pool, one migration run | Medium. N schemas to migrate, shared connection pool | High. N databases, N connection pools, N migration runs |
| Cross-tenant queries | Possible via missing WHERE clause (risk) | Requires cross-schema joins (harder to do accidentally) | Requires cross-database links (very hard to do accidentally) |
| Cost per tenant | Lowest | Medium (shared compute, separate schemas) | Highest (dedicated compute and storage possible) |
| Tenant count ceiling | Tens of thousands | Hundreds to low thousands | Tens to low hundreds |
| Noisy neighbor risk | Highest without per-tenant quotas | Medium, shared compute but isolated data paths | Lowest, fully independent resources |
| Onboarding speed | Instant, insert a row | Seconds, run schema creation + seed | Minutes, provision database + run migrations |
| Backup/restore granularity | Requires filtering by `tenant_id` | Per-schema dump possible | Per-database dump, simplest |

### Default: start with row-level

Row-level isolation is the default for new multi-tenant systems. Only escalate to schema-level or database-level when a specific requirement demands it: regulatory compliance, contractual obligation, or measured noisy-neighbor impact that per-tenant quotas cannot solve.

### Row-Level Implementation

Every table that stores tenant-owned data must have a `tenant_id` column. No exceptions.

```typescript
// Prisma schema: tenant_id on every tenant-scoped model
model Invoice {
  id        String   @id @default(cuid())
  tenantId  String   @map("tenant_id")
  amount    Int
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  tenant Tenant @relation(fields: [tenantId], references: [id])

  @@index([tenantId])
  @@map("invoices")
}
```

Rules for the `tenant_id` column:

- NOT NULL constraint on every tenant-scoped table
- Foreign key to the tenants table
- Indexed, either standalone or as the leading column in composite indexes
- Never has a default value. The application must set it explicitly on every insert

## Data Leakage Prevention

Cross-tenant data leakage is the highest-severity bug in a multi-tenant system. Every layer must enforce tenant scoping independently.

### Middleware Tenant Context

Extract the tenant ID at the request boundary and propagate it through a request-scoped context. Every downstream layer reads from this context instead of accepting tenant ID as a parameter.

```typescript
// tenant-context.ts
import { AsyncLocalStorage } from "node:async_hooks";

interface TenantContext {
  readonly tenantId: string;
}

const tenantStorage = new AsyncLocalStorage<TenantContext>();

function runWithTenant<T>(tenantId: string, fn: () => T): T {
  return tenantStorage.run({ tenantId }, fn);
}

function getTenantId(): string {
  const context = tenantStorage.getStore();
  if (!context) {
    throw new Error("Tenant context not initialized. Every request must pass through tenant middleware.");
  }
  return context.tenantId;
}

export { runWithTenant, getTenantId };
```

```typescript
// tenant.middleware.ts
import { runWithTenant } from "./tenant-context";

function tenantMiddleware(req: Request, res: Response, next: NextFunction): void {
  const tenantId = req.headers["x-tenant-id"];
  if (!tenantId || typeof tenantId !== "string") {
    res.status(400).json({ error: "Missing X-Tenant-Id header" });
    return;
  }

  runWithTenant(tenantId, () => next());
}
```

### Query-Level Enforcement

Every repository method must include `tenant_id` in the WHERE clause. Never trust the caller to pass the correct tenant ID. Read it from the request-scoped context.

```typescript
// invoice.repository.ts
import { getTenantId } from "./tenant-context";

async function findInvoices(filters: InvoiceFilters): Promise<readonly Invoice[]> {
  const tenantId = getTenantId();

  return prisma.invoice.findMany({
    where: {
      tenantId,
      ...filters,
    },
  });
}
```

### PostgreSQL Row-Level Security

For row-level isolation on PostgreSQL, enable RLS as a defense-in-depth layer on top of application-level scoping. RLS catches bugs that application code misses.

```sql
-- Enable RLS on every tenant-scoped table
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;

-- Policy: rows visible only when tenant_id matches the session variable
CREATE POLICY tenant_isolation ON invoices
  USING (tenant_id = current_setting('app.tenant_id')::text);

-- Set the session variable at connection checkout
SET app.tenant_id = 'tenant_abc123';
```

Rules for RLS:

- Enable on every tenant-scoped table, not just the "important" ones
- Use `FORCE ROW LEVEL SECURITY` so superuser roles are also restricted during application queries
- Set the session variable at connection checkout in the connection pool middleware, never in individual queries
- Test that a query without the session variable returns zero rows, not all rows

### Enforcement Layers

A single enforcement point is a single point of failure. Use at least two layers.

| Layer | Mechanism | What it catches |
|-------|-----------|----------------|
| Middleware | Extracts and validates tenant ID from request | Missing or malformed tenant identifier |
| Repository | Reads tenant ID from async context, adds to every query | Developer forgetting to filter by tenant |
| Database (RLS) | PostgreSQL policy rejects rows not matching session variable | Application bugs, raw queries, ORM bypasses |
| Cache | Tenant ID as part of every cache key | Cross-tenant cache poisoning |

### Cross-Tenant Access Tests

Every multi-tenant system must have explicit tests that verify tenant isolation. These tests are not optional.

```typescript
describe("tenant isolation", () => {
  // Arrange
  const tenantA = faker.string.uuid();
  const tenantB = faker.string.uuid();

  it("must not return tenant B data when querying as tenant A", async () => {
    // Arrange
    await createInvoice({ tenantId: tenantA, amount: 100 });
    await createInvoice({ tenantId: tenantB, amount: 200 });

    // Act
    const invoices = await runWithTenant(tenantA, () => findInvoices({}));

    // Assert
    expect(invoices).toHaveLength(1);
    expect(invoices[0].tenantId).toBe(tenantA);
  });

  it("must not update another tenant's record", async () => {
    // Arrange
    const invoice = await createInvoice({ tenantId: tenantB, amount: 200 });

    // Act
    const result = await runWithTenant(tenantA, () =>
      updateInvoice(invoice.id, { amount: 999 })
    );

    // Assert
    expect(result.count).toBe(0);
    const unchanged = await findInvoiceById(invoice.id);
    expect(unchanged.amount).toBe(200);
  });
});
```

Required test scenarios:

| Scenario | What to verify |
|----------|---------------|
| Read isolation | Tenant A query returns zero records belonging to tenant B |
| Write isolation | Tenant A cannot create records with tenant B's ID |
| Update isolation | Tenant A cannot modify tenant B's records |
| Delete isolation | Tenant A cannot delete tenant B's records |
| Cache isolation | Cached data for tenant A is not served to tenant B |
| Search isolation | Full-text search, filters, and aggregations respect tenant boundaries |

## Noisy Neighbor Prevention

One tenant's activity must not degrade service for other tenants. Enforce limits at every shared resource.

### Per-Tenant Rate Limits

Every API endpoint must enforce per-tenant rate limits. Use the tenant ID as the rate limit key, not user ID or IP address.

| Resource | Limit type | Implementation |
|----------|-----------|----------------|
| API requests | Requests per second per tenant | Token bucket or sliding window keyed by `tenant_id` |
| Database connections | Max concurrent connections per tenant | Per-tenant connection pool or semaphore |
| Queue throughput | Messages per minute per tenant | Per-tenant queue or priority-weighted consumer |
| Storage | Total bytes per tenant | Quota check before every write |
| Background jobs | Concurrent jobs per tenant | Per-tenant worker pool or job semaphore |
| File uploads | Max upload size and daily volume per tenant | Middleware check before processing |

### Per-Tenant Connection Pools

A shared connection pool allows one tenant's slow queries to exhaust connections for everyone. Isolate at the pool level.

```typescript
// connection-pool.ts
interface TenantPoolConfig {
  readonly maxConnections: number;
  readonly idleTimeoutMs: number;
  readonly statementTimeoutMs: number;
}

const DEFAULT_POOL_CONFIG: TenantPoolConfig = {
  maxConnections: 5,
  idleTimeoutMs: 30_000,
  statementTimeoutMs: 10_000,
};

// Per-tenant pool with bounded connections
function createTenantPool(
  tenantId: string,
  config: TenantPoolConfig = DEFAULT_POOL_CONFIG
): Pool {
  return new Pool({
    max: config.maxConnections,
    idleTimeoutMillis: config.idleTimeoutMs,
    statement_timeout: config.statementTimeoutMs,
    application_name: `tenant_${tenantId}`,
  });
}
```

When per-tenant connection pools are too expensive, like systems with thousands of tenants, use a shared pool with per-tenant concurrency limits enforced by a semaphore. Never allow a single tenant to hold more than a fixed percentage of the total pool.

### Per-Tenant Queue Priorities

Separate queues per tenant, or use priority-weighted consumers on a shared queue.

| Strategy | When to use |
|----------|-------------|
| Separate queues per tenant | Low tenant count, strict SLA per tenant, different processing guarantees |
| Priority-weighted shared queue | High tenant count, fair-share scheduling sufficient |
| Dedicated workers per tier | Tiered pricing where premium tenants get guaranteed capacity |

Rules:

- Every queue consumer must enforce a per-tenant processing rate limit
- A tenant that floods the queue must not starve other tenants' messages
- Monitor per-tenant queue depth and alert when any single tenant exceeds 80% of total queue capacity

## Tenant-Scoped Observability

Every log line, metric, and trace must carry the tenant identifier. Observability without tenant context makes debugging multi-tenant issues impossible.

### Logging

Include `tenantId` as a required field on every log entry. Use the same request-scoped context that the query layer uses.

```typescript
// logger.ts
import { getTenantId } from "./tenant-context";

function log(level: string, message: string, context: Record<string, unknown> = {}): void {
  const entry = {
    level,
    message,
    timestamp: new Date().toISOString(),
    tenantId: getTenantId(),
    ...context,
  };
  process.stdout.write(JSON.stringify(entry) + "\n");
}
```

### Metrics

Tag every metric with the tenant ID. Use low-cardinality tenant identifiers as metric labels only when the total tenant count is manageable for the metrics backend. For high tenant counts, use per-tenant metric namespaces or aggregate at query time.

| Tenant count | Strategy |
|-------------|----------|
| Under 100 | `tenantId` as a metric label directly |
| 100 to 10,000 | Emit per-tenant metrics to a time-series database, query by tenant at dashboard time |
| Over 10,000 | Log-based metrics with tenant ID as a structured field, aggregate on demand |

Required per-tenant metrics:

- Request rate and error rate
- Latency (p50, p95, p99)
- Resource consumption: storage bytes, API calls, background job count
- Quota utilization as a percentage of allocated limit

### Distributed Tracing

Add `tenant.id` as a span attribute on the root span. Propagate it to all child spans automatically via the context.

```typescript
// tracing.ts
import { trace } from "@opentelemetry/api";
import { getTenantId } from "./tenant-context";

function startTenantSpan(name: string): Span {
  const span = trace.getTracer("app").startSpan(name);
  span.setAttribute("tenant.id", getTenantId());
  return span;
}
```

### Per-Tenant Alerts

Configure alerts that trigger per tenant, not just globally.

| Alert | Threshold | Action |
|-------|-----------|--------|
| Tenant error rate spike | 5x baseline for that tenant over 5 minutes | Investigate tenant-specific issue |
| Tenant approaching quota | 80% of any resource limit | Notify tenant, prepare for throttling |
| Tenant latency degradation | p99 exceeds 2x the global p99 | Check for noisy neighbor or tenant-specific data hotspot |
| Tenant blocked by rate limit | More than 100 rejected requests in 1 minute | Review limit configuration, contact tenant if needed |

## Tenant Lifecycle

### Onboarding

Provisioning a new tenant must be fully automated. No manual steps, no code changes.

| Isolation level | Onboarding steps |
|----------------|-----------------|
| Row-level | 1. Insert tenant record. 2. Seed default configuration. 3. Create admin user. 4. Set quotas |
| Schema-level | 1. Create schema. 2. Run migrations within schema. 3. Seed data. 4. Insert tenant record in shared schema. 5. Set quotas |
| Database-level | 1. Provision database. 2. Run all migrations. 3. Seed data. 4. Register database connection in routing table. 5. Set quotas |

Rules:

- Onboarding must be idempotent. Running it twice for the same tenant must not create duplicates or fail
- Every step must be wrapped in a transaction where possible. Partial provisioning is worse than failed provisioning
- Record the provisioning status on the tenant record: `provisioning`, `active`, `suspended`, `deprovisioning`, `deleted`
- If any step fails, mark the tenant as `provisioning_failed` with an error message. Never leave a tenant in a half-provisioned state without a status that reflects it

### Offboarding

Tenant deletion must satisfy data privacy requirements. GDPR, LGPD, and similar regulations require actual deletion, not just soft delete.

| Step | Action | Verification |
|------|--------|-------------|
| 1. Export | Generate a full data export for the tenant in a portable format | Export file contains all tenant data, verified by row count comparison |
| 2. Suspend | Set tenant status to `deprovisioning`. Reject all new requests | API returns 403 for the tenant. No new data written |
| 3. Delete data | Remove all tenant-owned rows, files, cache entries, queue messages | Row count for `tenant_id` is zero across all tables |
| 4. Delete configuration | Remove tenant-specific config, feature flags, secrets | No references to the tenant in configuration stores |
| 5. Delete infrastructure | For schema/database isolation: drop schema or database | Schema or database no longer exists |
| 6. Audit log | Record the deletion event with timestamp, operator, and method | Audit entry exists and is immutable |
| 7. Mark deleted | Update tenant status to `deleted` with deletion timestamp | Tenant record reflects final state |

Rules:

- Retain the tenant record itself with status `deleted` for audit purposes. Delete the data, not the tenant metadata
- The data export must be delivered to the tenant or their authorized representative before deletion begins
- Implement a grace period between suspension and deletion, 30 days minimum unless the tenant requests immediate deletion
- Deletion must be complete: database rows, object storage files, search indexes, cache entries, queue messages, and any derived data

### Migration Between Isolation Levels

When a tenant outgrows row-level isolation and needs schema-level or database-level:

1. Provision the target isolation level for the tenant
2. Copy data from the shared environment to the isolated one
3. Verify data integrity: row counts, checksums, referential integrity
4. Switch the tenant's routing entry to point to the new isolation level
5. Run dual-read validation: serve from the new location, compare results with the old location
6. Remove data from the old location after the validation period
7. Update the tenant record to reflect the new isolation level

This migration must be possible without downtime. Use the same patterns as zero-downtime database migrations: dual-write during transition, switch reads, stop writes to old location, clean up.

## Testing

### Isolation Tests

Cross-tenant leakage tests are mandatory for every multi-tenant system. They are not covered by standard unit or integration tests because they require two tenant contexts in the same test.

Required test categories:

| Category | Description |
|----------|-------------|
| Read isolation | Query as tenant A, verify zero results from tenant B |
| Write isolation | Attempt to write with tenant B's ID while authenticated as tenant A |
| Update isolation | Attempt to modify tenant B's record as tenant A, verify no change |
| Delete isolation | Attempt to delete tenant B's record as tenant A, verify record persists |
| Cache isolation | Populate cache as tenant A, verify cache miss when reading as tenant B |
| Search isolation | Full-text and filtered searches return only the requesting tenant's data |
| Aggregate isolation | SUM, COUNT, AVG queries must not include other tenants' data |
| Background job isolation | Jobs queued by tenant A must not process tenant B's data |

### Performance Tests with Simulated Noisy Neighbor

Simulate a tenant generating 10x to 100x normal load while measuring the impact on other tenants.

```typescript
describe("noisy neighbor resilience", () => {
  it("must maintain p99 latency for tenant B while tenant A floods", async () => {
    // Arrange
    const tenantA = await provisionTenant();
    const tenantB = await provisionTenant();
    const baselineLatency = await measureP99Latency(tenantB);

    // Act
    const floodPromise = floodWithRequests(tenantA, { rps: 1000, durationMs: 30_000 });
    const stressedLatency = await measureP99Latency(tenantB);
    await floodPromise;

    // Assert
    expect(stressedLatency).toBeLessThan(baselineLatency * 2);
  });
});
```

Verify:

- Per-tenant rate limits reject excess traffic from the noisy tenant
- Other tenants' latency stays within 2x of baseline during the flood
- The noisy tenant receives 429 responses, not timeouts
- Shared resources like connection pools and queues do not saturate

## Configuration

### Per-Tenant Feature Flags

Feature flags must support tenant-level targeting. A flag that is only global is not sufficient for multi-tenant systems.

```typescript
// feature-flags.ts
interface FeatureFlag {
  readonly name: string;
  readonly defaultValue: boolean;
  readonly tenantOverrides: ReadonlyMap<string, boolean>;
}

function isFeatureEnabled(flag: FeatureFlag, tenantId: string): boolean {
  const override = flag.tenantOverrides.get(tenantId);
  if (override !== undefined) {
    return override;
  }
  return flag.defaultValue;
}
```

Rules:

- Every feature flag must have a global default and support per-tenant overrides
- Flag evaluation must use the tenant ID from the request context, not from user input
- Flag changes must take effect without redeployment. Store flags in a database or external service, not in code
- Log every flag evaluation with the tenant ID and the result for audit purposes

### Per-Tenant Configuration Overrides

Tenants may need different limits, thresholds, or behaviors. Store these as structured configuration, not as code branches.

```typescript
// tenant-config.ts
interface TenantConfig {
  readonly tenantId: string;
  readonly maxApiRequestsPerSecond: number;
  readonly maxStorageBytes: number;
  readonly maxConcurrentJobs: number;
  readonly features: ReadonlyMap<string, boolean>;
  readonly theme: TenantTheme | null;
}

interface TenantTheme {
  readonly primaryColor: string;
  readonly logoUrl: string;
  readonly faviconUrl: string;
}

const DEFAULT_CONFIG: Omit<TenantConfig, "tenantId"> = {
  maxApiRequestsPerSecond: 100,
  maxStorageBytes: 10 * 1024 * 1024 * 1024, // 10 GB
  maxConcurrentJobs: 5,
  features: new Map(),
  theme: null,
};
```

Resolution order for configuration values:

| Priority | Source | Example |
|----------|--------|---------|
| 1 (highest) | Tenant-specific override | Tenant has a custom rate limit of 500 rps |
| 2 | Plan-level default | "Enterprise" plan gets 200 rps |
| 3 | Global default | All tenants get 100 rps |

Rules:

- Never use `if (tenantId === "acme")` in application code. All tenant-specific behavior must come from configuration
- Configuration changes must not require a deployment
- Every configuration key must have a global default. A tenant without overrides must work correctly
- Validate configuration values at load time. A negative rate limit or a storage quota of zero must fail loudly

### Per-Tenant Branding and Theming

When tenants need custom branding:

- Store theme configuration in the tenant config, not in the frontend codebase
- Use CSS custom properties or a design token system that reads from the tenant config at runtime
- Validate asset URLs (logos, favicons) at upload time: format, dimensions, file size
- Serve tenant assets from a CDN with the tenant ID in the path to prevent cache collisions
- Default theme must always be present. A tenant with no custom branding must see a coherent default, not broken styles
