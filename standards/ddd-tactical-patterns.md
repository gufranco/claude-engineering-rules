# DDD Tactical Patterns

Domain-Driven Design tactical patterns for projects with complex domain logic. Use when the core problem is understanding and modeling business rules, not just moving data between layers.

## When to Use

DDD tactical patterns earn their cost when:
- Business rules have conditionals, state transitions, and invariants that go beyond CRUD
- Domain experts use specific terminology that the code should mirror
- Multiple teams or bounded contexts interact through defined contracts

Skip for: simple CRUD APIs, data pipelines, infrastructure tooling, or any project where the database schema IS the domain model.

## Ubiquitous Language

The code uses the same terms that domain experts use. Not developer translations.

| Domain expert says | Code uses | Code does NOT use |
|-------------------|-----------|-------------------|
| "Place an order" | `placeOrder()` | `createRecord()`, `insertData()` |
| "Order is fulfilled" | `OrderStatus.Fulfilled` | `status: 3`, `isDone: true` |
| "Apply discount" | `applyDiscount(coupon)` | `updatePrice(modifier)` |
| "Backorder" | `BackorderPolicy` | `OutOfStockHandler` |

Rules:
- Class names, method names, enum values, and event names come from domain language
- If the team cannot agree on a term, that is a modeling question to resolve with domain experts, not a naming question to resolve in a PR
- When language changes (business redefines a concept), rename in code. The cost of a rename is lower than the cost of permanent translation

## Value Objects

Immutable objects defined by their attributes, not by identity. Two value objects with the same attributes are equal.

```typescript
class Money {
  private constructor(
    readonly amount: number,
    readonly currency: Currency,
  ) {}

  static create(amount: number, currency: Currency): Result<Money, ValidationError> {
    if (amount < 0) return err(new ValidationError('Amount must be non-negative'));
    return ok(new Money(amount, currency));
  }

  add(other: Money): Result<Money, CurrencyMismatchError> {
    if (this.currency !== other.currency) {
      return err(new CurrencyMismatchError(this.currency, other.currency));
    }
    return ok(new Money(this.amount + other.amount, this.currency));
  }

  equals(other: Money): boolean {
    return this.amount === other.amount && this.currency === other.currency;
  }
}
```

Rules:
- Always immutable. Operations return new instances
- Smart constructor validates invariants at creation. Invalid value objects cannot exist
- Encapsulate behavior with the data. `money.add(other)` instead of `addMoney(a, b)`
- Compare by value, not reference
- Use for: monetary amounts, email addresses, date ranges, coordinates, measurements, any concept where identity does not matter

## Entities

Objects with a unique identity that persists across state changes. Two entities with the same attributes but different IDs are different objects.

```typescript
class Order {
  constructor(
    readonly id: OrderId,
    private _status: OrderStatus,
    private _items: readonly OrderItem[],
    private _placedAt: Date,
  ) {}

  get status(): OrderStatus { return this._status; }
  get items(): readonly OrderItem[] { return this._items; }
  get total(): Money { return this._items.reduce((sum, item) => sum.add(item.price), Money.zero()); }

  cancel(reason: CancellationReason): Result<DomainEvent[], OrderError> {
    if (this._status !== OrderStatus.Placed) {
      return err(new OrderError(`Cannot cancel order in ${this._status} status`));
    }
    this._status = OrderStatus.Cancelled;
    return ok([new OrderCancelled(this.id, reason, new Date())]);
  }
}
```

Rules:
- Identity is established at creation and never changes
- Use branded types for entity IDs: `OrderId`, `UserId`, never raw strings
- Entities enforce their own invariants. An entity in an invalid state is a bug
- Equality by ID only. Two `Order` objects with the same `OrderId` are the same order regardless of other fields
- Minimize public setters. State changes go through methods that enforce business rules and emit domain events

## Aggregates

A cluster of entities and value objects with a single root entity that enforces consistency boundaries. External code can only reference the aggregate through its root.

```typescript
// Order is the aggregate root
// OrderItem is an entity within the aggregate
// Money, Address are value objects within the aggregate

class Order {
  // Only the aggregate root has a public repository
  // OrderItem is never loaded independently

  addItem(product: ProductId, quantity: Quantity, price: Money): Result<void, OrderError> {
    if (this._status !== OrderStatus.Draft) {
      return err(new OrderError('Cannot modify a placed order'));
    }
    if (this._items.length >= Order.MAX_ITEMS) {
      return err(new OrderError(`Order cannot exceed ${Order.MAX_ITEMS} items`));
    }
    this._items = [...this._items, new OrderItem(OrderItemId.generate(), product, quantity, price)];
    return ok(undefined);
  }
}
```

