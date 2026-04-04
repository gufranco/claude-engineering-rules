# State Machines

Formal patterns for managing stateful behavior. Use when an entity has discrete states with defined transitions and rules about which transitions are valid.

## When to Use

State machines earn their cost when:
- An entity has 3+ states with conditional transitions between them
- Invalid state transitions are a source of bugs (e.g., shipping a cancelled order)
- Business rules depend on the current state (e.g., "only draft orders can be edited")
- The state diagram is part of the domain language (e.g., order lifecycle, payment flow)

Skip for: simple boolean flags (active/inactive), linear pipelines with no branching, or state that is derived from other data.

## Two Approaches

| Approach | Enforcement | Best for | Trade-off |
|----------|------------|----------|-----------|
| Type state (compile-time) | Compiler prevents invalid transitions. Methods only exist on valid states | Workflows with well-known states that rarely change | Requires one class/type per state. Harder to serialize |
| Runtime state machine | Guard conditions checked at runtime. Invalid transitions return errors | Dynamic workflows, UI state, configurable processes | Invalid transitions are runtime errors, not compile errors |

Use type state when the state set is stable and the compiler catching bugs is worth the extra types. Use runtime machines when states are dynamic, configurable, or need serialization (persisted workflows, UI state charts).

## Type State Pattern

Each state is a distinct type. Methods on a state return the next valid state. Invalid transitions are impossible because the method does not exist.

```typescript
class DraftOrder {
  constructor(
    readonly id: OrderId,
    private readonly items: readonly OrderItem[],
  ) {}

  addItem(item: OrderItem): DraftOrder {
    return new DraftOrder(this.id, [...this.items, item]);
  }

  submit(): Result<SubmittedOrder, OrderError> {
    if (this.items.length === 0) return err(new OrderError('Cannot submit empty order'));
    return ok(new SubmittedOrder(this.id, this.items, new Date()));
  }
  // no ship(), no cancel() — only addItem and submit are valid from draft
}

class SubmittedOrder {
  constructor(
    readonly id: OrderId,
    readonly items: readonly OrderItem[],
    readonly submittedAt: Date,
  ) {}

  approve(approver: UserId): ApprovedOrder {
    return new ApprovedOrder(this.id, this.items, this.submittedAt, approver);
  }

  reject(reason: string): RejectedOrder {
    return new RejectedOrder(this.id, reason);
  }
  // no addItem() — submitted orders cannot be modified
}
```

Rules:
- One class per state. All classes share the same aggregate identity (ID)
- Methods return the new state type, never `this`
- Use `Result` return types when a transition has preconditions that can fail
- Combine with branded types for state-specific IDs when functions should only accept entities in a specific state

### Persistence with Type State

Type state types need mapping for storage. The database stores a discriminated union. The repository reconstitutes the correct type.

```typescript
// Database representation
interface OrderRecord {
  id: string;
  status: 'draft' | 'submitted' | 'approved' | 'rejected';
  items: OrderItemRecord[];
  submittedAt: string | null;
  approvedBy: string | null;
}

// Repository maps to the correct type state
type AnyOrder = DraftOrder | SubmittedOrder | ApprovedOrder | RejectedOrder;

class OrderRepository {
  findById(id: OrderId): Promise<Result<AnyOrder, NotFoundError>> {
    const record = await this.db.findOne(id);
    switch (record.status) {
      case 'draft':     return ok(DraftOrder.fromRecord(record));
      case 'submitted': return ok(SubmittedOrder.fromRecord(record));
      case 'approved':  return ok(ApprovedOrder.fromRecord(record));
      case 'rejected':  return ok(RejectedOrder.fromRecord(record));
    }
  }
}
```

## Runtime State Machine

Define states, events, and transitions as data. A machine function processes events and returns the next state.

```typescript
enum OrderState {
  Draft = 'draft',
  Submitted = 'submitted',
  Approved = 'approved',
  Shipped = 'shipped',
  Delivered = 'delivered',
  Cancelled = 'cancelled',
}

type OrderEvent =
  | { kind: 'submit' }
  | { kind: 'approve'; approver: UserId }
  | { kind: 'ship'; tracking: TrackingId }
  | { kind: 'deliver'; signature: string }
  | { kind: 'cancel'; reason: string };

interface Transition {
  from: OrderState;
  event: OrderEvent['kind'];
  to: OrderState;
  guard?: (context: OrderContext) => Result<void, TransitionError>;
  action?: (context: OrderContext, event: OrderEvent) => void;
}

const transitions: readonly Transition[] = [
  { from: OrderState.Draft,     event: 'submit',  to: OrderState.Submitted },
  { from: OrderState.Submitted, event: 'approve', to: OrderState.Approved },
  { from: OrderState.Submitted, event: 'cancel',  to: OrderState.Cancelled },
  { from: OrderState.Approved,  event: 'ship',    to: OrderState.Shipped },
  { from: OrderState.Approved,  event: 'cancel',  to: OrderState.Cancelled },
  { from: OrderState.Shipped,   event: 'deliver', to: OrderState.Delivered },
] as const;
```

