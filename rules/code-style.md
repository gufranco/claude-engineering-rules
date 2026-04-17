# Code Style

## Completeness (MANDATORY)

Always choose the complete implementation. No half-measures, no TODOs, no "leave for later," no shortcuts.

- Tests: write all test cases, all edge cases, all error paths. Never "add tests later"
- Error handling: handle every error path. Never swallow, never punt
- Validation: validate all inputs completely. Never skip "for now"
- Edge cases: handle all of them. Never assume they will not happen
- Documentation: update everything the change affects. Never leave stale docs
- Accessibility: implement fully. Never "a11y pass later"
- Migrations: write both up and down. Never skip the down migration
- Cleanup: remove dead code, unused imports, stale references. Never leave debris
- Seed data: new database models must include seed data for localhost development. Every entity type must have realistic records generated with `@faker-js/faker`. Never hardcode names, emails, or descriptions in seed files. The seed quantity must be configurable via an environment variable (e.g., `SEED_SCALE`)
- Translations: new user-facing strings must be translated into ALL supported locales before delivery. No English-only UI text
- Sorting: every table that displays backend data must support server-side sorting with URL-persisted state

When scope crosses into multi-week rewrites or cross-cutting architectural changes, flag as a separate task. Within declared scope, every aspect must be finished to production quality.

## Fundamentals

- DRY, SOLID, KISS, YAGNI, LoD, CQS, Pit of Success
- Small functions (< 30 lines). Small files (< 500 lines). When a file exceeds 500 lines, extract sections into separate files
- Meaningful names
- No magic numbers or magic strings. Extract any literal used more than once to a named constant. API model names, rate limits, timeouts, thresholds, and config values all belong in a centralized constants file
- Single export per file
- For functions with many arguments, pass one options object. Return objects
- File order: main export first, then subcomponents, helpers, static content, types
- **Functional core, imperative shell**: pure logic with no I/O in the core, side effects pushed to the outermost layer
- **Use-case functions**: for multi-step business flows, write a thin orchestration function with zero conditionals, zero loops, and zero exception handling. Only flat, sequential calls to domain services. Name in business language (`calculatePriceCut`, `transferOwnership`)
- **No environment conditionals**: never branch business logic on `NODE_ENV`, `APP_ENV`, or equivalent. Use configuration externalization for infrastructure differences
- **Remove over guard**: prefer removing an unsupported feature over wrapping it in a conditional. Only guard when the feature is critical and has no cross-platform alternative
- **Domain exception boundary**: services and domain logic throw domain-specific error classes, never framework HTTP exceptions. A filter or middleware at the boundary maps them to HTTP responses
- **Validation infrastructure**: in NestJS projects, register validation globally via interceptor + method decorator, not per-parameter pipes. Controllers must have no validation imports or logic
- **Law of Demeter**: only call methods on direct dependencies. Never chain through transitive objects like `order.getCustomer().getAddress().getCity()`
- Prefer composition over inheritance
- **No side effects at module level**: keep module scope free of I/O, network calls, global state mutations, and event listener registration. All side effects belong inside explicitly called functions. Common violations: `const redis = createClient()` at module level, registering an event listener, starting a timer
- Use braces for all control structures
- **Never swallow errors**: no empty `catch`, no `catch {}`. Every catch must log the error with context (entity ID, operation name) using the project's logger, then either rethrow or return a typed error
- **Fire-and-forget side effects must have error logging**: when using `void promise`, always append `.catch((error: unknown) => logger.error({ err: error }, 'description'))`. A void promise without `.catch()` silently drops errors
- **Never ignore return values**: every non-void return value must be used or explicitly discarded. In TypeScript, enable `@typescript-eslint/no-floating-promises`. In Go, handle every error return. In Rust, never use `let _ =` on a `Result` without justification
- **Use the project logger, never console**: `console.log`, `console.error`, `console.warn`, and `console.info` must not appear in production code. Only exception: Next.js error boundaries (`error.tsx`)
- **No deep nesting**: max 3 levels of indentation. Guard clauses and early returns to flatten control flow
- **Flat control flow**: avoid recursion unless the data structure is inherently recursive. When recursion is necessary, always add a depth limit
- **Strong typing**: explicit types for parameters, return values, and public interfaces. Never `any`, use `unknown` and narrow. When modifying a file that already uses `any`, replace it in the code you touch
- **Enums over string literal unions**: string enums for domain values
- **Explicit imports**: import only what you use. Never barrel imports (`import * from`) or re-export index files
- **Bounded iteration**: every loop and retry must have an explicit upper bound. No `while (true)` without a guaranteed break condition. Polling loops need a timeout. Retry loops need a max attempt count
- **Minimal scope**: declare variables at the smallest scope where they are used
- **Don't block the request-handling thread**: never run CPU-intensive work or synchronous I/O on the request-serving thread. Offload to a worker thread, background job, or separate process
- **Pit of Success**: design APIs so the correct usage is the easiest path. Wrong usage should require deliberate effort
- **DI only when needed**: start with direct module imports. Only adopt a DI container when you genuinely need to swap implementations at runtime or in tests
- **No `Record<string, unknown>` for ORM queries**: use the generated types (`Prisma.WorkOrderWhereInput`, etc.). `Record<string, unknown>` bypasses type safety and hides field renames
- **No raw SQL**: never use raw SQL when the project has an ORM. No exceptions. This includes `$queryRaw`, `$executeRaw`, `$queryRawUnsafe`, `$executeRawUnsafe` in Prisma. The only place SQL is acceptable is migration files. This applies to test files too
- **Service layer for data access**: routers, controllers, and API handlers must never import the ORM directly. All database operations go through service classes

