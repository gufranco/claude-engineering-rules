# Code Style

- DRY, SOLID, KISS, YAGNI, LoD, CQS, Pit of Success
- Small functions (< 30 lines)
- Meaningful names
- No magic numbers
- Single export per file
- For functions with many arguments, pass one options object. Return objects.
- File order: main export first, then subcomponents, helpers, static content, types
- Design for change: isolate business logic from the framework. Prefer dependency inversion. Structure as **functional core, imperative shell**: pure logic with no I/O in the core, side effects pushed to the outermost layer. The core is testable with no mocks. The shell converts between the external world and the core's types
- **Use-case functions**: for multi-step business flows, write a thin orchestration function that contains zero conditionals, zero loops, and zero exception handling. Only flat, sequential calls to domain services. Name it in business language (`calculatePriceCut`, `transferOwnership`), not technical language (`processData`). Use cases serve as a navigation index: any reader can see the full flow, its parameters, and its dependencies at a glance
- **No environment conditionals**: never branch business logic on `NODE_ENV`, `APP_ENV`, or equivalent. Code that runs only in production is code that is never tested. Use configuration externalization for infrastructure differences (log format, connection strings), not code conditionals
- **Remove over guard**: when a feature or dependency is unsupported on a platform, prefer removing it over wrapping it in a conditional. Conditionals add complexity, testing surface, and maintenance burden. Only guard when the feature is critical and has no cross-platform alternative
- **Domain exception boundary**: services and domain logic throw domain-specific error classes, never framework HTTP exceptions. An exception filter or middleware at the boundary maps domain errors to HTTP responses.
- **Validation infrastructure**: in NestJS projects, register validation globally via interceptor + method decorator, not per-parameter pipes. Controllers should have no validation imports or logic.
- **Law of Demeter**: only call methods on direct dependencies: `this`, parameters, objects you create, and owned fields. Never chain through transitive objects like `order.getCustomer().getAddress().getCity()`. Each intermediate accessor is a coupling point. If you need data from a distant object, ask your direct collaborator to provide it
- Prefer composition over inheritance
- **No side effects at module level**: module/file scope runs on import. Keep it free of I/O, network calls, global state mutations, and event listener registration. All side effects belong inside explicitly called functions. A module that changes behavior just by being imported is a hidden coupling
- Use braces for all control structures
- **Never swallow errors**: no empty catch; log with context, rethrow or handle
- **Never ignore return values**: every non-void return value must be used or explicitly discarded. Unchecked return values hide failures silently. In TypeScript, enable `@typescript-eslint/no-floating-promises`. In Go, handle every error return. In Rust, never use `let _ =` on a `Result` without justification. If a return value is genuinely irrelevant, document why
- **No deep nesting**: max 3 levels of indentation. Guard clauses and early returns to flatten control flow
- **Flat control flow**: avoid recursion unless the data structure is inherently recursive, like trees or graphs. Prefer iterative solutions with explicit bounds. Recursion hides stack growth, making resource usage unpredictable and stack overflows hard to diagnose. When recursion is necessary, always add a depth limit
- **Strong typing**: explicit types for parameters, return values, and public interfaces. Never `any`, use `unknown` and narrow. Enable strict mode. When modifying a file that already uses `any`, replace it with proper types in the code you touch. Existing violations are not permission to add more
- **Enums over string literal unions**: string enums for domain values. They exist at runtime, can be iterated, and are the single source of truth
- **Explicit imports**: import only what you use. Barrel imports (`import * from`) and re-export index files load entire modules, increasing startup time and memory. For libraries you author, provide granular exports so consumers can import individual functions
- **Bounded iteration**: every loop and retry must have an explicit upper bound. No `while (true)` without a break condition that is guaranteed to trigger. Polling loops need a timeout. Retry loops need a max attempt count. Pagination loops need a page limit. An unbounded loop is a latent outage
- **Minimal scope**: declare variables at the smallest scope where they are used. Do not declare at function top and use 40 lines later. In languages with block scope, declare inside the block. Smaller scope means fewer interactions, easier reasoning, and less surface for bugs
- **Don't block the request-handling thread**: never run CPU-intensive work (image processing, compression, cryptographic operations on large inputs) or synchronous I/O on the thread that serves requests. Offload to a worker thread, background job, or separate process. A blocked request thread stalls all concurrent requests
- **Pit of Success**: design APIs so the correct usage is the easiest path. Wrong usage should require deliberate effort. Accept `NonEmptyArray<T>` instead of `T[]` with a runtime check. Require dependencies in the constructor instead of exposing an `init()` the caller might forget. Use enums instead of magic strings. When a caller can misuse your API without the compiler stopping them, the API is a pit of failure
- **DI only when needed**: start with direct module imports. Only adopt dependency injection when you genuinely need to swap implementations at runtime or in tests. DI containers add indirection, increase startup time, and make stack traces harder to follow. Most applications never need to swap a real implementation
- **No raw SQL**: never use raw SQL when the project has an ORM or query builder. No exceptions. Raw SQL bypasses type safety, query logging, middleware hooks, and migration tracking. Express every database operation, including concurrency patterns, conditional writes, row locking, and atomic updates, using native ORM or query builder methods. If the ORM cannot express the operation, reconsider the approach. Raw SQL is only acceptable when the project has neither an ORM nor a query builder

