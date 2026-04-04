# Feature Flags

Systematic approach to decoupling deployment from release. Feature flags control runtime behavior without code deploys. Every flag has a type, an owner, and an expiration plan.

## Flag Types

Every flag must declare its type at creation. The type determines lifecycle, ownership, and cleanup rules.

| Type | Purpose | Lifetime | Owner | Cleanup |
|------|---------|----------|-------|---------|
| Release | Gate incomplete or risky features during rollout | Temporary. Max 30 days after 100% rollout | Feature team | Remove flag and dead code path within 30 days of full rollout |
| Experiment | A/B tests, multivariate tests | Temporary. Max 90 days | Product/growth team | Remove after experiment concludes and winner is chosen |
| Ops | Kill switches, maintenance mode, load shedding | Permanent until feature is decommissioned | Platform/SRE team | Review quarterly. Remove when the guarded system is retired |
| Permission | Feature entitlements, plan-based access | Permanent | Product team | Remove when the feature becomes universally available or the product tier is retired |

### Metadata Schema

Every flag definition must include these fields:

```typescript
interface FlagDefinition {
  readonly key: string;               // kebab-case: "checkout-redesign"
  readonly type: 'release' | 'experiment' | 'ops' | 'permission';
  readonly description: string;       // what the flag controls and why
  readonly owner: string;             // team or individual responsible
  readonly createdAt: string;         // ISO 8601
  readonly expiresAt: string | null;  // null only for ops and permission types
  readonly defaultValue: boolean;     // fallback when evaluation fails
  readonly tags: readonly string[];   // grouping: ["checkout", "payments"]
}
```

Rules:
- Release and experiment flags must have a non-null `expiresAt`
- Flag keys must be globally unique and use kebab-case
- The `owner` field must reference a team, not a person. People change teams. Teams own features
- `defaultValue` must be the safe value: `false` for new features, `true` for kill switches

## Evaluation

### Server-Side vs Client-Side

| Aspect | Server-side | Client-side |
|--------|------------|-------------|
| Evaluation location | Application server | Browser or mobile app |
| Latency | Sub-millisecond, in-process | Sub-millisecond from local cache, seconds if fetching |
| Security | Flag rules stay server-side | Flag rules exposed to the client |
| Use case | API behavior, business logic, infrastructure | UI variations, frontend experiments |
| Sensitive flags | Required for pricing, permissions, internal ops | Never. Client-side flags are user-visible |

**Default rule**: evaluate server-side. Use client-side only for UI-only flags where the server has no involvement.

### Performance Requirements

Flag evaluation must be sub-millisecond. A feature flag that adds latency to every request defeats its purpose.

| Requirement | Constraint |
|-------------|-----------|
| Evaluation time | < 1ms per flag, < 5ms for a batch of all flags in a request |
| Network calls during evaluation | Zero. Evaluation reads from a local in-memory cache |
| Cache refresh | Background polling or streaming. Never block a request waiting for fresh flag data |
| Cache staleness tolerance | 30 seconds maximum for release flags. 5 minutes for permission flags. 0 for ops flags using streaming |
| Memory footprint | All flag definitions fit in memory. If the flag set exceeds 10MB, the flag taxonomy is bloated |

### Local Cache with Background Refresh

```typescript
import type { FlagValue } from './flags.types';

class FlagEvaluator {
  private readonly cache: ReadonlyMap<string, FlagValue>;
  private readonly defaults: ReadonlyMap<string, FlagValue>;
  private readonly refreshIntervalMs: number;

  constructor(
    private readonly fetcher: FlagFetcher,
    defaults: ReadonlyMap<string, FlagValue>,
    refreshIntervalMs = 30_000,
  ) {
    this.defaults = defaults;
    this.cache = new Map();
    this.refreshIntervalMs = refreshIntervalMs;
  }

  async initialize(): Promise<void> {
    await this.refresh();
    this.startBackgroundRefresh();
  }

  evaluate(key: string, context: EvaluationContext): FlagValue {
    const cached = this.cache.get(key);
    if (cached === undefined) {
      return this.defaults.get(key) ?? false;
    }
    return cached;
  }

  private async refresh(): Promise<void> {
    try {
      const flags = await this.fetcher.fetchAll();
      // Replace entire cache atomically
      (this as { cache: ReadonlyMap<string, FlagValue> }).cache = flags;
    } catch {
      // Cache retains previous values. Log the failure.
      logger.warn('Flag refresh failed, serving stale values');
    }
  }

  private startBackgroundRefresh(): void {
    setInterval(() => {
      void this.refresh();
    }, this.refreshIntervalMs);
  }
}
```