## Prisma Schema Completeness

Every new Prisma model must include these fields and annotations. Missing any is a review-blocking issue.

| Requirement | Rule |
|-------------|------|
| `createdAt` | `DateTime @default(now())` on every model |
| `updatedAt` | `DateTime @updatedAt` on every modifiable model. Append-only models (audit logs, event logs, feed items) are exempt |
| `companyId` index | `@@index([companyId])` on every model with a `companyId` field |
| Compound indexes | `@@index([companyId, status])` and `@@index([companyId, createdAt])` when filtered by status or sorted by date |
| Foreign key indexes | Every `@relation` field needs an `@@index` unless covered by `@@unique` |

Checklist before committing a new model:

1. Does it have `createdAt` and `updatedAt`?
2. Does it have `@@index([companyId])` if it has a `companyId` field?
3. Do all `@relation` fields have indexes?
4. Is the model in the test cleanup order in `test/setup.ts`?
5. Does the seed file create records for this model?

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

- Every variant must share a literal `kind`, `type`, or `tag` discriminant property
- Exhaustive matching is mandatory. Use `satisfies never` in the default branch or a library like ts-pattern with `.exhaustive()`. Adding a new variant must produce compile errors at every unhandled match site
- Avoid boolean blindness: when the caller needs to know WHY, return a discriminated union instead of a boolean
- Prefer discriminated unions over class hierarchies for domain modeling

### Branded Types

```typescript
type Brand<T, B extends string> = T & { readonly __brand: B };
type UserId = Brand<string, 'UserId'>;
type OrderId = Brand<string, 'OrderId'>;
```

- Combine with Zod's `.brand()` for runtime validation and compile-time branding in one step
- Use for: IDs, validated strings (Email, URL), units of measure (Seconds vs Milliseconds), monetary amounts with currency

### Type State Pattern