## TypeScript Type Constructs

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

### Discriminated Unions

Use discriminated unions to make illegal states unrepresentable. When fields depend on each other, model them as variants of a tagged union, not as optional fields on a flat interface.

- Every variant must share a literal `kind`, `type`, or `tag` discriminant property
- Exhaustive matching is mandatory. Use `satisfies never` in the default branch or a library like ts-pattern with `.exhaustive()`. Adding a new variant must produce compile errors at every unhandled match site
- Avoid boolean blindness: when the caller needs to know WHY, return a discriminated union instead of a boolean
- Prefer discriminated unions over class hierarchies for domain modeling. They compose with pattern matching, serialize trivially, and do not require `instanceof`

### Branded Types

Use branded types to prevent structurally identical values from being confused. A `UserId` and an `OrderId` are both strings, but passing one where the other is expected is a bug.

```typescript
type Brand<T, B extends string> = T & { readonly __brand: B };
type UserId = Brand<string, 'UserId'>;
type OrderId = Brand<string, 'OrderId'>;
```

- Zero runtime cost. The brand is a phantom property that exists only in the type system
- Combine with Zod's `.brand()` for runtime validation and compile-time branding in one step
- Use for: IDs, validated strings (Email, URL), units of measure (Seconds vs Milliseconds), monetary amounts with currency

### Type State Pattern

Encode state machine transitions in the type system. Each state is a distinct type. Methods on a state return the next valid state. Invalid transitions do not exist in the API.

```typescript
class DraftOrder {
  submit(items: readonly OrderItem[]): SubmittedOrder { /* ... */ }
  // no ship(), no cancel() — only submit is valid from draft
}

class SubmittedOrder {
  ship(tracking: TrackingId): ShippedOrder { /* ... */ }
  cancel(reason: string): CancelledOrder { /* ... */ }
  // no submit() — can't submit twice
}

class ShippedOrder {
  deliver(signature: string): DeliveredOrder { /* ... */ }
  // no cancel() — shipped orders follow a return flow, not cancellation
}
```

- Use when: order workflows, payment processing, document lifecycles, connection states, authentication flows
- Different from discriminated unions: unions model "what states exist" as data. Type state models "what transitions are legal" through method availability. The compiler prevents invalid transitions, not runtime checks
- Combine with branded types for state identifiers: `DraftOrderId` vs `ShippedOrderId` prevents passing the wrong order to the wrong function

## Command-Query Separation

A function either changes state (command, returns void) or returns data (query, no side effects). Never both.

- Commands perform an action: `saveUser(user)`, `sendEmail(message)`. Return `void` or a `Result` indicating success/failure
- Queries return data without side effects: `getUserById(id)`, `calculateTotal(items)`. Safe to call multiple times
- When you need both, split into two: `createOrder()` (command) then `getOrder(id)` (query), not `createAndReturnOrder()`
- Exceptions: stack/queue `pop` operations where the removal and retrieval are inherently atomic. Document these cases