### Fallback Behavior

| Failure mode | Behavior |
|-------------|----------|
| SDK initialization fails | Serve `defaultValue` for every flag. Log an error. Do not block application startup |
| Cache refresh fails | Continue serving previous cached values. Retry on next interval |
| Unknown flag key requested | Return `defaultValue` from flag definition. If no definition exists, return `false` and log a warning |
| Flag service is down | Cache continues serving indefinitely. Alert after 3 consecutive refresh failures |

Rules:
- Never throw an exception from flag evaluation. Return the default value and log
- Never block application startup waiting for the flag service. Initialize asynchronously, serve defaults until ready
- Never make a synchronous network call during evaluation

## Rollout Strategies

### Percentage-Based Rollout

Route a percentage of traffic to the new behavior using consistent hashing on a stable identifier.

```typescript
function evaluatePercentageRollout(
  flagKey: string,
  userId: string,
  percentage: number,
): boolean {
  // Consistent hash: same user always gets the same result for the same flag
  const hash = murmurHash3(`${flagKey}:${userId}`);
  const bucket = hash % 100;
  return bucket < percentage;
}
```

Rules:
- Hash on a stable, unique identifier. Never use session IDs or random values. The same user must see the same variant across requests
- Include the flag key in the hash input. Two flags at 50% must not activate for the exact same users
- Never use `Math.random()`. Non-deterministic evaluation causes flickering

### Gradual Ramp Schedule

| Stage | Percentage | Duration | Gate to proceed |
|-------|-----------|----------|-----------------|
| Canary | 1% | 24 hours minimum | Error rate delta < 0.1%, latency p99 within 10% of baseline |
| Early adopters | 5% | 48 hours | No degradation in canary metrics |
| Partial rollout | 25% | 72 hours | No new error categories, no support tickets |
| Broad rollout | 50% | 48 hours | Business metrics (conversion, engagement) neutral or positive |
| Full rollout | 100% | Stable for 7 days | Begin flag cleanup |

Rules:
- Never jump from 0% to 100%. Every release flag must go through at least 1%, 25%, 100%
- Each stage must have explicit success criteria defined before the rollout starts
- Rollback to 0% immediately if error rate increases by more than 0.5% at any stage

### User-Segment Targeting

```typescript
interface TargetingRule {
  readonly segments: readonly Segment[];
  readonly percentage: number; // within the segment
}

type Segment =
  | { readonly kind: 'user-list'; readonly userIds: readonly string[] }
  | { readonly kind: 'attribute'; readonly key: string; readonly operator: 'eq' | 'in' | 'gt' | 'lt'; readonly value: unknown }
  | { readonly kind: 'geo'; readonly countries: readonly string[] };
```

| Strategy | Use case | Example |
|----------|---------|---------|
| User list | Internal testing, beta users | Enable for the QA team before public rollout |
| Attribute match | Plan-based, role-based | Enable for enterprise plan users |
| Geographic | Regional rollout, compliance | Enable in EU before US for GDPR features |
| Combined | Multi-condition targeting | Enterprise users in the US at 50% |

### Automatic Rollback Triggers

Define rollback conditions per flag before the rollout starts. When any trigger fires, the flag reverts to 0% automatically.

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Error rate increase | > 0.5% above baseline | Rollback to 0%, page on-call |
| Latency p99 increase | > 20% above baseline | Rollback to 0%, alert team |
| Business metric drop | Conversion rate drops > 2% | Rollback to 0%, alert product |
| Manual kill | Operator decision | Rollback to 0% |

## Flag Cleanup

Stale flags are technical debt with compound interest. Every release flag that outlives its rollout is dead code that confuses engineers, bloats the flag service, and makes the codebase harder to reason about.

### Lifecycle Rules

| Rule | Constraint |
|------|-----------|
| Release flag expiration | Must have `expiresAt` set at creation. Maximum 30 days after 100% rollout |
| Experiment flag expiration | Must have `expiresAt` set at creation. Maximum 90 days from creation |
| Stale flag detection | Any flag unchanged for 30 days and at 100% or 0% triggers an alert |
| Expired flag alert | Automated alert to the owning team on the `expiresAt` date. Escalate to engineering lead after 7 days |
| Quarterly audit | Ops and permission flags must be reviewed quarterly. Remove flags for retired features |

