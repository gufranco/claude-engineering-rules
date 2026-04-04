# GraphQL API Design

## Schema Design

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Fields | camelCase | `firstName`, `createdAt`, `orderTotal` |
| Types | PascalCase | `User`, `OrderItem`, `PaymentStatus` |
| Enums | PascalCase type, UPPER_SNAKE_CASE values | `enum Role { ADMIN, EDITOR, VIEWER }` |
| Input types | PascalCase with `Input` suffix | `CreateUserInput`, `UpdateOrderInput` |
| Mutations | camelCase verb + noun | `createUser`, `cancelOrder`, `assignRole` |
| Queries | camelCase noun or getter | `user`, `orders`, `currentUser` |
| Subscriptions | camelCase with event context | `orderStatusChanged`, `messageReceived` |
| Connections | PascalCase type + `Connection` | `UserConnection`, `OrderConnection` |
| Edges | PascalCase type + `Edge` | `UserEdge`, `OrderEdge` |

### Nullability

Default to non-nullable. Make a field nullable only when null carries distinct meaning.

```graphql
type User {
  id: ID!            # always present
  email: String!     # required
  name: String!      # required
  bio: String        # nullable: user may not have set one
  deletedAt: DateTime # nullable: null means not deleted
}
```

- Every `ID` field must be non-nullable
- Foreign key references must be non-nullable unless the relationship is optional
- List fields must be non-nullable with non-nullable items: `[Order!]!`, never `[Order]` or `[Order!]`
- Mutation return types must be non-nullable

### Pagination

Use Relay cursor-based connections for all list fields. Offset-based pagination must not be used in GraphQL schemas.

```graphql
type Query {
  users(first: Int, after: String, last: Int, before: String): UserConnection!
}

type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type UserEdge {
  cursor: String!
  node: User!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

- Default page size: 20. Maximum: 100. Enforce server-side
- Cursors must be opaque. Base64-encode the underlying key. Never expose raw IDs or offsets
- Every connection must include `totalCount` for UI pagination controls

### Input Types

Every mutation must accept a single input argument typed as a dedicated input type.

```graphql
# Correct: single input object
type Mutation {
  createUser(input: CreateUserInput!): CreateUserPayload!
}

input CreateUserInput {
  email: String!
  name: String!
  role: Role!
}

# Wrong: loose arguments
type Mutation {
  createUser(email: String!, name: String!, role: Role!): User!
}
```

- Input types must not share fields by inheritance. Duplicate fields across inputs when needed
- Nested input types are acceptable for structured data: `AddressInput` inside `CreateUserInput`
- Every mutation must return a dedicated payload type, not the entity directly

### Enums

Use GraphQL enums for all fixed domain values. Never use `String` for a field with a known set of values.

```graphql
enum OrderStatus {
  DRAFT
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
  CANCELLED
}

enum Role {
  ADMIN
  EDITOR
  VIEWER
}
```

- Enum values use UPPER_SNAKE_CASE
- Document enum values with descriptions when the name alone is ambiguous
- Adding a new value is non-breaking. Removing a value is breaking: deprecate first

## Query Complexity

### Limits

| Constraint | Limit |
|-----------|-------|
| Maximum query depth | 10 levels |
| Maximum complexity score | 1000 points |
| Maximum number of aliases | 20 |
| Maximum number of root fields | 10 |

### Complexity Scoring

Assign a cost to each field based on its resolver cost. Use static analysis before execution.

| Field type | Default cost |
|-----------|-------------|
| Scalar field | 0 |
| Object field | 1 |
| List field without connection | 1 x estimated item count |
| Connection field | cost(first or last argument) x child complexity |
| Mutation | 10 base + field costs |

```typescript
import { createComplexityRule, simpleEstimator, fieldExtensionsEstimator } from 'graphql-query-complexity';