## Immutability

Immutable by default, mutable by exception. Every value starts as readonly. Mutability requires an explicit decision, not the other way around.

### Behavioral Rules

- Never mutate function arguments. Copy, modify the copy, return it
- `const` by default. `let` only when reassignment is needed, never `var`
- Spread or `structuredClone` over in-place mutation: `{ ...obj, field: newValue }` for shallow updates, `structuredClone(obj)` when you need a true deep copy without structural sharing
- Arrays: `[...arr, item]`, `.filter()`, `.map()` over `.push()`, `.splice()`, `.sort()` on the original. Prefer ES2023 non-mutating methods when available: `.toSorted()`, `.toReversed()`, `.toSpliced()`, `.with(index, value)`
- State transitions produce new state, never mutate the previous one
- Derive values with selectors or computed properties. Never cache derived values as mutable fields
- Framework-internal mutation like Immer or MobX stays at the framework boundary. Everything else treats state as read-only

### Type-Level Enforcement (TypeScript)

Make the compiler catch mutations instead of relying on discipline alone. `readonly` is compile-time only, zero runtime overhead.

- Mark interface and type properties as `readonly` when the value must not change after construction
- Use `as const` on object and array literals whose values are known at declaration time. This makes every property deeply readonly and narrows types to their literal values. Combine with `satisfies` to get both literal inference and type validation: `const ROUTES = { home: '/' } as const satisfies Record<string, string>`
- Function parameters that accept arrays: use `readonly T[]` or `ReadonlyArray<T>`. This removes `.push()`, `.splice()`, `.sort()` from the type signature
- Function parameters that accept objects: use `Readonly<T>` when the function must not modify the input
- Use `ReadonlyMap<K, V>` and `ReadonlySet<T>` for collections used as lookups that must not grow or shrink
- Enable `@typescript-eslint/prefer-readonly-parameter-types` to enforce readonly parameters automatically
- Prefer `readonly` over `Object.freeze()`. `readonly` catches mutations at compile time with no cost. `Object.freeze()` is runtime, shallow only, and has overhead. Reserve `Object.freeze()` for runtime protection at trust boundaries where external code may bypass the type system

## Data Safety

Before writing code that mutates state, answer three questions:

1. **Idempotent?** Can this run twice with the same input without damage? If not, add a guard
2. **Atomic?** Do multiple writes need to succeed or fail together? Use a transaction
3. **Duplicates?** Networks retry. Queues redeliver. Users double-click. Extract a dedup key and use a durable store

See `standards/resilience.md` for patterns and `standards/database.md` for transaction strategies.

## Error Classification

Every `catch` must classify: transient (retry with backoff), permanent (fail immediately), or ambiguous (retry with limit, then permanent). A bare catch that logs and rethrows is a bug.

Also classify by scope:

- **Request-scoped** (non-catastrophic): return an error response to the caller and continue serving. Validation failures, not-found errors, permission denials
- **Process-scoped** (catastrophic): trigger graceful shutdown. Unrecoverable state corruption, exhausted resources, broken invariants that affect all requests

The error handler itself must be self-protecting: if logging fails inside the handler, fall back to stdout directly. A crashing error handler turns every error into an unrecoverable crash.

### Typed Error Returns

In domain logic, prefer returning typed errors over throwing exceptions. A `Result<T, E>` type makes the error channel visible in the function signature. Callers cannot forget to handle the failure path because the type system forces it.

- Use exceptions for truly exceptional, unrecoverable situations: broken invariants, programmer errors, process-scoped failures
- Use Result types for expected domain failures: validation errors, not-found, permission denied, business rule violations
- At framework boundaries (HTTP handlers, CLI entry points, queue consumers), convert Result types to the framework's error mechanism (throw, error response, rejection)
- A hand-rolled discriminated union is sufficient. Libraries like neverthrow or Effect provide chaining utilities if the codebase benefits from pipelines

## Defensive Invariants

Functions that transform data or coordinate side effects must assert their preconditions. Not every function needs assertions, but functions at trust boundaries, data transformation pipelines, and state transitions must validate assumptions before proceeding.