Encode state machine transitions in the type system. Invalid transitions do not exist in the API.

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
```

- Use when: order workflows, payment processing, document lifecycles, connection states, authentication flows
- Combine with branded types for state identifiers: `DraftOrderId` vs `ShippedOrderId`

## Command-Query Separation

A function either changes state (command, returns void) or returns data (query, no side effects). Never both.

- Commands: return `void` or a `Result` indicating success/failure
- Queries: return data without side effects. Safe to call multiple times
- When you need both, split into two functions
- Exception: stack/queue `pop` operations where removal and retrieval are inherently atomic. Document these cases

## Immutability

Immutable by default, mutable by exception. Code review must reject any `.push()`, `.splice()`, `.sort()`, or `let` that could be `const`.

- Never mutate function arguments. Copy, modify the copy, return it
- `const` by default. `let` only when reassignment is genuinely needed. Never `var`
- Spread or `structuredClone` over in-place mutation
- **`.push()` is banned.** Use spread `[...arr, item]` or `Array.from()`. Exception: `router.push()` from Next.js navigation
- **`.sort()` is banned.** Use `.toSorted()`. If ES2023 not available, spread first: `[...arr].sort()`
- **`let` that could be `const`** is a code review failure
- State transitions produce new state, never mutate the previous one
- Derive values with selectors or computed properties. Never cache derived values as mutable fields
- Framework-internal mutation (Immer, MobX) stays at the framework boundary

### Type-Level Enforcement (TypeScript)

- Mark interface and type properties as `readonly` when the value must not change after construction
- Use `as const` on object and array literals whose values are known at declaration time. Combine with `satisfies`: `const ROUTES = { home: '/' } as const satisfies Record<string, string>`
- Function parameters accepting arrays: use `readonly T[]` or `ReadonlyArray<T>`
- Function parameters accepting objects: use `Readonly<T>` when the function must not modify the input
- Use `ReadonlyMap<K, V>` and `ReadonlySet<T>` for lookup collections
- Enable `@typescript-eslint/prefer-readonly-parameter-types`
- Prefer `readonly` over `Object.freeze()`. Reserve `Object.freeze()` for runtime protection at trust boundaries only

## Delivery Path Consistency

When the same business logic is served through multiple delivery paths (REST, WebSocket, background job, SSE, mobile push), the calculation must be identical across all paths.

**Rule: extract shared calculations into a single function. Every delivery path calls that function. No path reimplements the logic inline.**

| Violation | Consequence |
|-----------|------------|
| REST applies `baseVig + volumeVig`, WebSocket applies only `volumeVig` | Users see different prices depending on delivery path |
| API validates permissions with middleware, background job skips the check | Unauthorized actions succeed via the async path |
| Web formats dates as ISO 8601, mobile push as Unix timestamp | Client-side parsing breaks on one path |

When adding a new delivery path:
1. Find every transformation applied in the existing path
2. Extract any inline transformation into a named, tested function
3. Call that function from both paths
4. Add a test that asserts both paths produce identical output for the same input

## Data Safety

Before writing code that mutates state, answer three questions:

1. **Idempotent?** Can this run twice with the same input without damage? If not, add a guard
2. **Atomic?** Do multiple writes need to succeed or fail together? Use a transaction
3. **Duplicates?** Networks retry. Queues redeliver. Users double-click. Extract a dedup key and use a durable store

## Error Classification

Every `catch` must classify: transient (retry with backoff), permanent (fail immediately), or ambiguous (retry with limit, then permanent). A bare catch that logs and rethrows is a bug.

Classify by scope:
- **Request-scoped** (non-catastrophic): return an error response to the caller and continue serving
- **Process-scoped** (catastrophic): trigger graceful shutdown. Unrecoverable state corruption, exhausted resources, broken invariants

The error handler itself must be self-protecting: if logging fails inside the handler, fall back to stdout directly.

### Typed Error Returns

- Use Result types for expected domain failures: validation errors, not-found, permission denied, business rule violations
- Use exceptions for truly exceptional, unrecoverable situations: broken invariants, programmer errors, process-scoped failures
- At framework boundaries, convert Result types to the framework's error mechanism
- A hand-rolled discriminated union is sufficient. Libraries like neverthrow or Effect provide chaining utilities if the codebase benefits from pipelines

## Defensive Invariants

| Location | What to check |
|----------|--------------|
| Public API entry points | Input ranges, required fields, enum membership |
| After external data arrives | Parsed shape matches expected schema, nulls absent where required |
| Before irreversible operations | State preconditions that, if violated, would corrupt data |
| After complex transformations | Output satisfies postconditions the caller depends on |

### Total Functions

Prefer total functions over partial functions.

| Strategy | Technique |
|----------|-----------|
| Narrow the input | Branded types or discriminated unions so invalid inputs are unrepresentable |
| Widen the output | Return `T \| undefined` or `Result<T, E>` instead of throwing |
| Validate at construction | Smart constructors that return a Result |
| Exhaust all cases | Use `satisfies never` to catch missing branches at compile time |

## Analyzability

- Avoid dynamic property access when the set of keys is known
- Avoid `eval`, `Function()`, `exec`, and runtime code generation
- Avoid excessive type assertions or casts
- Keep the call graph static. Constrain dynamic dispatch through typed interfaces
- Metaprogramming must produce output that is itself analyzable

## Comments Policy

**Code should be self-explanatory.** Only add comments for: complex algorithms, non-obvious business rules, workarounds for external issues, doc comments for public APIs.

## Backward Compatibility

- Do not break existing callers, APIs, or config without a plan
- Document breaking changes and migration steps

## Dependencies

1. **Ask permission.** Never add without approval
2. **Check existing.** Maybe already solved natively
3. **Evaluate.** Compare the top 3-5 options using a structured table: maintenance activity (commits last 6 months), community size (stars, dependents), known vulnerabilities, bundle size, API quality. Never pick by gut feeling
4. **Size.** Avoid heavy packages for simple tasks
5. Pin exact versions. Separate dev dependencies. Commit lockfile
6. **Pin the package manager.** Use Corepack, a manifest version field, or CI config to enforce consistency

## Validation

- **Zod** is the preferred validation library for TypeScript projects
- Validate semantically, not just syntactically: positive monetary values, valid date ranges, enum membership
- Validate both input and output schemas at system boundaries
- **Parse, don't validate**: return a typed value, not a boolean. `parseEmail(input: string): Result<Email, ValidationError>` — after parsing, every downstream function accepts `Email` with zero re-validation. Combine Zod's `.transform()` + `.brand()` to parse and brand in one step
- **String ID fields must reject empty strings**: every required `z.string()` field representing an identifier must have `.min(1)`. Optional ID fields use `z.string().min(1).optional()`
- **Monetary and quantity fields must be positive**: `z.number().positive()` for any field representing money, counts, ratings, or quantities

## File Naming

Follow `name-of-content.type.ts`: `user-credentials.service.ts`, `create-order.dto.ts`, `payment-status.enum.ts`. Group by domain context in folders.

## Versions

- Always use the latest stable or LTS version of languages, runtimes, and dependencies
- When a platform has version constraints, use the latest version available on that platform

## Maximum Compiler and Checker Strictness

Every project's compiler, type checker, and linter must be configured at the highest strictness level the toolchain supports.

| Language | Requirement |
|----------|-------------|
| TypeScript | `"strict": true` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`, `noFallthroughCasesInSwitch`, `forceConsistentCasingInFileNames`, `verbatimModuleSyntax`. Enable every new strictness flag added to TypeScript |
| Go | `go vet` plus `staticcheck` or `golangci-lint` with all relevant linters enabled |
| Rust | `#![deny(warnings)]` in `lib.rs`/`main.rs`. `clippy::pedantic` enabled in CI |
| Python | `mypy --strict` or `pyright` in strict mode. `ruff` with all applicable rule sets |
| Java/Kotlin | `-Xlint:all` for javac. `-Werror` to treat warnings as errors |

