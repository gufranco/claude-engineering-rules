# TypeScript Type Constructs

## Construct Selection

| Construct | When to use |
|-----------|------------|
| `interface` | Object shapes: DTOs, props, service contracts. Prefer for public APIs |
| `type` | Unions, intersections, mapped types, conditional types, tuples, function signatures |
| `enum` (string) | Fixed domain values that need runtime existence: statuses, roles, categories |
| `as const` object | Lookup tables with metadata, derive union types from keys/values |
| Discriminated union | Sum types with a `kind`/`type` tag: model states, outcomes, domain events |
| Branded type | Nominal distinction for structurally identical primitives: `UserId` vs `OrderId` |

- `interface` for object shapes, `type` for the rest. Do not mix for the same purpose
- Consistency within a codebase. If DTOs use `interface`, all DTOs use `interface`
- Never alias a single primitive with `type`. Use a branded pattern if needed
- Prefer `interface` when either works. Clearer error messages, supports declaration merging

## Discriminated Unions

Use discriminated unions to make illegal states unrepresentable. When fields depend on each other, model them as variants of a tagged union, not as optional fields on a flat interface.

- Every variant must share a literal `kind`, `type`, or `tag` discriminant property
- Exhaustive matching is mandatory. Use `satisfies never` in the default branch or a library like ts-pattern with `.exhaustive()`. Adding a new variant must produce compile errors at every unhandled match site
- Avoid boolean blindness: when the caller needs to know WHY, return a discriminated union instead of a boolean
- Prefer discriminated unions over class hierarchies for domain modeling. They compose with pattern matching, serialize trivially, and do not require `instanceof`

## Branded Types

Use branded types to prevent structurally identical values from being confused. A `UserId` and an `OrderId` are both strings, but passing one where the other is expected is a bug.

```typescript
type Brand<T, B extends string> = T & { readonly __brand: B };
type UserId = Brand<string, 'UserId'>;
type OrderId = Brand<string, 'OrderId'>;
```

- Zero runtime cost. The brand is a phantom property that exists only in the type system
- Combine with Zod's `.brand()` for runtime validation and compile-time branding in one step
- Use for: IDs, validated strings (Email, URL), units of measure (Seconds vs Milliseconds), monetary amounts with currency

## Type State Pattern

Encode state machine transitions in the type system. Each state is a distinct type. Methods on a state return the next valid state. Invalid transitions do not exist in the API.

```typescript
class DraftOrder {
  submit(items: readonly OrderItem[]): SubmittedOrder { /* ... */ }
  // no ship(), no cancel(); only submit is valid from draft
}

class SubmittedOrder {
  ship(tracking: TrackingId): ShippedOrder { /* ... */ }
  cancel(reason: string): CancelledOrder { /* ... */ }
  // no submit(); cannot submit twice
}

class ShippedOrder {
  deliver(signature: string): DeliveredOrder { /* ... */ }
  // no cancel(); shipped orders follow a return flow, not cancellation
}
```

- Use when: order workflows, payment processing, document lifecycles, connection states, authentication flows
- Different from discriminated unions: unions model "what states exist" as data. Type state models "what transitions are legal" through method availability. The compiler prevents invalid transitions, not runtime checks
- Combine with branded types for state identifiers: `DraftOrderId` vs `ShippedOrderId` prevents passing the wrong order to the wrong function
