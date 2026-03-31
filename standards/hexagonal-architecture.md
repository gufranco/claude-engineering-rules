# Hexagonal Architecture

Also known as Ports and Adapters. Extends the "functional core, imperative shell" principle from code-style into a full architectural pattern.

## When to Use

Use hexagonal architecture when the project has two or more infrastructure dependencies (database, message queue, external API, file system) and the domain logic is complex enough that testing it in isolation has clear value. For simple CRUD with one database, this is overhead.

## Structure

Three concentric layers. Dependencies always point inward. The domain never imports from adapters.

```
adapters/  →  application/  →  domain/
(outer)       (middle)         (inner)
```

| Layer | Contains | Depends on | Never imports |
|-------|----------|------------|---------------|
| Domain | Entities, value objects, domain services, domain events, port interfaces | Nothing external | Application, adapters, frameworks, libraries with side effects |
| Application | Use cases, orchestration, input/output DTOs | Domain | Adapters, frameworks |
| Adapters | Controllers, repositories, API clients, CLI handlers, queue consumers | Application, domain | Other adapters |

## Ports

Ports are interfaces defined in the domain layer. They describe what the domain needs from the outside world without knowing how it will be provided.

```typescript
// domain/ports/order-repository.port.ts
interface OrderRepository {
  findById(id: OrderId): Promise<Result<Order, NotFoundError>>;
  save(order: Order): Promise<Result<void, PersistenceError>>;
}

// domain/ports/payment-gateway.port.ts
interface PaymentGateway {
  charge(amount: Money, method: PaymentMethod): Promise<Result<PaymentReceipt, PaymentError>>;
}
```

Rules:
- Ports use domain types only. No SQL types, HTTP types, or library-specific types in port signatures
- Name ports by domain purpose: `OrderRepository`, `PaymentGateway`, `NotificationSender`. Not `PostgresStore` or `StripeClient`
- Ports return `Result` types for expected failures. The domain defines its own error types

## Adapters

Adapters implement port interfaces using specific infrastructure. Each adapter lives in the outer layer.

```typescript
// adapters/persistence/postgres-order-repository.ts
class PostgresOrderRepository implements OrderRepository {
  constructor(private readonly db: DatabaseConnection) {}

  async findById(id: OrderId): Promise<Result<Order, NotFoundError>> {
    const row = await this.db.query('SELECT * FROM orders WHERE id = $1', [id]);
    if (!row) return err(new NotFoundError('Order', id));
    return ok(this.toDomain(row));
  }

  private toDomain(row: OrderRow): Order {
    // Map database representation to domain entity
  }
}
```

Rules:
- One adapter per port per infrastructure. `PostgresOrderRepository` and `InMemoryOrderRepository` both implement `OrderRepository`
- Adapters handle mapping between external representations and domain types. The domain never sees a database row, HTTP request, or message envelope
- Adapters catch infrastructure exceptions and convert them to domain error types

## Dependency Direction

The domain defines what it needs (ports). The application layer wires ports to adapters. The composition root (main entry point) assembles everything.

```typescript
// composition-root.ts (or module registration)
const orderRepository = new PostgresOrderRepository(dbConnection);
const paymentGateway = new StripePaymentGateway(stripeClient);
const submitOrder = new SubmitOrderUseCase(orderRepository, paymentGateway);
```

Rules:
- The domain layer has zero `import` statements pointing to adapter or framework code
- Framework decorators (@Controller, @Injectable) only appear in the adapter and composition layers
- If a domain file imports from `node_modules`, the dependency must be a pure library with no I/O (e.g., date-fns, zod for schemas)

## Testing Strategy

Each layer has a different testing approach:

| Layer | Test type | Infrastructure | Speed |
|-------|-----------|---------------|-------|
| Domain | Unit tests | None. Pure logic, no mocks needed | Instant |
| Application | Integration tests with in-memory adapters | In-memory implementations of ports, or in-memory SQL engines (SQLite, better-sqlite3) for lightweight persistence tests | Fast |
| Adapters | Integration tests with real infrastructure | Real database, real API (or contract tests) | Slower |
| Full stack | E2E tests | Everything real | Slowest |

The domain layer is the functional core: pure functions and types, testable with no setup. This is the primary benefit of the architecture.

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|-------------|---------|-----|
| Domain imports adapter | Inverts dependency direction | Define a port interface in domain, implement in adapter |
| Port uses infrastructure types | Leaks infrastructure into domain | Use domain types only. Map in the adapter |
| Use case returns HTTP status | Application layer knows about HTTP | Return Result with domain error. Adapter maps to HTTP |
| Adapter contains business logic | Logic is untestable without infrastructure | Move logic to domain service, keep adapter as a thin mapper |
| Shared adapter across ports | Creates coupling between unrelated ports | One adapter per port. Shared infrastructure (db connection) is injected, not shared at the adapter level |
