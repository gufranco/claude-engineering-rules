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

function getUser(id: string): User {
  using conn = new DatabaseConnection(pool.acquire());
  return conn.query("SELECT * FROM users WHERE id = $1", [id]);
}
```

The connection in `getUser` closes when the scope exits, even on a throw.

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

**Without `NoInfer`:** the fallback joins inference, so `C` widens to `"red" | "yellow" | "green" | "blue"` and the call compiles with no error.

```typescript
function createStreetLight<C extends string>(colors: readonly C[], defaultColor: C): C {
  return colors.includes(defaultColor) ? defaultColor : colors[0] ?? defaultColor;
}

createStreetLight(["red", "yellow", "green"], "blue");
```

**With `NoInfer`:** the fallback cannot influence `C`, so the same call fails because `"blue"` is not assignable to `"red" | "yellow" | "green"`.

```typescript
function createStreetLight<C extends string>(colors: readonly C[], defaultColor: NoInfer<C>): C {
  return colors.includes(defaultColor) ? defaultColor : colors[0] ?? defaultColor;
}

createStreetLight(["red", "yellow", "green"], "blue");
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

**Error with `verbatimModuleSyntax`:** `UserDTO` is only used as a type.

```typescript
import { UserService, UserDTO } from "./user";
```

**Correct, separate type imports:**

```typescript
import { UserService } from "./user";
import type { UserDTO } from "./user";
```

**Also correct, inline type modifier:**

```typescript
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

**Compile-time error:** the backreference `\k<name>` points at a group that does not exist, so the compiler reports an unknown named group.

```typescript
const pattern = /(?<=\d+)\k<name>/;
```

**Correct:**

```typescript
const pattern = /(?<name>\d+)-\k<name>/;
```

This catches common regex mistakes: unclosed groups, invalid backreferences, unsupported syntax for the target. Set `target` to ES2018 or later to enable.

## Inferred Type Predicates

TypeScript 5.5 infers type predicates for simple filter callbacks, eliminating the need for explicit type annotations in common narrowing patterns.

```typescript
const items: Array<string | undefined> = ["a", undefined, "b"];
const filtered = items.filter((item) => item !== undefined);
```

Before 5.5, `filtered` is `Array<string | undefined>` because filtering does not narrow. From 5.5, `filtered` is `Array<string>` because the predicate is inferred.

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
  @track createOrder(): void {
    orderEvents.emit("created");
  }

  @track cancelOrder(): void {
    orderEvents.emit("cancelled");
  }
}

const trackedMethods = OrderService[Symbol.metadata]?.tracked;
```

At runtime, `trackedMethods` is `["createOrder", "cancelOrder"]`.

Use decorator metadata for DI registration, validation rules, ORM column definitions, and route registration.

## Isolated Declarations

TypeScript 5.5 introduced `isolatedDeclarations` mode. When enabled, each file must contain enough type information to generate `.d.ts` files without type inference from other files.

Every exported function, variable, and class must have explicit type annotations. The compiler cannot infer return types from implementation details.

**Error:** the return type must be explicit.

```typescript
export function createUser(name: string) {
  return { id: generateId(), name, createdAt: new Date() };
}
```

**Correct, explicit return type:**

```typescript
export function createUser(name: string): User {
  return { id: generateId(), name, createdAt: new Date() };
}
```

Benefits: parallel `.d.ts` generation across files, faster monorepo builds, and enforced explicit public API contracts.

## Strictness Flag Adoption

Enable every new strictness flag on each TypeScript upgrade. The cost of fixing type errors during development is near zero compared to the bugs they prevent.

| Flag | Version | What it catches |
|------|---------|----------------|
| `strict` | 2.3+ | Baseline strict family, such as `strictNullChecks` and `noImplicitAny`. It enables none of the flags below, so set each one explicitly |
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

## ES2024+ and ES2026 Built-ins

When `target` and `lib` include the edition named in each heading below, prefer non-mutating standard-library methods over polyfills, custom helpers, and old mutation-based idioms. The mutation-method-blocker hook (`~/.claude/hooks/mutation-method-blocker.py`) flags the mutating equivalents and points at the replacements below.

### Set composition (ES2025)

Set instances expose seven new composition methods. None mutate the receiver; each returns a new Set. Use them instead of building union/intersection logic by hand.

```typescript
const evens = new Set([2, 4, 6]);
const squares = new Set([1, 4, 9, 16]);

const both = evens.intersection(squares);
const either = evens.union(squares);
const onlyEvens = evens.difference(squares);
const symDiff = evens.symmetricDifference(squares);
const isSubset = new Set([2, 4]).isSubsetOf(evens);
const isSupset = evens.isSupersetOf(new Set([2, 4]));
const disjoint = evens.isDisjointFrom(new Set([7, 9]));
```