const complexityRule = createComplexityRule({
  maximumComplexity: 1000,
  estimators: [
    fieldExtensionsEstimator(),
    simpleEstimator({ defaultComplexity: 1 }),
  ],
  onComplete: (complexity: number) => {
    if (complexity > 800) {
      logger.warn('high query complexity', { complexity });
    }
  },
});
```

### Persisted Queries

Production environments must use persisted queries. Arbitrary query strings from clients must be rejected.

- Development: allow arbitrary queries
- Staging: log unregistered queries as warnings
- Production: reject unregistered queries with a 400 error

Store the query allowlist as a static map of hash-to-query. Generate it from the client codebase at build time.

## N+1 Prevention

### DataLoader Pattern

Every resolver that fetches data by a parent ID must use a DataLoader. Direct database calls inside field resolvers are banned.

```typescript
import DataLoader from 'dataloader';

// Create per-request DataLoader instances
function createLoaders(db: Database) {
  return {
    userById: new DataLoader<string, User>(async (ids) => {
      const users = await db.user.findMany({
        where: { id: { in: [...ids] } },
      });
      const userMap = new Map(users.map((u) => [u.id, u]));
      return ids.map((id) => userMap.get(id) ?? new Error(`User ${id} not found`));
    }),

    ordersByUserId: new DataLoader<string, readonly Order[]>(async (userIds) => {
      const orders = await db.order.findMany({
        where: { userId: { in: [...userIds] } },
      });
      const grouped = new Map<string, Order[]>();
      for (const order of orders) {
        const existing = grouped.get(order.userId) ?? [];
        grouped.set(order.userId, [...existing, order]);
      }
      return userIds.map((id) => grouped.get(id) ?? []);
    }),
  };
}

// Resolver usage
const resolvers = {
  Order: {
    user: (parent: Order, _args: unknown, ctx: Context) =>
      ctx.loaders.userById.load(parent.userId),
  },
  User: {
    orders: (parent: User, _args: unknown, ctx: Context) =>
      ctx.loaders.ordersByUserId.load(parent.id),
  },
};
```

### Rules

- Create DataLoader instances per request. Never share across requests: DataLoader caches are request-scoped
- The batch function must return results in the same order as the input keys
- For keys not found, return an `Error` instance at that index, not `null` or `undefined`
- For one-to-many relationships, the batch function returns arrays per key
- Monitor batch sizes. If a DataLoader consistently receives batches of 1, the batching window is misconfigured

### When Not to Use DataLoader

| Scenario | Approach |
|----------|---------|
| Root query resolvers | Direct database query with filters |
| Mutations | Direct database write, no batching needed |
| Fields derived from parent data | Compute in the resolver, no fetch needed |
| Aggregations | Direct query, DataLoader adds no value |

## Error Handling

### Error Classification

Separate user errors from system errors. User errors are expected domain failures. System errors are unexpected infrastructure failures.

| Category | Examples | How to communicate |
|----------|----------|-------------------|
| User error | Validation failure, not found, permission denied, business rule violation | Union type in the return type |
| System error | Database down, OOM, unhandled exception | GraphQL `errors` array with extensions |

### Union Types for Expected Errors

Mutations must return union types that make expected failure cases explicit in the schema.

```graphql
type Mutation {
  createUser(input: CreateUserInput!): CreateUserResult!
}

union CreateUserResult = CreateUserSuccess | ValidationError | DuplicateEmailError

type CreateUserSuccess {
  user: User!
}

type ValidationError {
  message: String!
  fields: [FieldError!]!
}

type FieldError {
  field: String!
  message: String!
}

type DuplicateEmailError {
  message: String!
  existingEmail: String!
}
```

```typescript
const resolvers = {
  Mutation: {
    createUser: async (_parent: unknown, { input }: { input: CreateUserInput }, ctx: Context): Promise<CreateUserResult> => {
      const validation = validateCreateUser(input);
      if (!validation.ok) {
        return {
          __typename: 'ValidationError',
          message: 'Invalid input',
          fields: validation.errors,
        };
      }

      const existing = await ctx.db.user.findUnique({ where: { email: input.email } });
      if (existing) {
        return {
          __typename: 'DuplicateEmailError',
          message: 'Email already registered',
          existingEmail: input.email,
        };
      }

      const user = await ctx.db.user.create({ data: input });
      return { __typename: 'CreateUserSuccess', user };
    },
  },

  CreateUserResult: {
    __resolveType: (obj: CreateUserResult) => obj.__typename,
  },
};
```

### System Error Extensions

System errors use the standard GraphQL `errors` array with structured extensions.

```typescript
import { GraphQLError } from 'graphql';