Rules:
- One repository per aggregate. `OrderRepository`, never `OrderItemRepository`
- Transactions do not span aggregates. Each aggregate is a consistency boundary
- Reference other aggregates by ID, not by object reference. `Order` holds `customerId: CustomerId`, not `customer: Customer`
- Keep aggregates small. Large aggregates create contention and performance problems. If two parts of the aggregate change independently, they are probably two aggregates. Target fewer than 10 entities per aggregate. If load testing shows lock contention, split
- Cross-aggregate consistency is eventual. Use domain events to synchronize. For multi-step cross-aggregate workflows, use the Saga pattern from `standards/distributed-systems.md`
- Validation belongs in the domain layer, not in adapters. See `standards/hexagonal-architecture.md` Ports section for how domain ports define validation contracts

## Domain Events

Record that something meaningful happened in the domain. Events are past-tense, immutable facts.

```typescript
class OrderPlaced {
  readonly kind = 'OrderPlaced' as const;

  constructor(
    readonly orderId: OrderId,
    readonly customerId: CustomerId,
    readonly total: Money,
    readonly occurredAt: Date,
  ) {}
}

class OrderCancelled {
  readonly kind = 'OrderCancelled' as const;

  constructor(
    readonly orderId: OrderId,
    readonly reason: CancellationReason,
    readonly occurredAt: Date,
  ) {}
}

type OrderEvent = OrderPlaced | OrderCancelled | OrderShipped;
```

Rules:
- Past tense: `OrderPlaced`, not `PlaceOrder` (that is a command)
- Immutable. Events represent facts that already happened
- Include all data a consumer needs. Consumers should not need to query back for details
- Use discriminated unions with a `kind` tag for exhaustive matching
- Aggregate methods return domain events. The application layer dispatches them

## Domain Services

Operations that do not belong to a single entity or value object. A domain service is a stateless function that coordinates domain logic across multiple aggregates or uses domain knowledge that does not fit in one entity.

```typescript
class PricingService {
  calculateDiscount(
    order: Order,
    customer: CustomerTier,
    activeCoupons: readonly Coupon[],
  ): Result<Money, PricingError> {
    // Complex pricing logic that spans Order, Customer, and Coupon concepts
  }
}
```

Rules:
- Stateless. No fields, no mutable state. Pure domain logic
- Name from ubiquitous language: `PricingService`, `RoutingService`, `FraudDetectionService`
- Domain services use domain types only. No HTTP, no database, no framework types
- If the logic fits in an entity or value object, put it there. Domain services are for cross-entity operations

## Repositories

Collection-like abstraction for aggregate persistence. Defined as a port in the domain layer, implemented as an adapter.

```typescript
// Domain layer defines the interface
interface OrderRepository {
  findById(id: OrderId): Promise<Result<Order, NotFoundError>>;
  save(order: Order): Promise<Result<void, PersistenceError>>;
  nextId(): OrderId;
}

// Adapter layer implements it
class PostgresOrderRepository implements OrderRepository {
  // Maps between database rows and domain objects
}
```

Rules:
- One repository per aggregate root
- Repository interface uses domain types only
- Repositories return fully reconstituted aggregates, not database rows or partial objects
- `save` handles both insert and update. The caller does not distinguish between new and existing aggregates
- Repositories do not contain query logic for reporting or search. Use separate read models for complex queries (CQRS)

## Saga vs Domain Events

Sagas and domain events solve different coordination problems. Do not conflate them.

| Mechanism | Purpose | Consistency | Rollback |
|-----------|---------|-------------|----------|
| Domain events | Notify that something happened. Listeners react independently | Eventual. Each listener succeeds or fails independently | No built-in rollback. Each listener handles its own failure |
| Saga (orchestration) | Coordinate a multi-step workflow across aggregates or services | Eventual. Steps run sequentially with compensating actions | Each step has a compensating action that undoes its effect |
| Saga (choreography) | Decentralized coordination via event chains | Eventual. Each service reacts to events and publishes its own | Each service publishes a compensating event on failure |

**When to use which:**
- Single aggregate change that other modules need to know about: domain event
- Multi-aggregate workflow where all steps must eventually succeed or all must be compensated: saga
- Default to orchestration sagas. Choreography sagas become hard to trace and debug beyond 3-4 steps

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|-------------|---------|-----|
| Anemic domain model | Entities are data bags with getters/setters. Logic lives in services | Move behavior into entities and value objects. Services are for cross-entity operations only |
| God aggregate | One aggregate contains the entire domain | Split by consistency boundary. Ask: "what must be transactionally consistent?" |
| Aggregate references by object | `Order` holds `customer: Customer` | Reference by ID: `customerId: CustomerId`. Load separately when needed |
| Domain events with incomplete data | Event only has an ID, consumer must query for details | Include all relevant data in the event payload |
| Repository with business logic | Repository filters by business rules | Business logic in domain services. Repository provides collection operations |
| Ubiquitous language drift | Code uses developer terms while docs use business terms | Rename. The code IS the model |
| Transaction spans aggregates | A single database transaction modifies multiple aggregates | Each aggregate is a consistency boundary. Use domain events or sagas for cross-aggregate coordination |