| Binding | Value |
|---------|-------|
| `both` | `{4}` |
| `either` | `{2, 4, 6, 1, 9, 16}` |
| `onlyEvens` | `{2, 6}` |
| `symDiff` | `{2, 6, 1, 9, 16}` |
| `isSubset` | `true` |
| `isSupset` | `true` |
| `disjoint` | `true` |

When the hook flags `set.add(v)` or `set.delete(v)`, prefer `set.union(new Set([v]))` and `set.difference(new Set([v]))` over `new Set([...set, v])` for clarity.

### Iterator helpers (ES2025)

Iterator instances now compose lazily: `map`, `filter`, `take`, `drop`, `flatMap`, `forEach`, `toArray`, `reduce`, `some`, `every`, `find`. Calls do not allocate intermediate arrays.

```typescript
const tripled = numbers.values()
  .map((n) => n * 3)
  .filter((n) => n > 5)
  .take(3)
  .toArray();
```

Use iterator helpers instead of `Array.from(generator).map(...).filter(...)` chains. The lazy chain skips the intermediate array allocation entirely.

### Object.groupBy and Map.groupBy (ES2024)

Static methods on `Object` and `Map` for grouping iterables by a discriminator function.

```typescript
const grouped = Object.groupBy([1, 2, 3, 4, 5], (n) =>
  n % 2 === 0 ? 'even' : 'odd',
);

const groupedMap = Map.groupBy(items, (item) => item.category);
```

`grouped` is `{ even: [2, 4], odd: [1, 3, 5] }`.

`Object.groupBy` returns a null-prototype object. Use `Map.groupBy` when keys are not strings or when prototype-pollution safety is required.

### Promise.withResolvers (ES2024) and Promise.try (ES2025)

```typescript
const { promise, resolve, reject } = Promise.withResolvers<number>();

const safe = await Promise.try(() => maybeThrowingFunction());
```

`Promise.withResolvers` is the modern replacement for the manual `let resolve, reject; const p = new Promise(...)` dance. `Promise.try` wraps synchronous and asynchronous functions in a single Promise so callers do not need to remember whether the callee throws synchronously or returns a rejected promise.

### Array.fromAsync (Stage 4)

Builds an array from an async iterable.

```typescript
const collected = await Array.fromAsync(asyncStream);
```

### RegExp.escape (ES2025)

Escapes a string for safe use inside a regex literal.

```typescript
const pattern = new RegExp(RegExp.escape(userInput));
```

Replaces hand-rolled escape helpers and inline `replace(/[.*+?^${}()|[\]\\]/g, '\\$&')` patterns.

### Atomics.pause and Error.isError (Stage 4)

```typescript
Atomics.pause();

if (Error.isError(value)) {
  logger.error({ err: value }, 'operation failed');
}
```

`Atomics.pause` hints to the CPU during a spin-wait. Inside the `Error.isError` branch, `value` is narrowed to `Error`.

`Error.isError` survives realm boundaries; prefer it over `instanceof Error` in worker, iframe, or vm contexts.

### Float16Array (ES2025)

The 12th TypedArray. Same allocation and slicing semantics as `Float32Array`, half the byte width. Useful for ML and graphics buffers.

```typescript
const halfPrecision = new Float16Array(1024);
```

### Temporal API (ES2026, Stage 4)

Temporal reached Stage 4 on 2026-03-11 and ships natively in Chrome 144+, Firefox 139+, and Edge 144+. Use a polyfill like `@js-temporal/polyfill` or `temporal-polyfill` on older runtimes.

```typescript
import { Temporal } from '@js-temporal/polyfill';

const start = Temporal.PlainDate.from('2026-01-01');
const next = start.with({ month: 2 });
const later = start.add({ days: 7 });
const dur = Temporal.Duration.from({ hours: 1, minutes: 30 });
```

Every Temporal value is immutable. Methods like `add`, `subtract`, `with`, `until`, `since`, and `round` return a new value. The mutation hook recognizes Temporal usage and switches its date-setter fix suggestions from date-fns to Temporal.PlainDate when Temporal is detected in the file.

When introducing Temporal in a new module, prefer it over `Date` and over date-fns. Use date-fns only when interop with a legacy Date-based API is required.

## Platform APIs

The section above covers language built-ins. This one covers the layer underneath: APIs the runtime and the browser already implement. Current Node, Deno, Bun, Cloudflare Workers, and every current browser ship them, so the same code runs unchanged across all of them.

Reach for the platform API first. Hand-rolling an equivalent produces more code to review and reintroduces defect classes the platform already closed.

Two caveats before the table. The newer entries have higher runtime floors than the rest, `AbortSignal.any` and `URL.canParse` most of all, so check the floor for the specific runtime the project targets rather than assuming the whole table lands together. And `crypto.randomUUID` and `crypto.subtle` require a secure context in browsers, meaning HTTPS or localhost.