throw new GraphQLError('Service temporarily unavailable', {
  extensions: {
    code: 'SERVICE_UNAVAILABLE',
    timestamp: new Date().toISOString(),
    retryable: true,
  },
});
```

Standard error codes:

| Code | Meaning |
|------|---------|
| `UNAUTHENTICATED` | Missing or invalid auth token |
| `FORBIDDEN` | Authenticated but not authorized |
| `NOT_FOUND` | Resource does not exist |
| `VALIDATION_ERROR` | Input validation failed |
| `CONFLICT` | State conflict, like concurrent modification |
| `RATE_LIMITED` | Too many requests |
| `INTERNAL_ERROR` | Unexpected server error |
| `SERVICE_UNAVAILABLE` | Downstream dependency failed |

- Never expose stack traces, internal paths, or SQL in error messages
- Every error extension must include a `code` field for machine-readable classification
- Include `retryable: boolean` so clients know whether to retry

### Partial Success

Queries that resolve multiple fields must return partial results when some fields fail. A failed field resolver must not abort the entire query. Set the field to `null` and add the error to the `errors` array.

## Authorization

### Field-Level Auth

Use schema directives for declarative authorization. Every field that requires a specific role must be annotated.

```graphql
directive @auth(requires: Role!) on FIELD_DEFINITION

type Query {
  users: UserConnection! @auth(requires: ADMIN)
  currentUser: User! @auth(requires: VIEWER)
}

type User {
  id: ID!
  email: String! @auth(requires: ADMIN)
  name: String!
  salary: Float! @auth(requires: ADMIN)
}
```

### Resolver-Level Checks

Directives handle role checks. Resource-level authorization, like "user A can only see their own orders", must be enforced in the resolver.

```typescript
const resolvers = {
  Query: {
    order: async (_parent: unknown, { id }: { id: string }, ctx: Context): Promise<Order> => {
      const order = await ctx.loaders.orderById.load(id);
      if (!order) {
        throw new GraphQLError('Order not found', {
          extensions: { code: 'NOT_FOUND' },
        });
      }
      if (order.userId !== ctx.user.id && ctx.user.role !== Role.ADMIN) {
        throw new GraphQLError('Not authorized', {
          extensions: { code: 'FORBIDDEN' },
        });
      }
      return order;
    },
  },
};
```

### Schema Visibility

Use schema filtering to hide fields and types the current user cannot access. An unauthenticated client must not see admin-only fields in introspection results.

- Disable introspection in production unless the API is public
- When introspection is enabled, filter the schema per role
- Use a schema transform or gateway middleware to strip unauthorized types before serving introspection

## Federation and Composition

### When to Federate

| Scenario | Approach |
|----------|---------|
| Single team, single service | Monolithic schema. No federation overhead |
| Multiple teams, independent deploy cycles | Apollo Federation with a supergraph |
| Third-party schema integration | Schema stitching with type merging |
| Gateway aggregation of identical schemas | No federation, use a reverse proxy |

### Federation Rules

- Each subgraph owns its types. Only the owner defines fields on a type. Other subgraphs extend it via `@key`
- Entity references must use `@key` with the minimal set of fields needed to resolve the entity
- Every subgraph must be independently deployable and testable
- The supergraph schema must be composed and validated in CI before deploy

```graphql
# Users subgraph
type User @key(fields: "id") {
  id: ID!
  email: String!
  name: String!
}

# Orders subgraph
type User @key(fields: "id") {
  id: ID! @external
  orders: [Order!]!
}

type Order @key(fields: "id") {
  id: ID!
  total: Float!
  user: User!
}
```

### Service Boundaries

Split subgraphs along domain boundaries, not technical layers.

- One subgraph per bounded context: Users, Orders, Payments, Inventory
- Never split by resolver type, like "queries subgraph" and "mutations subgraph"
- Shared types, like `Address` or `Money`, live in the subgraph that owns the domain concept
- Cross-subgraph communication uses entity references, never direct service calls

## Subscriptions

### Transport

Use WebSocket with the `graphql-ws` protocol. The older `subscriptions-transport-ws` library is deprecated and must not be used.

### Lifecycle

```
Client                    Server
  |--- connection_init --->|
  |<-- connection_ack -----|
  |--- subscribe --------->|
  |<-- next (data) --------|
  |<-- next (data) --------|
  |--- complete ---------->|
  |<-- complete -----------|
