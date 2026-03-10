# Code Style

- DRY, SOLID, KISS
- Small functions (< 30 lines)
- Meaningful names
- No magic numbers
- Single export per file
- For functions with many arguments, pass one options object. Return objects.
- File order: main export first, then subcomponents, helpers, static content, types
- Design for change: isolate business logic from the framework. Prefer dependency inversion.
- **Use-case functions**: for multi-step business flows, write a thin orchestration function that contains zero conditionals, zero loops, and zero exception handling. Only flat, sequential calls to domain services. Name it in business language (`calculatePriceCut`, `transferOwnership`), not technical language (`processData`). Use cases serve as a navigation index: any reader can see the full flow, its parameters, and its dependencies at a glance
- **No environment conditionals**: never branch business logic on `NODE_ENV`, `APP_ENV`, or equivalent. Code that runs only in production is code that is never tested. Use configuration externalization for infrastructure differences (log format, connection strings), not code conditionals
- **Domain exception boundary**: services and domain logic throw domain-specific error classes, never framework HTTP exceptions. An exception filter or middleware at the boundary maps domain errors to HTTP responses.
- **Validation infrastructure**: in NestJS projects, register validation globally via interceptor + method decorator, not per-parameter pipes. Controllers should have no validation imports or logic.
- Prefer composition over inheritance
- **No side effects at module level**: module/file scope runs on import. Keep it free of I/O, network calls, global state mutations, and event listener registration. All side effects belong inside explicitly called functions. A module that changes behavior just by being imported is a hidden coupling
- Use braces for all control structures
- **Never swallow errors**: no empty catch; log with context, rethrow or handle
- **No deep nesting**: max 3 levels of indentation. Guard clauses and early returns to flatten control flow
- **Strong typing**: explicit types for parameters, return values, and public interfaces. Never `any`, use `unknown` and narrow. Enable strict mode
- **Enums over string literal unions**: string enums for domain values. They exist at runtime, can be iterated, and are the single source of truth
- **Explicit imports**: import only what you use. Barrel imports (`import * from`) and re-export index files load entire modules, increasing startup time and memory. For libraries you author, provide granular exports so consumers can import individual functions
- **Don't block the request-handling thread**: never run CPU-intensive work (image processing, compression, cryptographic operations on large inputs) or synchronous I/O on the thread that serves requests. Offload to a worker thread, background job, or separate process. A blocked request thread stalls all concurrent requests
- **DI only when needed**: start with direct module imports. Only adopt dependency injection when you genuinely need to swap implementations at runtime or in tests. DI containers add indirection, increase startup time, and make stack traces harder to follow. Most applications never need to swap a real implementation

## TypeScript Type Constructs

| Construct | When to use |
|-----------|------------|
| `interface` | Object shapes: DTOs, props, service contracts. Prefer for public APIs |
| `type` | Unions, intersections, mapped types, conditional types, tuples, function signatures |
| `enum` (string) | Fixed domain values that need runtime existence: statuses, roles, categories |
| `as const` object | Lookup tables with metadata, derive union types from keys/values |

- `interface` for object shapes, `type` for the rest. Do not mix for the same purpose
- Consistency within a codebase. If DTOs use `interface`, all DTOs use `interface`
- Never alias a single primitive with `type`. Use a branded pattern if needed
- Prefer `interface` when either works. Clearer error messages, supports declaration merging

## Immutability

- Never mutate function arguments. Copy, modify the copy, return it
- `const` by default. `let` only when reassignment is needed, never `var`
- Spread or structured clone over in-place mutation: `{ ...obj, field: newValue }`
- Arrays: `[...arr, item]`, `.filter()`, `.map()` over `.push()`, `.splice()`, `.sort()` on the original
- State transitions produce new state, never mutate the previous one
- Derive values with selectors or computed properties. Never cache derived values as mutable fields
- Framework-internal mutation like Immer or MobX stays at the framework boundary. Everything else treats state as read-only

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

## File Naming

For domain-driven structure, follow `name-of-content.type.ts`: `user-credentials.service.ts`, `create-order.dto.ts`, `payment-status.enum.ts`. Group by domain context in folders.

## Versions

- Always use the latest stable or LTS version of languages, runtimes, and dependencies
- When a platform has version constraints, use the latest version available on that platform

## Code Examples

Every code snippet in any output must follow all rules. A code example that violates a rule is a defect. If a fix suggestion introduces a violation, the suggestion itself is a review defect.
