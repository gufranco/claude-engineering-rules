# TypeScript 5.x Patterns

## Resource Management with using / await using

TypeScript 5.2 introduced `using` and `await using` for deterministic resource cleanup via `Symbol.dispose` and `Symbol.asyncDispose`. This replaces `try/finally` for resource management.

```typescript
class DatabaseConnection implements Disposable {
  constructor(private connection: Connection) {}

  query(sql: string): QueryResult {
    return this.connection.query(sql);
  }

  [Symbol.dispose](): void {
    this.connection.close();
  }
}

// Connection is closed when scope exits, even on throw
function getUser(id: string): User {
  using conn = new DatabaseConnection(pool.acquire());
  return conn.query("SELECT * FROM users WHERE id = $1", [id]);
}
```

For async resources, use `await using` with `Symbol.asyncDispose`:

```typescript
async function readConfig(): Promise<Config> {
  await using file = await FileHandle.open("config.json");
  return JSON.parse(await file.readAll());
}
```

| Pattern | Old approach | New approach |
|---------|-------------|-------------|
| Database connection | `try { conn = acquire() } finally { conn.close() }` | `using conn = acquire()` |
| File handle | `try { fh = open() } finally { fh.close() }` | `await using fh = await open()` |
| Lock | `try { lock.acquire() } finally { lock.release() }` | `using guard = lock.acquire()` |
| Transaction | `try { tx.begin() } catch { tx.rollback() } finally { tx.end() }` | `await using tx = await db.transaction()` |

Use `using` for any resource that must be released: connections, locks, file handles, temporary files, timers. The compiler guarantees cleanup runs on scope exit.

## NoInfer<T>

TypeScript 5.4 added `NoInfer<T>` to prevent type widening from fallback parameters. Without it, a default value can widen the inferred type, hiding type errors.

```typescript
// Without NoInfer: defaultValue widens T, hiding mismatches
function getOrDefault<T>(value: T | undefined, defaultValue: T): T {
  return value ?? defaultValue;
}
// No error: T widens to string | number
getOrDefault<string>("hello", 42);

// With NoInfer: defaultValue cannot influence T inference
function getOrDefault<T>(value: T | undefined, defaultValue: NoInfer<T>): T {
  return value ?? defaultValue;
}
// Error: number is not assignable to string
getOrDefault<string>("hello", 42);
```

Use `NoInfer<T>` on parameters that should follow the type, not lead it. Common cases:

| Parameter role | Use NoInfer? |
|---------------|-------------|
| Primary input that determines T | No |
| Default/fallback value | Yes |
| Event handler callback parameter | Yes |
| Comparison value in a generic function | Yes |

## verbatimModuleSyntax

Requires explicit `import type` for type-only imports. Eliminates ambiguity about which imports are erased at runtime.

```typescript
// Error with verbatimModuleSyntax: UserDTO is only used as a type
import { UserService, UserDTO } from "./user";

// Correct: separate type imports
import { UserService } from "./user";
import type { UserDTO } from "./user";

// Also correct: inline type modifier
import { UserService, type UserDTO } from "./user";
```

Enable in `tsconfig.json`:

```json
{
  "compilerOptions": {
    "verbatimModuleSyntax": true
  }
}
```

This replaces the older `importsNotUsedAsValues` and `preserveValueImports` flags. It makes the intent explicit: runtime imports stay, type imports are erased. Bundlers and runtimes can rely on the syntax without type analysis.

## Regex Syntax Checking

TypeScript 5.5 validates regular expression syntax at compile time when the target is ES2018 or later. Invalid regex patterns produce type errors instead of runtime exceptions.

```typescript
// Error at compile time: invalid regex
const pattern = /(?<=\d+)\k<name>/;
//                       ~~~~~~~~ error: Unknown named group

// Correct
const pattern = /(?<name>\d+)-\k<name>/;
```