```

### Rules

| Constraint | Limit |
|-----------|-------|
| Max concurrent subscriptions per client | 10 |
| Max concurrent connections per user | 5 |
| Connection idle timeout | 5 minutes without ping/pong |
| Subscription TTL | 1 hour, client must reconnect |

- Authenticate on `connection_init`. Reject unauthorized connections before accepting subscriptions
- Validate subscription queries against the same complexity rules as regular queries
- Every subscription must filter events server-side. Never broadcast all events and let the client filter

### Backpressure

When the server produces events faster than the client consumes them:

1. Buffer up to 100 events per subscription
2. If the buffer fills, drop the oldest events and send a warning message
3. If the client falls behind consistently for 30 seconds, terminate the subscription with an error
4. Log dropped events with the subscription ID and client identifier

## Performance

### Response Caching

| Cache level | When to use | TTL guidance |
|-------------|-------------|-------------|
| CDN/edge | Public data, introspection | 5-60 minutes |
| Application | Authenticated per-user data | 10-60 seconds |
| DataLoader | Within a single request | Request-scoped, no TTL |

- Use the `@cacheControl` directive to set per-field cache hints

```graphql
type Product @cacheControl(maxAge: 300) {
  id: ID!
  name: String! @cacheControl(maxAge: 3600)
  price: Float! @cacheControl(maxAge: 60)
  inventory: Int! @cacheControl(maxAge: 0)
}
```

- Cache keys must include the full query, variables, and user identity for authenticated data
- Never cache mutation responses

### Automatic Persisted Queries (APQ)

For clients that cannot use a static allowlist, APQ provides a middle ground.

1. Client sends a query hash
2. Server checks the hash against a cache
3. If miss, client resends with the full query text
4. Server stores hash-to-query in a shared cache (Redis)

- APQ reduces bandwidth and parsing overhead
- APQ is not a security mechanism. In production, combine APQ with an allowlist

### Field-Level Cost Directives

Annotate expensive fields to inform complexity analysis and caching.

```graphql
directive @cost(complexity: Int!) on FIELD_DEFINITION

type Query {
  search(query: String!, first: Int!): SearchConnection! @cost(complexity: 50)
  recommendations(userId: ID!): [Product!]! @cost(complexity: 30)
}

type User {
  friends: UserConnection! @cost(complexity: 10)
  activityFeed: [Activity!]! @cost(complexity: 20)
}
```

### Query Allowlisting

| Environment | Policy |
|-------------|--------|
| Development | Accept all queries |
| Staging | Accept all, warn on unregistered |
| Production | Reject unregistered queries |

Generate the allowlist from client code at build time. Store as a hash map. Reject queries not in the map with a `PERSISTED_QUERY_NOT_FOUND` error code.

## Testing

### Schema Validation

Test the schema against structural rules in CI.

```typescript
import { buildSchema, validateSchema } from 'graphql';
import { describe, it, expect } from 'vitest';

describe('schema validation', () => {
  it('must have zero schema errors', () => {
    // Arrange
    const schema = buildSchema(typeDefs);

    // Act
    const errors = validateSchema(schema);

    // Assert
    expect(errors).toHaveLength(0);
  });

  it('must have all connection types follow relay spec', () => {
    // Arrange
    const schema = buildSchema(typeDefs);
    const typeMap = schema.getTypeMap();
    const connectionTypes = Object.keys(typeMap).filter((name) => name.endsWith('Connection'));

    // Act & Assert
    for (const name of connectionTypes) {
      const type = typeMap[name];
      if ('getFields' in type) {
        const fields = type.getFields();
        expect(fields).toHaveProperty('edges');
        expect(fields).toHaveProperty('pageInfo');
        expect(fields).toHaveProperty('totalCount');
      }
    }
  });
});
```

### Resolver Tests

Test resolvers with a real database. Mock only external third-party APIs.

```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest';