### Replacement table

| Task | Hand-rolled default | Platform API | Defect class it removes |
|------|--------------------|--------------|-------------------------|
| Read query parameters | Split on `&` and `=`, assign into a plain object | `new URL(raw).searchParams` | Prototype pollution. Assigning a `__proto__` key into `{}` mutates the prototype chain. `URLSearchParams` stores entries internally and is immune |
| Build a query string | Concatenate and call `encodeURIComponent` per field | `new URLSearchParams(record).toString()` | Missed or double encoding on any field the author forgets |
| Validate a URL | `try { new URL(s) } catch { }` | `URL.canParse(s)` | Control flow through exceptions for an expected input case |
| Read every form field | One `useState` and one `onChange` per field | `new FormData(form)` | State drift between the DOM and the component. Cost stays flat as fields are added |
| Convert form data to an object | Loop and assign | `Object.fromEntries(formData)` | Same prototype-pollution surface as manual query parsing |
| Time out a request | `setTimeout` paired with an `AbortController` | `AbortSignal.timeout(ms)` | Leaked timers. A manual pair leaks whenever an early return skips `clearTimeout` |
| Cancel on any of several conditions | Track controllers and abort each by hand | `AbortSignal.any([a, b])` | Missed cancellation paths when one source is forgotten |
| Remove event listeners on teardown | Keep a handler reference, call `removeEventListener` | Pass `{ signal }` to `addEventListener`, then abort once | Listener leaks from a mismatched or unreachable handler reference |
| Run independent work in parallel | `Promise.all` plus per-item error flags | `Promise.allSettled` | One rejection discarding the results that did succeed |
| Take the first success | Race with manual bookkeeping | `Promise.any` | Treating the first rejection as the outcome |
| Deep copy a value | Recursive clone helper, or `JSON.parse(JSON.stringify(x))` | `structuredClone(x)` | Silent loss of `Date`, `Map`, `Set`, `BigInt`, and cyclic references |
| Generate an identifier | Hand-rolled random string | `crypto.randomUUID()` | Weak entropy and collisions |
| Hash a value | A hashing dependency | `crypto.subtle.digest` | An added dependency for something already present |
| Text to bytes and back | Manual char-code loops | `TextEncoder`, `TextDecoder` | Broken handling of multi-byte and astral-plane characters |
| Manipulate headers | Plain object with ad-hoc casing | `new Headers(init)` | Case-sensitivity bugs. HTTP header names are case-insensitive and `Headers` normalizes them |

### Worked examples

```typescript
const params = new URL(request.url).searchParams;
const page = Number(params.get('page') ?? '1');
const tags = params.getAll('tag');
```

```typescript
const response = await fetch(endpoint, { signal: AbortSignal.timeout(5000) });
```

```typescript
function handleSubmit(event: SubmitEvent): void {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const values = Object.fromEntries(new FormData(form));
}
```

`Object.fromEntries` keeps only the last value for a repeated field name. When a field can repeat, such as a multi-select or a checkbox group, read it with `formData.getAll(name)` instead.

```typescript
const results = await Promise.allSettled(ids.map((id) => load(id)));
const loaded = results.filter((r) => r.status === 'fulfilled').map((r) => r.value);
const failures = results.filter((r) => r.status === 'rejected');
```

```typescript
const controller = new AbortController();
element.addEventListener('scroll', onScroll, { signal: controller.signal });
element.addEventListener('resize', onResize, { signal: controller.signal });
controller.abort();
```

One `abort()` removes every listener registered with that signal. No handler references to store, and no way to leak one by mismatching the function identity passed to `removeEventListener`.

### When hand-rolling is correct

The directive is platform-first, not platform-only. Write the custom version when one of these holds, and say which one in the code review:

- The format is one the API does not model. `URLSearchParams` handles flat key-value pairs; deeply nested bracket notation needs a real parser.
- A benchmark shows the platform API is the bottleneck. A measured number, not a suspicion. See [`performance.md`](performance.md).
- The target runtime lacks the API and a polyfill costs more than the custom code.
- The platform API's behavior is close but wrong for the case, and the difference is stated. `structuredClone` throws on functions and DOM nodes, so a structure holding either needs different handling.

Absent one of those, the platform API wins.

## Related Standards

- [`frontend.md`](frontend.md): Frontend Design
- [`performance.md`](performance.md): benchmark thresholds for the hot-path carve-out above
- [`typescript-immutability.md`](typescript-immutability.md) "ES2024+ Fix Suggestions" lists every mutating call and its non-mutating replacement.
- [`../checklists/checklist.md`](../checklists/checklist.md) category 4 carries the `Promise.all` and `Promise.allSettled` check from the concurrency-safety angle.