- When creating a new project, configure maximum strictness from the start
- When joining an existing project, verify the strictness configuration. If flags are missing, add them and fix the resulting errors in the same PR
- Never lower strictness to make code compile. Fix the code instead
- When a new strictness flag becomes available in a toolchain update, enable it
- Document any flag intentionally left disabled with the specific reason in the config file

For Node.js projects, `target` and `module`/`moduleResolution` must match the runtime version. Use the `@tsconfig/node{version}/tsconfig.json` base or set equivalent values manually.

## Zero Warnings

Apply `checklists/checklist.md` category 17. Zero tolerance for compiler, linter, type checker, build, test runner, and runtime warnings. No suppression without documented justification.

## Removal Safety

Before removing or renaming any resource, grep the entire codebase first. Check imports, string references, and dynamic access patterns.

| Resource removed | Where to check |
|-----------------|---------------|
| Function or export | All imports, barrel re-exports, test files |
| File or module | All import paths, dynamic imports, config references |
| API route or endpoint | All `fetch()`, `axios`, `trpc`, `href`, `action` attributes |
| Database column or model | Prisma schema, services, seed files, migration scripts |
| Environment variable | `.env.example`, CI/CD, Docker, Terraform, all `process.env` reads |
| Translation key | All `t('key')`, `t.raw('key')`, message JSON files |
| CSS class or design token | All `className`, Tailwind config, component files |
| Package dependency | All imports from that package across `src/` and `tests/` |

A removal without a consumer search is a latent runtime error.

## Date and Time Handling

Never use raw `Date` methods for formatting, parsing, comparison, or arithmetic.

| Raw Date pattern | Preferred replacement |
|-----------------|----------------------|
| `new Date().getFullYear()` | `getYear(new Date())` from date-fns |
| `date.toISOString()` | `formatISO(date)` from date-fns |
| `new Date(isoString)` | `parseISO(isoString)` from date-fns |
| `dateA < dateB` | `isBefore(dateA, dateB)` from date-fns |
| `new Date(d.setMonth(...))` | `subMonths(d, n)` from date-fns |
| `date.toLocaleDateString()` | `format(date, pattern)` from date-fns |

- `new Date()` for creating a timestamp to pass to a database ORM is acceptable
- For TypeScript projects, `date-fns` is the preferred library
- All date formatting must respect user locale or configurable format preferences, never hardcode a single format
- Every `format()` call that renders user-visible text must receive the dynamic locale from the app's locale context, never a hardcoded locale import

## Locale-Aware Components

