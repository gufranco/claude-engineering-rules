# Railway-Oriented Programming

Extends the "typed error returns" principle from code-style into a full composition pattern for multi-step business logic.

## Core Concept

Every operation returns a `Result<T, E>`. The happy path flows forward. An error at any step short-circuits the rest. No try/catch, no null checks, no boolean flags.

```
  [parseInput] → [validateOrder] → [checkInventory] → [chargePayment] → [confirmOrder]
       ↓ err          ↓ err             ↓ err              ↓ err
    ─────────────── error track ──────────────────────────────────────→ [handleError]
```

## Result Type

A minimal Result type for hand-rolled implementations:

```typescript
type Result<T, E> = { readonly ok: true; readonly value: T }
                   | { readonly ok: false; readonly error: E };

function ok<T>(value: T): Result<T, never> {
  return { ok: true, value };
}

function err<E>(error: E): Result<never, E> {
  return { ok: false, error };
}
```

For projects with multi-step pipelines, use neverthrow or Effect instead of hand-rolling. They provide `map`, `flatMap`, `mapErr`, and composition utilities that are tested and optimized.

## Operations

| Operation | Signature | Use when |
|-----------|-----------|----------|
| `map` | `Result<A, E>` → `(A → B)` → `Result<B, E>` | Transform the success value without new failure modes |
| `flatMap` / `andThen` | `Result<A, E>` → `(A → Result<B, E>)` → `Result<B, E>` | Chain an operation that can itself fail |
| `mapErr` | `Result<A, E1>` → `(E1 → E2)` → `Result<A, E2>` | Transform the error type (e.g., reclassify at a boundary) |
| `unwrapOr` | `Result<A, E>` → `A` → `A` | Extract value with a fallback default |
| `match` | `Result<A, E>` → `{ ok: (A → B), err: (E → B) }` → `B` | Handle both tracks at the boundary |

## Composition Patterns

### Sequential pipeline (fail-fast)

Each step depends on the previous step's output. First failure stops the chain.

```typescript
function submitOrder(input: unknown): Result<OrderConfirmation, SubmitOrderError> {
  return parseOrderInput(input)
    .andThen(validateBusinessRules)
    .andThen(checkInventory)
    .andThen(chargePayment)
    .andThen(confirmOrder);
}
```

### Error accumulation (collect all errors)

Validate multiple independent fields. Collect all errors instead of stopping at the first.

```typescript
function validateOrder(input: OrderInput): Result<ValidOrder, ValidationError[]> {
  const results = [
    validateEmail(input.email),
    validateAddress(input.address),
    validateItems(input.items),
  ];

  const errors = results.filter((r) => !r.ok).map((r) => r.error);
  if (errors.length > 0) return err(errors);

  return ok(buildValidOrder(input));
}
```

Use fail-fast for sequential dependencies (step B needs step A's output). Use error accumulation for independent validations (email and address have no dependency on each other).

### Async pipelines

The same pattern works with `ResultAsync` (neverthrow) or `Effect` for async operations:

```typescript
function submitOrder(input: unknown): ResultAsync<OrderConfirmation, SubmitOrderError> {
  return parseOrderInput(input)       // sync validation
    .asyncAndThen(checkInventory)     // async: hits database
    .andThen(chargePayment)           // async: hits payment API
    .andThen(confirmOrder);           // async: persists
}
```

## Boundary Conversion

At framework boundaries, convert between Result and the framework's error mechanism:

```typescript
// HTTP controller (adapter layer)
async handleSubmitOrder(req: Request, res: Response): Promise<void> {
  const result = await submitOrder(req.body);

  result.match({
    ok: (confirmation) => res.status(201).json(confirmation),
    err: (error) => {
      switch (error.kind) {
        case 'validation': res.status(400).json(error); break;
        case 'inventory':  res.status(409).json(error); break;
        case 'payment':    res.status(502).json(error); break;
        default:           res.status(500).json(error);
      }
    },
  });
}
```

Rules:
- Domain and application layers use Result types. No `throw` for expected failures
- Adapters convert between external exceptions and Result types
- HTTP handlers, CLI entry points, and queue consumers are where Result becomes a response, exit code, or rejection
- Never `.unwrap()` or force-extract without handling the error case. That defeats the purpose

## When to Use

| Scenario | Approach |
|----------|----------|
| Multi-step business pipeline (3+ steps) | Railway with `andThen` chaining |
| Single operation that can fail | Return `Result` directly, no chaining needed |
| Independent validations | Error accumulation |
| CRUD with no complex logic | Direct try/catch at the controller level is fine |
| Framework-required throw patterns | Convert Result to throw at the boundary |

## Library Comparison

| Library | Size | Async support | Ecosystem | Best for |
|---------|------|--------------|-----------|----------|
| Hand-rolled | 0 KB | Manual | None | Simple cases, 1-2 Result types |
| neverthrow | ~5 KB | `ResultAsync` built-in | Small | Most TypeScript projects |
| Effect | ~200 KB | Native, full runtime | Large, growing | Complex systems with dependency injection, concurrency, and observability needs |

Start with neverthrow. Move to Effect when you need its runtime features (structured concurrency, layers, telemetry). Do not adopt Effect for simple Result chaining.

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|-------------|---------|-----|
| `.unwrap()` everywhere | Panics on error, same as not using Result | Use `match` or `andThen` |
| Result wrapping exceptions | `try { ... } catch (e) { return err(e) }` at every call site | Wrap once at the adapter boundary, not in business logic |
| Mixing throw and Result | Callers don't know which error channel to handle | One convention per layer. Domain uses Result, adapters convert |
| Ignoring the error track | `.map()` chains with no error handling at the end | Every pipeline must terminate with `match` or equivalent |
| Over-engineering simple code | Single operation wrapped in a 5-step pipeline | Use Result directly for simple cases. Railway is for composition |

## Related Standards

- `standards/ddd-tactical-patterns.md`: DDD Tactical Patterns
- `standards/resilience.md`: Resilience
