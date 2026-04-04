# Contract Testing

## When to Use

Contract testing fills the gap between unit tests and end-to-end integration tests. It verifies that services agree on the shape and behavior of their interactions without requiring all services to run simultaneously.

| Situation | Contract testing? |
|-----------|------------------|
| Microservices with multiple consumers per API | Yes, primary use case |
| Monolith with a single frontend | No, integration tests suffice |
| Third-party API you do not control | No, use schema validation against their OpenAPI spec |
| Internal service with 2+ consumers | Yes |
| Event-driven communication between services | Yes, for event schema contracts |
| Shared library consumed by multiple services | No, version pinning and unit tests are sufficient |

## Consumer-Driven Contracts

The consumer defines what it needs from the provider. The provider verifies it can satisfy those needs. This inverts the traditional approach where the provider dictates the API.

1. Consumer team writes a contract: "I send this request and expect this response shape."
2. Contract is published to a broker.
3. Provider CI fetches the contract and runs verification against its real implementation.
4. If the provider breaks a consumer's contract, the provider's build fails.

This prevents providers from making breaking changes without knowing which consumers are affected.

## Pact Framework

Pact is the standard tool for consumer-driven contract testing.

### Consumer Side

The consumer test creates a mock provider, defines expected interactions, and runs consumer code against the mock.

```typescript
import { PactV4 } from "@pact-foundation/pact";

const provider = new PactV4({
  consumer: "OrderService",
  provider: "UserService",
});

describe("UserService contract", () => {
  it("should return user by ID", async () => {
    // Arrange
    await provider
      .addInteraction()
      .given("user 42 exists")
      .uponReceiving("a request for user 42")
      .withRequest("GET", "/users/42")
      .willRespondWith(200, (builder) => {
        builder.jsonBody({
          id: 42,
          name: Matchers.string("Alice"),
          email: Matchers.email(),
        });
      });

    // Act & Assert
    await provider.executeTest(async (mockServer) => {
      const client = new UserClient(mockServer.url);
      const user = await client.getUser(42);
      expect(user.id).toBe(42);
    });
  });
});
```

### Provider Side

The provider test replays all consumer contracts against the real provider implementation.

```typescript
import { Verifier } from "@pact-foundation/pact";

describe("UserService provider verification", () => {
  it("should satisfy all consumer contracts", async () => {
    // Arrange
    const verifier = new Verifier({
      providerBaseUrl: "http://localhost:3000",
      pactBrokerUrl: process.env.PACT_BROKER_URL,
      provider: "UserService",
      providerVersion: process.env.GIT_SHA,
      publishVerificationResult: true,
      stateHandlers: {
        "user 42 exists": async () => {
          await seedUser({ id: 42, name: "Alice" });
        },
      },
    });

    // Act & Assert
    await verifier.verifyProvider();
  });
});
```

## Pact Broker

The Pact Broker stores contracts and verification results. It acts as the single source of truth for API compatibility across all services.

- Self-host with Docker or use PactFlow as a managed service.
- Publish consumer contracts after consumer tests pass.
- Tag contracts with the consumer's branch and environment: `main`, `staging`, `production`.
- Provider verification fetches contracts by tag, not by "latest." This prevents a consumer's feature branch from breaking the provider's main build.

## Can-I-Deploy Gate

`can-i-deploy` checks whether a specific version of a service is compatible with all services in a target environment.

```bash
pact-broker can-i-deploy \
  --pacticipant UserService \
  --version $GIT_SHA \
  --to-environment production
```

- Run `can-i-deploy` as a required CI check before deployment.
- If it returns failure, the service has unverified or broken contracts with services already in that environment.
- Never deploy without a passing `can-i-deploy` check.

## Contract Versioning

APIs evolve. Contracts must evolve with them without breaking existing consumers.

| Change type | Impact | Strategy |
|-------------|--------|----------|
| Adding a new field to response | Non-breaking | Consumers ignore unknown fields. No contract update needed |
| Removing a response field | Breaking | Verify no consumer contract depends on it via `can-i-deploy` |
| Changing a field type | Breaking | Publish a new contract version, update consumers first |
| Adding a required request field | Breaking | Add as optional first, migrate consumers, then make required |
| Adding a new endpoint | Non-breaking | No impact on existing contracts |

### Versioning workflow for breaking changes

1. Provider adds new field or endpoint alongside the old one.
2. Consumers update their contracts to use the new version.
3. All consumer contracts pass verification against the provider.
4. Provider removes the deprecated field or endpoint.

This mirrors the expand-contract pattern used for database migrations.

## Provider States

Provider states set up test data for contract verification. They are the contract testing equivalent of test fixtures.

- Name states descriptively: `"user 42 exists"`, `"no orders for user 99"`.
- Keep state handlers idempotent. They may run multiple times.
- State handlers run real setup code, not mocks. Seed the database, configure feature flags, create test records.
- Clean up state after verification to avoid test pollution.

## Event Contracts

For event-driven architectures, test the contract between event producers and consumers.

- The consumer defines what event shape it expects.
- The producer verifies it can produce events matching that shape.
- Use Pact's message interaction support for async contracts.

```typescript
await provider
  .addInteraction()
  .expectsToReceive("an order created event")
  .withContent(
    contentType("application/json"),
    {
      orderId: Matchers.uuid(),
      userId: Matchers.integer(),
      total: Matchers.decimal(),
      currency: Matchers.string("USD"),
    },
  );
```

## Integration with CI

| Pipeline stage | Action |
|----------------|--------|
| Consumer PR | Run consumer contract tests, publish to broker with branch tag |
| Provider PR | Run provider verification against `main` tagged contracts |
| Pre-deploy | Run `can-i-deploy` for the target environment |
| Post-deploy | Tag the deployed version with the environment name |

A consumer PR that publishes a new contract does not block the provider. The provider verifies on its own schedule. But deployment is blocked until both sides verify.

## Related Standards

- `standards/api-design.md`: API Design
- `standards/distributed-systems.md`: Distributed Systems