Calendars, date pickers, and any locale-sensitive component must bind to the app's dynamic locale. Never hardcode a single locale.

- Import all supported locales (e.g., `enUS`, `ptBR`, `es` from `date-fns/locale`)
- Use the app's locale hook (e.g., `useLocale()` from `next-intl`) to select the active locale at runtime
- Pass the resolved locale to the component's `locale`, `culture`, or equivalent prop
- Test every locale-aware component in at least two locales

## i18n Accent and Diacritical Marks

Translation files must use correct diacritical marks. Missing accents are bugs.

| Language | Common errors | Correct form |
|----------|--------------|-------------|
| Portuguese | `cao` endings | `ção` (ação, função, configuração) |
| Portuguese | `coes` endings | `ções` (ações, informações, notificações) |
| Portuguese | Missing accents | título, código, número, usuário, técnico, horário, relatório |
| Spanish | `cion` endings | `ción` (acción, información, configuración) |
| Spanish | Wrong plural accent | `ciones` NOT `ciónes` (acciones, notificaciones, funciones) |
| Spanish | Missing accents | página, código, número, técnico, período |

Run accent verification on every translation file change. Automated tests must catch these patterns.

## Destructive Action Confirmation

Every single-click action that deletes, cancels, or significantly alters a record must show a confirmation dialog before executing:

- Delete buttons
- Status changes (approve, reject, cancel, archive)
- Toggle switches (activate/deactivate)
- Revoke actions (API keys, access tokens)
- Bulk operations

Form submissions where the user deliberately filled fields do not need confirmation.

Never use `confirm()` or `window.confirm()`. Use the framework's dialog component (AlertDialog in shadcn/ui, Modal in other UI libraries).

## Database Connection Pooling

Every service that connects to a relational database must use a connection pool.

**Pool sizing formula:** `(CPU_COUNT * 2) + 1` connections per process.

- Configure `max`, `min`, and `acquire_timeout` on every pool. Missing `acquire_timeout` causes requests to queue indefinitely when the pool is exhausted
- For Prisma: set `connection_limit` in the datasource URL and use `directUrl` for migrations. Example: `postgresql://...?connection_limit=9&pool_timeout=10`
- For PgBouncer in transaction mode: set `server_pool_size` to the formula value
- Never open a connection at module level. Lazy-initialize inside the first request handler or a dedicated connect function

## Rate Limiting Algorithm Selection

| Algorithm | Behavior | When to use |
|-----------|----------|-------------|
| Token bucket | Allows short bursts up to bucket capacity, then enforces average rate | Public APIs where occasional bursts are acceptable |
| Sliding window log | Exact rate enforcement, no burst allowance | Financial transactions, auth endpoints |
| Fixed window counter | Simple, low memory, allows 2x burst at window boundary | Internal APIs, non-critical endpoints |
| Sliding window counter | Approximates log accuracy at lower memory cost | General purpose API rate limiting |

- Token bucket is the default for most REST APIs
- Sliding window log is mandatory for auth endpoints. A fixed window lets an attacker send 2x the limit by straddling the window boundary
- Store counters in Redis with TTL set to the window duration. Never store in application memory
- Always respond with `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` headers
- Set separate limits per API key tier: free, standard, enterprise. Enforce at the gateway or middleware layer

## LLM Output Trust Boundary

Treat LLM output as untrusted external input.

- Validate format and shape of all LLM-generated values before writing to the database
- Sanitize LLM output before inserting into vector databases to prevent stored prompt injection
- Allowlist URLs before server-side fetching of LLM-generated URLs to prevent SSRF
- Verify tool output shape matches expected schema before acting on it
- Never store raw LLM output in user-visible fields without sanitization

## TypeScript 5.x Patterns

- Use `using` / `await using` for resource management instead of manual try/finally. Implement `Symbol.dispose` / `Symbol.asyncDispose` on classes that manage connections, file handles, or sessions
- Use `NoInfer<T>` on fallback parameters in generic functions to prevent type widening from the default value
- Enable `verbatimModuleSyntax` in all new projects. Require explicit `import type` declarations
- Enable every new strictness flag when upgrading TypeScript versions

## Bisect-Friendly Commits

- Separate rename/move operations from behavior changes
- Separate test infrastructure from test implementations
- Each commit must independently compile and pass tests
- Never mix formatting changes with logic changes

## Code Examples

Every code snippet in any output must follow all rules. A code example that violates a rule is a defect. If a fix suggestion introduces a violation, the suggestion itself is a review defect.