### Dead Code Removal

When removing a flag after full rollout:

1. Remove the flag evaluation call and the `else` branch (the old code path)
2. Promote the `if` branch to unconditional code
3. Remove the flag definition from the flag service
4. Search the entire codebase for the flag key string. Remove all references: tests, configs, documentation
5. Remove any feature module wrapper that existed solely for the flag

```typescript
// BEFORE: flag active
function getCheckoutPage(context: RequestContext): CheckoutPage {
  if (flagEvaluator.evaluate('checkout-redesign', context)) {
    return renderRedesignedCheckout(context);
  }
  return renderLegacyCheckout(context);
}

// AFTER: flag removed (redesign is now the only path)
function getCheckoutPage(context: RequestContext): CheckoutPage {
  return renderRedesignedCheckout(context);
}
// Also delete: renderLegacyCheckout, its tests, its CSS, its templates
```

### Preventing Flag Accumulation

| Mechanism | Implementation |
|-----------|---------------|
| CI check for expired flags | A CI step queries the flag service for flags past `expiresAt`. Fail the build if any exist for the PR's owning team |
| Flag count dashboard | Track total flags by type over time. A growing release flag count signals cleanup failure |
| Flag creation budget | Each team gets a maximum of 20 active release flags. New flags require removing an expired one first |

## Testing

### Test Both States

Every feature behind a flag must have tests for both the enabled and disabled paths. A flag that is only tested in one state is a latent production incident.

```typescript
describe('checkout flow', () => {
  describe('when checkout-redesign is enabled', () => {
    beforeEach(() => {
      flagOverrides.set('checkout-redesign', true);
    });

    it('must render the redesigned checkout', () => {
      // Arrange
      const context = buildRequestContext();

      // Act
      const page = getCheckoutPage(context);

      // Assert
      expect(page.template).toBe('checkout-v2');
    });
  });

  describe('when checkout-redesign is disabled', () => {
    beforeEach(() => {
      flagOverrides.set('checkout-redesign', false);
    });

    it('must render the legacy checkout', () => {
      // Arrange
      const context = buildRequestContext();

      // Act
      const page = getCheckoutPage(context);

      // Assert
      expect(page.template).toBe('checkout-v1');
    });
  });
});
```

### Flag Override Mechanism

Provide a test-only override that bypasses the flag service entirely:

```typescript
class TestFlagEvaluator implements FlagEvaluator {
  private readonly overrides = new Map<string, FlagValue>();

  set(key: string, value: FlagValue): void {
    this.overrides.set(key, value);
  }

  clear(): void {
    this.overrides.clear();
  }

  evaluate(key: string, _context: EvaluationContext): FlagValue {
    const override = this.overrides.get(key);
    if (override !== undefined) {
      return override;
    }
    return false; // default off in tests
  }
}
```

Rules:
- Register the test evaluator via dependency injection. Never use `process.env` to toggle flags in tests
- Reset all overrides in `afterEach` to prevent flag state leaking between tests
- Never mock the flag evaluator. Use the real evaluator with test overrides

### Test the Default/Fallback Path

```typescript
it('must serve default when flag service is unavailable', () => {
  // Arrange
  const evaluator = new FlagEvaluator(
    failingFetcher,       // simulates flag service down
    defaultFlags,
  );
  const context = buildRequestContext();

  // Act
  const result = evaluator.evaluate('checkout-redesign', context);

  // Assert
  expect(result).toBe(false); // safe default
});
```

### Testing Flag Interactions

When two flags can be active simultaneously and their behavior overlaps, test the interaction matrix:

| Flag A | Flag B | Expected behavior | Must test? |
|--------|--------|-------------------|-----------|
| Off | Off | Baseline | Yes |
| On | Off | Feature A only | Yes |
| Off | On | Feature B only | Yes |
| On | On | Both features active, no conflict | Yes |

Rules:
- If two flags modify the same code path, the interaction must be tested explicitly
- If the combination is invalid, enforce mutual exclusion in the flag service, not in application code. The flag service must prevent enabling both simultaneously
- Document known flag interactions in the flag definition metadata

## Code Patterns

### Evaluate at the Boundary

Flag evaluation belongs at the system boundary: HTTP handlers, queue consumers, CLI entry points. Never bury flag checks deep in business logic.