This catches common regex mistakes: unclosed groups, invalid backreferences, unsupported syntax for the target. Set `target` to ES2018 or later to enable.

## Inferred Type Predicates

TypeScript 5.5 infers type predicates for simple filter callbacks, eliminating the need for explicit type annotations in common narrowing patterns.

```typescript
const items: Array<string | undefined> = ["a", undefined, "b"];

// Before 5.5: result is Array<string | undefined>, filtering does not narrow
const filtered = items.filter((item) => item !== undefined);

// TypeScript 5.5: result is Array<string>, predicate is inferred
const filtered = items.filter((item) => item !== undefined);
```

The compiler infers the type predicate `item is string` from the truthiness check. This works for simple guards:

| Guard pattern | Inferred predicate |
|--------------|--------------------|
| `x !== undefined` | `x is T` where T excludes undefined |
| `x !== null` | `x is T` where T excludes null |
| `x != null` | `x is T` where T excludes null and undefined |
| `typeof x === "string"` | `x is string` |
| `x instanceof Date` | `x is Date` |

For complex guards, explicit type predicates are still needed:

```typescript
function isValidUser(user: unknown): user is User {
  return typeof user === "object" && user !== null && "id" in user;
}
```

## Decorator Metadata

TypeScript 5.2 supports the TC39 decorator metadata proposal. Decorators can attach metadata to classes and members, accessible at runtime through `Symbol.metadata`.

```typescript
function track(context: ClassMethodDecoratorContext): void {
  const metadata = context.metadata as Record<string, string[]>;
  metadata.tracked = [...(metadata.tracked ?? []), String(context.name)];
}

class OrderService {
  @track createOrder(): void { /* ... */ }
  @track cancelOrder(): void { /* ... */ }
}

// Runtime access: OrderService[Symbol.metadata]?.tracked
// ["createOrder", "cancelOrder"]
```

Use decorator metadata for DI registration, validation rules, ORM column definitions, and route registration.

## Isolated Declarations

TypeScript 5.5 introduced `isolatedDeclarations` mode. When enabled, each file must contain enough type information to generate `.d.ts` files without type inference from other files.

Every exported function, variable, and class must have explicit type annotations. The compiler cannot infer return types from implementation details.

```typescript
// Error: return type must be explicit
export function createUser(name: string) {
  return { id: generateId(), name, createdAt: new Date() };
}

// Correct: explicit return type
export function createUser(name: string): User {
  return { id: generateId(), name, createdAt: new Date() };
}
```

Benefits: parallel `.d.ts` generation across files, faster monorepo builds, and enforced explicit public API contracts.

## Strictness Flag Adoption

Enable every new strictness flag on each TypeScript upgrade. The cost of fixing type errors during development is near zero compared to the bugs they prevent.

| Flag | Version | What it catches |
|------|---------|----------------|
| `strict` | 2.3+ | Baseline strict mode, enables all flags below it |
| `noUncheckedIndexedAccess` | 4.1 | Index access on arrays and records returns `T \| undefined` |
| `exactOptionalPropertyTypes` | 4.4 | `undefined` must be explicit, not implicit via `?:` |
| `noPropertyAccessFromIndexSignature` | 4.2 | Forces bracket notation for dynamic keys |
| `noFallthroughCasesInSwitch` | 2.0 | Requires break or return in every case |
| `forceConsistentCasingInFileNames` | 2.0 | Prevents case-mismatch imports on case-insensitive OS |
| `verbatimModuleSyntax` | 5.0 | Requires explicit `import type` |
| `isolatedDeclarations` | 5.5 | Requires explicit types on exports |
| `erasableSyntaxOnly` | 5.8 | Restricts to syntax that can be erased without type info |

Process for each TypeScript upgrade:

1. Update TypeScript version.
2. Check the release notes for new strictness flags.
3. Enable every new flag.
4. Fix all resulting errors. Do not disable the flag.
5. Commit the tsconfig change with the fixes.