Rules:
- Define transitions as data, not as conditional logic scattered across methods
- Guard conditions validate preconditions for a transition. Return `Result`, not `boolean`
- Actions execute side effects when a transition occurs (emit event, update timestamp)
- The transition table is the single source of truth. All valid state changes are visible in one place

### Transition Function

```typescript
function transition(
  current: OrderState,
  event: OrderEvent,
  context: OrderContext,
): Result<OrderState, TransitionError> {
  const t = transitions.find((t) => t.from === current && t.event === event.kind);

  if (!t) {
    return err(new TransitionError(`Cannot ${event.kind} from ${current}`));
  }

  if (t.guard) {
    const guardResult = t.guard(context);
    if (!guardResult.ok) return guardResult;
  }

  if (t.action) {
    t.action(context, event);
  }

  return ok(t.to);
}
```

## XState

For complex state machines with hierarchical states, parallel regions, or delayed transitions, use XState instead of hand-rolling.

When to reach for XState:
- States have substates (e.g., `Shipping` has `AwaitingPickup`, `InTransit`, `OutForDelivery`)
- Parallel regions (e.g., payment processing and inventory reservation happen concurrently)
- Delayed transitions (e.g., auto-cancel after 30 minutes of inactivity)
- The state machine needs visualization for stakeholder communication

When hand-rolled is enough:
- Flat state list with simple transitions
- No timers or parallel regions
- The transition table fits in one screen

## Testing State Machines

### Test every valid transition

```typescript
describe('OrderStateMachine', () => {
  it('should transition from draft to submitted on submit', () => {
    // Arrange
    const state = OrderState.Draft;

    // Act
    const result = transition(state, { kind: 'submit' }, context);

    // Assert
    expect(result).toEqual(ok(OrderState.Submitted));
  });
});
```

### Test every invalid transition

```typescript
it('should reject ship from draft state', () => {
  // Arrange
  const state = OrderState.Draft;

  // Act
  const result = transition(state, { kind: 'ship', tracking }, context);

  // Assert
  expect(result.ok).toBe(false);
});
```

### Test guard conditions

```typescript
it('should reject submit when order has no items', () => {
  // Arrange
  const state = OrderState.Draft;
  const emptyContext = { ...context, items: [] };

  // Act
  const result = transition(state, { kind: 'submit' }, emptyContext);

  // Assert
  expect(result).toEqual(err(expect.objectContaining({ kind: 'validation' })));
});
```

### Coverage checklist

- Every state has at least one valid outgoing transition (or is explicitly terminal)
- Every terminal state (Delivered, Cancelled) rejects all events
- Every guard condition has both a passing and failing test
- The full happy-path lifecycle is tested end-to-end (Draft → Submitted → Approved → Shipped → Delivered)

## Serialization and Deserialization

State machines that persist state must handle serialization explicitly.

- Serialize only the state identifier and context data, not the state class instance
- On deserialization, reconstruct the correct type from the stored discriminant. Use a factory or repository that maps `status` to the appropriate state class
- Version the serialization format. When adding new states or changing context shape, ensure existing persisted records can still be deserialized
- For type state: the repository is the deserialization boundary. See the "Persistence with Type State" section above
- For runtime machines: store `{ state: string, context: object }` and rehydrate through the transition function

## Entry and Exit Actions

Actions that run on entering or leaving a state, independent of which transition caused the change.

| Action type | When it runs | Example |
|-------------|-------------|---------|
| Entry action | Every time the state is entered, regardless of source transition | Start a timer on entering `AwaitingPayment`, send notification on entering `Shipped` |
| Exit action | Every time the state is left, regardless of destination | Cancel the timer on leaving `AwaitingPayment`, release a held resource |
| Transition action | Only on a specific transition | Log the approver on `Submitted -> Approved` |

Entry/exit actions reduce duplication when multiple transitions lead to the same state. Without them, the same side effect must be repeated in every transition action that targets that state.

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|-------------|---------|-----|
| Boolean state soup | `isSubmitted && !isCancelled && isApproved` | Single state enum. One field, exhaustive matching |
| Transitions in conditionals | `if (status === 'draft') { status = 'submitted' }` scattered across codebase | Centralize in transition table or type state methods |
| Missing terminal states | Order can be cancelled but there is no Cancelled state | Explicitly model all end states |
| Implicit transitions | State changes without going through the machine | All state changes go through the transition function |
| No guard validation | Transition succeeds even when preconditions are not met | Add guard conditions and test them |

## Related Standards

- `standards/ddd-tactical-patterns.md`: DDD Tactical Patterns
- `standards/event-driven-architecture.md`: Event-Driven Architecture