```typescript
// WRONG: flag check deep in the domain layer
class OrderService {
  calculateDiscount(order: Order): Money {
    if (this.flags.evaluate('new-discount-algo', { userId: order.userId })) {
      return this.newDiscountCalculator.calculate(order);
    }
    return this.legacyDiscountCalculator.calculate(order);
  }
}

// CORRECT: flag check at the boundary, domain receives the chosen strategy
class OrderController {
  handle(request: CreateOrderRequest): OrderResponse {
    const discountCalculator = this.flags.evaluate('new-discount-algo', request.context)
      ? this.newDiscountCalculator
      : this.legacyDiscountCalculator;

    return this.orderService.createOrder(request, discountCalculator);
  }
}
```

Rules:
- Domain services must not depend on the flag evaluator. They receive the resolved behavior via parameters or injected strategies
- One evaluation per flag per request. Evaluate once at the entry point and pass the result down
- If a flag changes multiple behaviors in the same request, resolve all of them at the boundary and pass a configuration object

### No Nested Flag Checks

```typescript
// WRONG: nested flags create exponential complexity
if (flags.evaluate('feature-a', ctx)) {
  if (flags.evaluate('feature-b', ctx)) {
    handleAB();
  } else {
    handleAOnly();
  }
} else if (flags.evaluate('feature-b', ctx)) {
  handleBOnly();
} else {
  handleBaseline();
}

// CORRECT: resolve flags into a single configuration at the boundary
interface CheckoutConfig {
  readonly useRedesignedCart: boolean;
  readonly useNewPaymentFlow: boolean;
}

function resolveCheckoutConfig(
  flags: FlagEvaluator,
  context: EvaluationContext,
): CheckoutConfig {
  return {
    useRedesignedCart: flags.evaluate('redesigned-cart', context),
    useNewPaymentFlow: flags.evaluate('new-payment-flow', context),
  };
}

// Handler receives a flat config, no flag evaluator dependency
function handleCheckout(config: CheckoutConfig): CheckoutResult {
  const cart = config.useRedesignedCart
    ? buildRedesignedCart()
    : buildLegacyCart();
  const payment = config.useNewPaymentFlow
    ? processNewPayment()
    : processLegacyPayment();
  return { cart, payment };
}
```

### Flag-Aware Dependency Injection

For flags that swap entire implementations, resolve the dependency at the composition root:

```typescript
function configureServices(
  flags: FlagEvaluator,
  context: EvaluationContext,
): ServiceContainer {
  const paymentGateway = flags.evaluate('stripe-migration', context)
    ? new StripeGateway(stripeConfig)
    : new BraintreeGateway(braintreeConfig);

  const notifier = flags.evaluate('email-v2', context)
    ? new SendgridNotifier(sendgridConfig)
    : new SesNotifier(sesConfig);

  return { paymentGateway, notifier };
}
```

### Feature Module Pattern

For large features behind a flag, isolate the entire feature in a module. When the flag is removed, delete the module.

```
src/
  features/
    checkout-redesign/          # entire module lives or dies with the flag
      checkout-redesign.controller.ts
      checkout-redesign.service.ts
      checkout-redesign.module.ts
    checkout/                   # existing stable module
      checkout.controller.ts
      checkout.service.ts
      checkout.module.ts
```

Rules:
- The feature module must not modify existing modules. It provides an alternative implementation
- The flag evaluation at the boundary routes to either the existing module or the feature module
- When the flag is removed, delete the feature module directory and update the routing

## Observability

### Flag Evaluation Logging

Log every flag evaluation with enough context to debug issues. Do not log the evaluation result inline with every request log. Use a structured event.

```typescript
interface FlagEvaluationEvent {
  readonly flagKey: string;
  readonly value: FlagValue;
  readonly userId: string;
  readonly reason: 'cache' | 'default' | 'override' | 'targeting-match';
  readonly timestamp: string;
}
```

Rules:
- Log at `debug` level for normal evaluations. Log at `warn` for fallback/default evaluations
- Include the evaluation reason: was it from cache, from defaults, from an override, or from targeting
- Never log the full targeting rules or user context at `info` level. That data is high-cardinality

### Exposure Tracking

Track which users were exposed to which flag variant. This is the foundation for experiment analysis and incident investigation.

| Data point | Purpose |
|-----------|---------|
| Flag key + variant | Which flag and which value the user saw |
| User ID | Who was exposed |
| Timestamp | When the exposure happened |
| Request ID | Correlate with other request-level data |
| Source | Server-side evaluation, client-side evaluation, or default fallback |