describe('createUser mutation', () => {
  let db: Database;
  let server: ApolloServer;

  beforeAll(async () => {
    db = await createTestDatabase();
    server = createTestServer(db);
  });

  afterAll(async () => {
    await db.cleanup();
  });

  it('must create a user with valid input', async () => {
    // Arrange
    const mutation = `
      mutation CreateUser($input: CreateUserInput!) {
        createUser(input: $input) {
          ... on CreateUserSuccess {
            user { id email name }
          }
          ... on ValidationError {
            message fields { field message }
          }
        }
      }
    `;
    const variables = {
      input: {
        email: faker.internet.email(),
        name: faker.person.fullName(),
        role: 'VIEWER',
      },
    };

    // Act
    const result = await server.executeOperation({
      query: mutation,
      variables,
    });

    // Assert
    expect(result.body.kind).toBe('single');
    const data = result.body.singleResult.data?.createUser;
    expect(data.__typename).toBe('CreateUserSuccess');
    expect(data.user.email).toBe(variables.input.email);
  });

  it('must return ValidationError for invalid email', async () => {
    // Arrange
    const mutation = `
      mutation CreateUser($input: CreateUserInput!) {
        createUser(input: $input) {
          ... on CreateUserSuccess {
            user { id }
          }
          ... on ValidationError {
            message fields { field message }
          }
        }
      }
    `;
    const variables = {
      input: { email: 'not-an-email', name: faker.person.fullName(), role: 'VIEWER' },
    };

    // Act
    const result = await server.executeOperation({
      query: mutation,
      variables,
    });

    // Assert
    const data = result.body.singleResult.data?.createUser;
    expect(data.__typename).toBe('ValidationError');
    expect(data.fields[0].field).toBe('email');
  });
});
```

### Schema Snapshot Tests

Snapshot the full SDL to detect unintended schema changes.

```typescript
import { printSchema } from 'graphql';
import { describe, it, expect } from 'vitest';

describe('schema snapshots', () => {
  it('must match the approved schema', () => {
    // Arrange
    const schema = buildSchema(typeDefs);

    // Act
    const sdl = printSchema(schema);

    // Assert
    expect(sdl).toMatchSnapshot();
  });
});
```

Review snapshot diffs on every PR. A changed snapshot without a corresponding changelog entry is a review blocker.

### Integration Test Coverage

| Area | What to test |
|------|-------------|
| Auth directives | Unauthenticated request returns `UNAUTHENTICATED` |
| Field auth | User without role cannot read restricted field |
| Pagination | `first`, `after`, `last`, `before` return correct slices |
| Error unions | Each union variant is reachable and returns correct `__typename` |
| N+1 | Query with nested list does not exceed expected query count |
| Complexity | Query exceeding limit returns error before execution |

## Versioning

### Schema Evolution

GraphQL schemas must evolve without breaking existing clients. Never introduce a version number in the schema URL or type names.

### Non-Breaking Changes

These changes are always safe:

- Adding a new type
- Adding a new field to an existing type
- Adding a new enum value
- Adding a new argument with a default value
- Adding a new query or mutation
- Extending a union with a new member

### Breaking Changes

These changes break clients and must follow the deprecation lifecycle:

- Removing a field
- Removing a type
- Removing an enum value
- Changing a field's type
- Making a nullable field non-nullable
- Adding a required argument without a default
- Removing a union member

### Deprecation Lifecycle

```graphql
type User {
  # Phase 1: announce deprecation
  firstName: String! @deprecated(reason: "Use `name` instead. Removal: 2026-09-01")
  name: String!
}
```

| Phase | Duration | Action |
|-------|----------|--------|
| Announce | Day 0 | Add `@deprecated` directive with reason and removal date |
| Monitor | 0-3 months | Track field usage via query analytics. Log clients still querying the field |
| Warn | 3-5 months | Add warning to API changelog and client-facing docs |
| Remove | 6+ months | Remove the field only when usage drops to zero or the deadline passes |

- Minimum deprecation period: 6 months for external APIs, 3 months for internal APIs
- Every deprecated field must include a `reason` that names the replacement
- Schema CI must fail if a deprecated field is removed before its announced date
- Run `graphql-inspector` or equivalent in CI to detect breaking changes against the production schema

## Related Standards

- `standards/api-design.md`: API Design
- `standards/caching.md`: Caching
- `standards/authentication.md`: Authentication
