# Zero-Downtime Deployments

## Deployment Strategy Decision Framework

| Strategy | Rollback speed | Cost | Complexity | Best for |
|----------|---------------|------|-----------|----------|
| Blue-green | Instant, switch traffic back | 2x infrastructure | Low | Stateless services, critical production workloads |
| Canary | Fast, route traffic away from canary | 1x + small canary pool | Medium | Services with measurable success metrics |
| Rolling | Moderate, redeploy previous version | 1x | Low to medium | Orchestrated environments like Kubernetes, ECS |

## Blue-Green Deployment

Maintain two identical environments. Only one serves production traffic at a time.

1. Deploy the new version to the idle environment.
2. Run smoke tests against the idle environment.
3. Switch the load balancer or DNS to point to the new environment.
4. Monitor for errors. If issues appear, switch back immediately.
5. The old environment becomes the idle standby.

Strengths: instant rollback by switching traffic back. Full environment testing before exposure.

Costs: 2x infrastructure during the transition window. Both environments must have identical configuration, data access, and network policies.

Database considerations: both environments share the same database. Schema changes must be backward-compatible so the old version can still operate if traffic is switched back.

## Canary Deployment

Route a small percentage of traffic to the new version. Expand gradually if metrics are healthy.

| Phase | Traffic to canary | Duration | Decision |
|-------|------------------|----------|----------|
| 1 | 1% | 10 minutes | Check error rate, latency p99 |
| 2 | 5% | 15 minutes | Compare metrics against baseline |
| 3 | 25% | 30 minutes | Verify across user segments |
| 4 | 50% | 30 minutes | Final validation |
| 5 | 100% | Complete | Full rollout |

- Automate progression with metric gates. Do not rely on manual observation.
- Halt and rollback if error rate exceeds baseline by 1% or latency p99 increases by 20%.
- Route canary traffic by user segment, not random. This ensures consistent experience per user.
- Log the canary version in every request for post-hoc analysis.

## Rolling Deployment

Update instances in batches. Each batch is drained, updated, health-checked, and returned to the pool.

- Set `maxUnavailable` to limit how many instances are offline simultaneously.
- Set `maxSurge` to allow temporary extra capacity during the rollout.
- Health checks must pass before an updated instance receives traffic.
- If a health check fails, halt the rollout automatically.

```yaml
# Kubernetes rolling update strategy
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1
    maxSurge: 1
```

## Expand-Contract Database Migrations

Database schema changes must not break the currently running application version. The old code and the new code must work against the same database simultaneously.

### Three-phase process

**Phase 1: Expand.** Add new columns, tables, or indexes alongside the existing schema. The old application version ignores them.

```sql
-- Phase 1: Add new column, nullable, with default
ALTER TABLE orders ADD COLUMN status_v2 VARCHAR(50) DEFAULT 'pending';
CREATE INDEX idx_orders_status_v2 ON orders(status_v2);
```

**Phase 2: Migrate.** Deploy code that writes to both old and new structures. Backfill existing data.

```sql
-- Phase 2: Backfill existing records
UPDATE orders SET status_v2 = status WHERE status_v2 IS NULL;
```

**Phase 3: Contract.** After all application versions use the new structure, remove the old columns or tables.

```sql
-- Phase 3: Remove deprecated column (only after all app versions use status_v2)
ALTER TABLE orders DROP COLUMN status;
ALTER TABLE orders RENAME COLUMN status_v2 TO status;
```

Never combine expand and contract in the same deployment. The gap between phases must span at least one full deployment cycle.

### Backward-Compatible Schema Changes

| Change type | Backward compatible? | Strategy |
|-------------|---------------------|----------|
| Add nullable column | Yes | Deploy migration, then code |
| Add non-nullable column | No | Add as nullable with default, backfill, then add NOT NULL constraint |
| Rename column | No | Add new column, dual-write, migrate reads, drop old |
| Drop column | No | Remove all code references first, then drop in next deployment |
| Change column type | No | Add new column with new type, migrate data, swap references, drop old |
| Add index | Yes | Create concurrently to avoid locking |
| Drop table | No | Remove all code references, verify no queries, then drop |

## Progressive Delivery with Feature Flags

Decouple deployment from release. Deploy code to production with features behind flags. Enable features independently of deployments.

- Deploy dark: code is in production but the feature is disabled.
- Enable for internal users first.
- Expand to a percentage of external users.
- Monitor metrics at each expansion step.
- Kill switch: disable the feature instantly without a deployment.

```typescript
async function processCheckout(order: Order): Promise<Result> {
  if (await featureFlags.isEnabled("new-payment-flow", order.userId)) {
    return newPaymentFlow(order);
  }
  return legacyPaymentFlow(order);
}
```

Feature flags are temporary. Every flag must have a cleanup date. After full rollout, remove the flag, the conditional, and the old code path. Stale flags accumulate as technical debt.

## Rollback Procedures

Every deployment must have a documented rollback path before it starts.

| Strategy | Rollback mechanism |
|----------|-------------------|
| Blue-green | Switch load balancer back to the old environment |
| Canary | Route 100% of traffic away from canary, terminate canary instances |
| Rolling | Redeploy the previous container image version |
| Feature flag | Disable the flag |
| Database migration | Run the down migration. If irreversible, restore from backup |

Rollback decisions must be fast. Define rollback criteria in advance:

- Error rate above X% for Y minutes: automatic rollback.
- Latency p99 above Z ms for Y minutes: automatic rollback.
- Any data corruption signal: immediate manual rollback.

## Health Checks

Two types of health checks serve different purposes.

| Check type | Purpose | What it verifies | Failure action |
|-----------|---------|-----------------|----------------|
| Liveness | Is the process running? | Process is responsive | Restart the container |
| Readiness | Can it serve traffic? | Dependencies are reachable, warmup complete | Remove from load balancer |

- Liveness checks must not depend on external services. A database outage should not cause container restarts.
- Readiness checks verify the instance can actually serve requests: database connection, cache connection, configuration loaded.
- Set appropriate timeouts and thresholds. A single failed readiness check should not remove the instance. Use 3 consecutive failures.

## Pre-Deployment Checklist

Before every production deployment:

1. Migrations are backward-compatible with the current running version.
2. Rollback procedure is documented and tested.
3. Monitoring dashboards show current baseline metrics.
4. Alert thresholds are set for automated rollback.
5. Feature flags are configured for gradual rollout if applicable.
6. Communication is sent to stakeholders if the change is user-visible.

## Related Standards

- `standards/database.md`: Database
- `standards/infrastructure.md`: Infrastructure
- `standards/feature-flags.md`: Feature Flags