Rules:
- Deduplicate exposures per user per session. A user who hits 50 requests sees one exposure event, not 50
- Store exposure data in the analytics pipeline, not the application database
- Exposure data must be queryable within 1 hour. Real-time is preferable for experiment monitoring

### Flag Impact on Metrics

Connect flag state to business and operational metrics:

| Metric type | What to measure | Example |
|------------|----------------|---------|
| Error rate | Error rate segmented by flag variant | "checkout-redesign: enabled 0.3% error rate vs disabled 0.1%" |
| Latency | p50/p95/p99 segmented by flag variant | "new-search-algo: enabled p99 = 180ms vs disabled p99 = 220ms" |
| Business KPI | Conversion, revenue, engagement per variant | "checkout-redesign: enabled +2.1% conversion" |
| Infrastructure | CPU, memory, DB queries per variant | "new-cache-strategy: enabled 30% fewer DB queries" |

### Flag Change Audit Trail

Every flag state change must be recorded immutably:

```typescript
interface FlagChangeEvent {
  readonly flagKey: string;
  readonly previousValue: FlagConfig;
  readonly newValue: FlagConfig;
  readonly changedBy: string;       // who made the change
  readonly changedAt: string;       // ISO 8601
  readonly reason: string;          // why the change was made
  readonly changeType: 'created' | 'percentage-updated' | 'targeting-updated' | 'killed' | 'deleted';
}
```

Rules:
- Flag changes must be auditable for at least 1 year
- Every change must include a `reason` field. "Updated" is not a reason. "Ramping checkout-redesign from 25% to 50% after 72h stable canary" is
- Integrate flag change events with the incident timeline. When investigating an incident, query "what flags changed in the last 2 hours?"

## Platform Comparison

| Feature | LaunchDarkly | Unleash | Flagsmith | GrowthBook | Custom |
|---------|-------------|---------|-----------|------------|--------|
| Hosting | SaaS | Self-hosted or managed | Self-hosted or SaaS | Self-hosted or cloud | Self-hosted |
| Evaluation | Server-side + client-side SDKs | Server-side + client-side | Server-side + client-side | Server-side + client-side | Whatever you build |
| Targeting | User segments, rules, percentages | Strategies with constraints | Segments and rules | Attributes and conditions | Whatever you build |
| Experiments | Built-in A/B, multivariate | Basic via strategy variants | Built-in | Core focus, statistical engine | Must build or integrate |
| Audit trail | Built-in, SOC 2 compliant | Basic change log | Built-in | Basic change log | Must build |
| SDKs | 25+ languages | 15+ languages | 12+ languages | 10+ languages | 0, you write them |
| Streaming updates | SSE and WebSocket | Webhook + polling | SSE | Webhook + polling | Must build |
| Local evaluation | Yes, all SDKs | Yes, server-side SDKs | Yes | Yes | Must build |
| Pricing | Per seat, expensive at scale | Free (OSS), paid for managed | Free tier, paid for scale | Free (OSS), paid for cloud | Infrastructure cost only |
| Bootstrap time | Minutes | Hours (self-hosted) | Hours (self-hosted) | Hours (self-hosted) | Weeks to months |
| Maintenance burden | Zero (SaaS) | Medium (self-hosted) | Medium (self-hosted) | Medium (self-hosted) | High |

### Selection Guide

| Situation | Recommendation |
|-----------|---------------|
| Startup with < 10 engineers, needs flags fast | LaunchDarkly or Flagsmith SaaS. The cost is lower than the engineering time to self-host |
| Organization that requires data residency or cannot use SaaS | Unleash self-hosted or Flagsmith self-hosted |
| Heavy experimentation and A/B testing focus | GrowthBook. Statistical rigor is its core strength |
| Enterprise with compliance requirements | LaunchDarkly. SOC 2, HIPAA, FedRAMP certifications |
| Already has a mature platform team and wants full control | Custom implementation. Only when the team can commit to maintaining SDKs, cache, audit, and cleanup automation |

**Default rule**: do not build a custom flag system until the team has outgrown a managed solution or has a hard constraint that no vendor satisfies. The evaluation engine is the easy part. The SDKs, caching, audit trail, targeting UI, and cleanup automation are where the real cost lives.

## Related Standards

- `standards/ab-testing.md`: A/B Testing
- `standards/observability.md`: Observability
- `standards/distributed-systems.md`: Distributed Systems