Where to assert:

| Location | What to check |
|----------|--------------|
| Public API entry points | Input ranges, required fields, enum membership |
| After external data arrives | Parsed shape matches expected schema, nulls are absent where required |
| Before irreversible operations | State preconditions that, if violated, would corrupt data |
| After complex transformations | Output satisfies postconditions the caller depends on |

Use the language's native assertion mechanism: `assert` in Python, `console.assert` or throwing on violation in TypeScript, `debug_assert!`/`assert!` in Rust, `if err != nil` patterns in Go. The goal is executable documentation of assumptions, not ceremony.

### Total Functions

A total function returns a valid result for every valid input. A partial function crashes, throws, or returns garbage for some inputs. Prefer total functions.

| Strategy | Technique |
|----------|-----------|
| Narrow the input | Use branded types or discriminated unions so invalid inputs are unrepresentable at the type level |
| Widen the output | Return `T \| undefined` or `Result<T, E>` instead of throwing |
| Validate at construction | Smart constructors that return a Result, making invalid instances impossible to create |
| Exhaust all cases | Handle every variant of a union type. Use `satisfies never` to catch missing branches at compile time |

Partial functions are acceptable after validation at a system boundary. If the API layer proved the array is non-empty, internal functions can assume non-emptiness.

## Analyzability

Write code that automated tools can reason about. Avoid patterns that defeat static analysis, linters, and type checkers.

- Avoid dynamic property access when the set of keys is known. Use typed lookups or maps instead of `obj[someVariable]`
- Avoid `eval`, `Function()`, `exec`, and runtime code generation. Use lookup tables or strategy patterns instead
- Avoid excessive type assertions or casts. If the type system cannot express the relationship, the design likely needs rethinking
- Keep the call graph static. When dynamic dispatch is needed, like plugins or event handlers, constrain it through typed interfaces, not arbitrary function references
- Metaprogramming, like decorators, macros, and code generation, must produce output that is itself analyzable. If a decorator hides control flow that a linter cannot trace, the decorator is a liability

## Comments Policy

**Code should be self-explanatory.** Only add comments for: complex algorithms, non-obvious business rules, workarounds for external issues, doc comments for public APIs.

## Backward Compatibility

- Do not break existing callers, APIs, or config without a plan
- Document breaking changes and migration steps

## Dependencies

1. **Ask permission.** Never add without approval.
2. **Check existing.** Maybe already solved natively.
3. **Evaluate.** Compare the top 3-5 options in the category using a structured table with measurable criteria: maintenance activity (commits in last 6 months), community size (stars, dependents), known vulnerabilities, bundle size, and API quality. Never pick by gut feeling.
4. **Size.** Avoid heavy packages for simple tasks.
5. Pin exact versions. Separate dev dependencies. Commit lockfile.
6. **Pin the package manager.** Different versions produce different lockfiles. Use Corepack, a manifest version field, or CI config to enforce consistency.

## Validation

- **Zod** is the preferred validation library for TypeScript projects
- Validate semantically, not just syntactically: positive monetary values, valid date ranges, enum membership
- Validate both input and output schemas at system boundaries
- **Parse, don't validate**: validation that returns `boolean` is wasteful. The caller still holds untyped data and downstream functions cannot trust it without re-checking. Instead, parse into a typed value. `parseEmail(input: string): Result<Email, ValidationError>` returns a branded `Email` type. After this point, every function that accepts `Email` is guaranteed valid input with zero re-validation. Combine Zod's `.transform()` + `.brand()` to parse and brand in a single step

## File Naming

For domain-driven structure, follow `name-of-content.type.ts`: `user-credentials.service.ts`, `create-order.dto.ts`, `payment-status.enum.ts`. Group by domain context in folders.

## Versions

- Always use the latest stable or LTS version of languages, runtimes, and dependencies
- When a platform has version constraints, use the latest version available on that platform

## Code Examples

Every code snippet in any output must follow all rules. A code example that violates a rule is a defect. If a fix suggestion introduces a violation, the suggestion itself is a review defect.
