# TypeScript Immutability

Immutable by default, mutable by exception. Every value starts as readonly. Mutability requires an explicit decision, not the other way around. This rule is absolute. Code review must reject any `.push()`, `.splice()`, `.sort()`, or `let` that could be `const`.

## Behavioral Rules

- Never mutate function arguments. Copy, modify the copy, return it
- `const` by default. `let` only when reassignment is genuinely needed (loop counters, accumulators that cannot be expressed functionally). Never `var`
- Spread or `structuredClone` over in-place mutation: `{ ...obj, field: newValue }` for shallow updates, `structuredClone(obj)` when you need a true deep copy without structural sharing
- Arrays: `[...arr, item]`, `.filter()`, `.map()`, `reduce()` over `.push()`, `.splice()`, `.sort()` on the original. Prefer ES2023 non-mutating methods when available: `.toSorted()`, `.toReversed()`, `.toSpliced()`, `.with(index, value)`
- **`.push()` is banned.** Use spread `[...arr, item]` or `Array.from()`. The only exception is `router.push()` from Next.js/framework navigation, which is not an array mutation
- **`.sort()` is banned.** Use `.toSorted()`. If the target does not support ES2023, spread first: `[...arr].sort()`
- **`let` that could be `const`** is a code review failure. Use ternary, lookup maps, or `??` to avoid `let` with conditional assignment
- State transitions produce new state, never mutate the previous one
- Derive values with selectors or computed properties. Never cache derived values as mutable fields
- Framework-internal mutation like Immer or MobX stays at the framework boundary. Everything else treats state as read-only

## Type-Level Enforcement

Make the compiler catch mutations instead of relying on discipline alone. `readonly` is compile-time only, zero runtime overhead.

- Mark interface and type properties as `readonly` when the value must not change after construction
- Use `as const` on object and array literals whose values are known at declaration time. This makes every property deeply readonly and narrows types to their literal values. Combine with `satisfies` to get both literal inference and type validation: `const ROUTES = { home: '/' } as const satisfies Record<string, string>`
- Function parameters that accept arrays: use `readonly T[]` or `ReadonlyArray<T>`. This removes `.push()`, `.splice()`, `.sort()` from the type signature
- Function parameters that accept objects: use `Readonly<T>` when the function must not modify the input
- Use `ReadonlyMap<K, V>` and `ReadonlySet<T>` for collections used as lookups that must not grow or shrink
- Enable `@typescript-eslint/prefer-readonly-parameter-types` to enforce readonly parameters automatically
- Prefer `readonly` over `Object.freeze()`. `readonly` catches mutations at compile time with no cost. `Object.freeze()` is runtime, shallow only, and has overhead. Reserve `Object.freeze()` for runtime protection at trust boundaries where external code may bypass the type system

## Mutation Surface

Every name below is rejected by `~/.claude/hooks/mutation-method-blocker.py` unless the file matches an auto-allowed scope (see "Auto-allowed scopes" further down). The hook covers 90+ patterns across 16 categories with stable codes MMB001-MMB092.

| Category | Methods or operators |
|----------|----------------------|
| Array prototype (9) | `push`, `pop`, `shift`, `unshift`, `splice`, `sort`, `reverse`, `fill`, `copyWithin` |
| Bracket-string dispatch (1) | `arr['push'](...)`, `arr["sort"](...)`, etc. |
| Collection mutation (6) | `Map.set`, `Map.delete`, `Map.clear`, `Set.add`, `Set.delete`, `Set.clear` (plus WeakMap, WeakSet) |
| TypedArray prototype (5) | `set`, `fill`, `sort`, `reverse`, `copyWithin` (auto-allowed in hot paths) |
| Property assignment (5) | `obj.prop = v`, `obj['prop'] = v`, `arr[i] = v`, compound (`+=`, 14 variants), increment (`++`, `--`) |
| Object utility (8) | `Object.assign(target, ...)` with non-fresh target, `defineProperty`, `defineProperties`, `setPrototypeOf`, `Reflect.set`, `Reflect.deleteProperty`, `Reflect.defineProperty`, `Reflect.setPrototypeOf` |
| `delete` operator (1) | `delete obj.prop`, `delete obj[key]`, `delete arr[i]` |
| Date prototype setters (16) | `setDate`, `setFullYear`, `setHours`, `setMilliseconds`, `setMinutes`, `setMonth`, `setSeconds`, `setTime`, `setYear`, `setUTCDate`, `setUTCFullYear`, `setUTCHours`, `setUTCMilliseconds`, `setUTCMinutes`, `setUTCMonth`, `setUTCSeconds` |
| Global mutation (1 family) | Direct assignment to `globalThis.*` or `process.env.*` (`window.*` and `self.*` are out of scope: see DOM and Web API Stance) |
| Parameter reassignment | Reassigning a function parameter (allowlisted: `acc`, `accumulator`, `result`, `ctx`, `context`, `req`, `request`, `res`, `response`, `next`, `e`, `event`, `draft`) |
| `let` could be `const` | `let` declarations never reassigned in the file (full-file Write payloads only) |
| Binary buffer writes (12) | `DataView.set{Int,Uint,Float}{8,16,32,64}`, `setBigInt64`, `setBigUint64`; two-arg `Uint8Array.prototype.set(source, offset)` is a separate detector targeting offset-bug-prone calls (hot paths auto-allowed) |
| Shared memory (8) | `Atomics.{store, exchange, compareExchange, add, sub, and, or, xor}` on SharedArrayBuffer views (info severity; `Atomics.load`, `wait`, `notify`, `pause` are non-mutating) |
| WebAssembly (1) | `WebAssembly.Memory.prototype.grow` (legitimate but every existing view over `memory.buffer` is invalidated and must be recreated) |
| Proxy traps (4) | Handler `set`, `deleteProperty`, `defineProperty`, `setPrototypeOf` inside `new Proxy({}, handler)` or `Proxy.revocable` |
| WeakRef chains (1) | `weakRef.deref()?.{push,pop,shift,splice,sort,reverse,set,delete,add,clear}` (GC may collect target between deref and call) |
| FinalizationRegistry (1) | `new FinalizationRegistry(callback)` (info severity; the callback runs at unpredictable GC moments and must not mutate shared state) |

## DOM and Web API Stance

The hook governs JS values, not Web platform side-effect APIs. The boundary is consistent:

| API | Status | Reason |
|-----|--------|--------|
| DOM nodes (`element.innerHTML`, `element.textContent`, `element.className`, `element.style.*`, `element.classList.*`, `element.dataset.*`, `element.scrollTop`, `element.disabled`, `shadowRoot.*`) | Out of scope | The DOM is inherently mutating. Flagging would generate noise on every render. Use `eslint-plugin-jsx-a11y` and `eslint-plugin-react` for DOM hygiene |
| `document.*` and `window.*` property writes | Out of scope | Same as DOM nodes |
| IndexedDB cursor / transaction mutations (`store.put`, `store.add`, `store.delete`, `store.clear`, `cursor.update`, `cursor.delete`) | Out of scope | The IndexedDB API is inherently mutating; it is a persistence layer, not a JS value |
| Web Storage (`localStorage.setItem`, `sessionStorage.setItem`, `*.removeItem`, `*.clear`) | Out of scope | Side-effect API. The "no module-level side effects" rule governs placement, not the mutation hook |
| `URLSearchParams.{append,set,delete,sort}` | **In scope** | Plain JS value with non-mutating fresh-instance alternative: `new URLSearchParams([...params, [k, v]])` |
| `Headers.{append,set,delete}` | **In scope** | Plain JS value with non-mutating fresh-instance alternative: `new Headers([...headers, [k, v]])` |
| `FormData.{append,set,delete}` | **In scope** | Plain JS value with non-mutating fresh-instance alternative: `Array.from(form.entries()).reduce((fd, [k, v]) => { fd.append(k, v); return fd }, new FormData())` (uses fresh-instance reducer initializer; mark with `@allow-mutation` for XHR.send pointer-stability cases) |

The principle: if the API mutates a JavaScript value that has a feasible non-mutating alternative via fresh-instance construction, the hook flags it. If the API mutates external state (DOM, persistence, storage) that has no in-memory equivalent, the hook is silent.

## Withdrawn Proposals

The Records and Tuples proposal (deeply immutable `#{}` records and `#[]` tuples with structural equality) was withdrawn from TC39 on 2025-04-14 and the spec repository was archived on 2025-04-15. Its successor, the Composites proposal, is at Stage 1 and not yet usable. Treat any code that still references `#{}` or `#[]` as legacy: rewrite using plain object/array literals plus `as const` and the `readonly` ladder. The mutation hook does not recognize these withdrawn syntaxes; if a parser fails on a `#{}` literal the policy default (allow) applies and a warning is logged.

## ES2024+ Fix Suggestions

Modern replacements are organized by category. ES2023 introduced the change-by-copy array methods. ES2024 added Set composition methods, iterator helpers, grouping primitives, `Promise.withResolvers`, and `Float16Array`. ES2025 / Stage 4 brings Temporal. None of the replacements below mutate the receiver.

### Arrays

| Mutating call | Non-mutating replacement | Standard |
|---------------|--------------------------|----------|
| `arr.push(item)` | `[...arr, item]` | ES2015 spread |
| `arr.pop()` | `arr.slice(0, -1)` (and read `arr.at(-1)` separately) | ES2022 `at` |
| `arr.shift()` | `arr.slice(1)` (and read `arr[0]` separately) | ES5 |
| `arr.unshift(item)` | `[item, ...arr]` | ES2015 spread |
| `arr.splice(i, n, item)` | `arr.toSpliced(i, n, item)` | ES2023 |
| `arr.sort(cmp)` | `arr.toSorted(cmp)` | ES2023 |
| `arr.reverse()` | `arr.toReversed()` | ES2023 |
| `arr[i] = value` | `arr.with(i, value)` | ES2023 |
| `arr.fill(v)` | `Array.from({ length: arr.length }, () => v)` | ES2015 |
| `arr.copyWithin(...)` | `arr.map((v, i) => /* explicit index map */)` | ES5 |
| `arr.reduce((acc, x) => { acc[k(x)].push(x); return acc; }, {})` | `Object.groupBy(arr, k)` or `Map.groupBy(arr, k)` | ES2024 |

### Objects

| Mutating call | Non-mutating replacement | Standard |
|---------------|--------------------------|----------|
| `Object.assign(target, src)` | `{ ...target, ...src }` or `Object.assign({}, target, src)` | ES2018 spread |
| `obj.prop = v` | `{ ...obj, prop: v }` | ES2018 spread |
| `delete obj.prop` | `const { prop, ...rest } = obj` | ES2018 rest |
| `Object.defineProperty(o, k, d)` | Declare in the type and the literal; for dynamic keys `{ ...o, [k]: v }` | ES5 |
| `Object.setPrototypeOf(o, p)` | Class inheritance, factory function, or `Object.create(p, descriptors)` | ES2015 |

### Maps and Sets

| Mutating call | Non-mutating replacement | Standard |
|---------------|--------------------------|----------|
| `map.set(k, v)` | `new Map([...map, [k, v]])` | ES2015 |
| `map.delete(k)` | `new Map([...map].filter(([key]) => key !== k))` | ES2015 |
| `map.clear()` | `new Map()` and reassign | ES2015 |
| `set.add(v)` | `new Set([...set, v])` | ES2015 |
| `set.delete(v)` | `new Set([...set].filter(x => x !== v))` | ES2015 |
| `set.clear()` | `new Set()` and reassign | ES2015 |
| Manual union `[...a, ...b]` (deduped) | `a.union(b)` | ES2024 |
| Manual intersection via filter | `a.intersection(b)` | ES2024 |
| Manual difference via filter | `a.difference(b)` | ES2024 |
| Manual XOR | `a.symmetricDifference(b)` | ES2024 |
| Manual subset check | `a.isSubsetOf(b)` | ES2024 |
| Manual superset check | `a.isSupersetOf(b)` | ES2024 |
| Manual disjoint check | `a.isDisjointFrom(b)` | ES2024 |

The seven Set composition methods all return new Set instances and never mutate the receiver. The mutation-method-blocker hook does not flag them.

### Iterables (iterator helpers, ES2024)

When the input is an iterable (generator, lazy stream, range), iterator helpers avoid materializing intermediate arrays and never mutate the source.

| Pattern with arrays | Iterator-helper replacement |
|---------------------|----------------------------|
| `arr.map(fn)` (lazy) | `iter.map(fn)` |
| `arr.filter(fn)` | `iter.filter(fn)` |
| `arr.slice(0, n)` | `iter.take(n)` |
| `arr.slice(n)` | `iter.drop(n)` |
| `arr.flatMap(fn)` | `iter.flatMap(fn)` |
| Materialize | `iter.toArray()` |
| Aggregate | `iter.reduce(fn, init)` |

`.forEach`, `.some`, `.every`, `.find` are also available as iterator helpers in ES2024.

### Dates

| Raw Date pattern | Preferred (Temporal, Stage 4 / ES2026) | Fallback (date-fns) |
|------------------|----------------------------------------|---------------------|
| `date.setMonth(m)` | `Temporal.PlainDate.from(date).with({ month: m })` | `setMonth(date, m)` |
| `date.setDate(d)` | `Temporal.PlainDate.from(date).with({ day: d })` | `setDate(date, d)` |
| `new Date(d.setMonth(...))` | Stay in Temporal: `instant.add({ months: n })` | `addMonths(d, n)` |

Native Temporal lands in Chrome 144+, Firefox 139+, and Edge 144+. Use `@js-temporal/polyfill` or `temporal-polyfill` until baseline support is everywhere.

### Concurrency primitives (no mutation surface)

These ES2024+ primitives are non-mutating and never trigger the hook:

- `Promise.withResolvers()` returns `{ promise, resolve, reject }`. Replaces the manual closure pattern.
- `Promise.try(fn)` runs `fn()` and wraps any throw or return value into a Promise. Replaces ad-hoc `Promise.resolve().then(fn)` wrappers.
- `Array.fromAsync(iterable)` materializes async iterables.
- `RegExp.escape(str)` returns a regex-safe escaped copy.
- `Atomics.pause()` is a SharedArrayBuffer-friendly busy-wait hint.
- `Error.isError(value)` is a duck-typed `instanceof Error` replacement that survives realms.

### Post-ES2024 Stage 3 / Stage 4 features (recognized, as of 2026-05-10)

The hook recognizes the following advanced proposals and emits Stage-aware fix suggestions. Use the env var `MUTATION_METHOD_TC39_STAGE_FILTER` to opt into pre-Stage-4 suggestions (default `4`; set to `3` for Stage 3, `2` for Stage 2 with proposal-volatility warnings).

| Feature | Stage | Use instead of |
|---------|-------|----------------|
| AsyncIterator helpers (`map`, `filter`, `take`, `drop`, `flatMap`, `toArray`) | Stage 3 | `for await` + `.push` materialization |
| `Iterator.range(start, end, step)` | Stage 2/3 | `Array.from({ length: n }, (_, i) => i)` |
| `Iterator.from(iterable)` chain | Stage 3 | Manual generator + array accumulator |
| `Uint8Array.fromBase64(str)` / `fromHex(str)` static factories | Stage 3 | `buf.setFromBase64(str)` / `setFromHex(str)` (mutate receiver) |
| `Float16Array` (allocation, no mutation) | ES2024 (shipped) | `Float32Array` cast or manual half-float bit packing |
| Pipeline operator `\|>` | Stage 2 (hack-style) | Nested function calls (parser-conditional) |
| Records and Tuples (`#{}`, `#[]`) | Withdrawn 2025-04-14 | Plain literals + `as const` and `readonly` ladder |
| Composites proposal | Stage 1 | Records and Tuples successor; not usable yet |
| TC39 Signals proposal (`signal-polyfill`) | Stage 1 | Framework-specific reactive primitives until standardized |

Stage 4 features (`Promise.try`, `Promise.withResolvers`, `Array.fromAsync`, `Error.isError`, `RegExp.escape`, `Atomics.pause`, `Float16Array`) are universally suggested. Stage 3 features ship in TypeScript 5.7+ for AsyncIterator helpers; consult `tsconfig.json` `lib` settings before relying on them.

## Readonly Type Ladder

Stack readonly types from the leaves outward: a parameter that accepts an array of structured records uses all four levels. The compiler rejects mutation at every level instead of only the outermost.

| Surface | Use this |
|---------|----------|
| Object property | `readonly prop: T` on the interface |
| Object as a whole | `Readonly<T>` |
| Array | `readonly T[]` or `ReadonlyArray<T>` |
| Tuple | `readonly [A, B, C]` or `Readonly<[A, B, C]>` |
| Map | `ReadonlyMap<K, V>` |
| Set | `ReadonlySet<T>` |
| Literal value | `as const` (deep readonly, narrows to literal type) |
| Combination | `Readonly<{ items: readonly T[]; tags: ReadonlySet<string> }>` |

The mutation hook complements these compile-time checks at the agent layer: even when a project lacks strict readonly types, the hook catches the mutation when the code is being written.

## Auto-Allowed Scopes

The hook recognizes these scopes without a suppression marker:

- Framework navigation receivers: `router.push`, `history.push`, `navigation.push`, `redirect.push`
- Stream and queue receivers: `stream.push`, `ws.push`, `res.push`, `subject.next`
- Draft and reducer libraries: Immer `produce(state, draft => ...)`, Mutative `create(state, draft => ...)`, Redux Toolkit `createSlice` and `extraReducers`
- Store libraries: Pinia `defineStore`, Vuex `mutations`, MobX `action` / `runInAction` / `makeAutoObservable`, Zustand `set(produce(...))`, Valtio `proxy(...)` tracked variables, Jotai `useAtom` setter, Recoil `useRecoilState` setter (deprecation hint emitted), Nanostores `atom`/`map` `.set()` and `.setKey()`, LegendApp State `observable(...)` `.set()`, Tanstack Store `Store` `.setState()`, Solid stores `setStore(...)`
- State machines: XState v5 `assign(...)` callbacks and `actions` configuration objects
- CRDT and runes: Yjs CRDT types (`new Y.Array`, `new Y.Map`, `new Y.Text`, etc.), Svelte 5 `$state(...)` (but NOT `$state.raw(...)` or `$derived(...)` reassignment)
- Immutable wrappers (mutations on tracked variables flag): Vue 3.5 `readonly()` and `shallowReadonly()`, Effect-TS `Data.struct()` / `Data.tagged()` / `Data.tuple()`
- Modern reactive primitives: Angular signals `signal()` / `computed()` / `linkedSignal()` / `resource()` with `.set()` and `.update()`, Qwik `useSignal()` / `useStore()` / `useComputed$()` with `.value =` assignment, Preact signals `signal()` / `computed()` / `batch()` from `@preact/signals*` packages with `.value =` assignment, React 19 `useFormState()` / `useActionState()` / `useOptimistic()` / `useReducer()` / `useSyncExternalStore()` setter dispatches, React 19 `'use server'` action bodies, TC39 Signals proposal `new Signal.State()` / `new Signal.Computed()` (Stage 1, future-proof placeholder via `signal-polyfill`), Effect-TS `Effect.gen(function*() { ... })` / `Ref.update()` / `Ref.set()` / `Ref.modify()` / `SubscriptionRef` / `SynchronizedRef`, Solid stores `produce()` / `unwrap()` / `reconcile()` (distinguished from Immer by `solid-js/store` import), fp-ts `pipe()` / `flow()` / `chain()` / `fold()` (non-mutating composition, never flagged)
- Solid resources (read-only, never flagged): `createResource()`, `createMemo()`, `createDeferred()`, `createComputed()`, `createReaction()`, `createSelector()`
- State-management filename patterns: `*Slice.ts`, `*Store.ts`, `*reducer.ts`, `*.pinia.ts`, `*.mobx.ts`, `*.valtio.ts`, `*.proxy.ts`, `*.machine.ts`, `*.actor.ts`, `*.svelte`, `*.svelte.ts`, `*.signal.ts`, `*.qwik.tsx`, `*.component.ts`, `*.service.ts`, `*.effect.ts`
- TypedArray hot-path directories: `crypto`, `codec`, `image`, `audio`, `parser`, `wasm`, `canvas`, `encoder`, `decoder`, `simd`, `webgl`, `pixel`, `hash`, `cipher`, `dsp`, `signal`, `fft`, `ml`, `tensor`

Outside these scopes, the rule is absolute. Suppression markers exist for genuine exceptions and require a justification trailer (`-- <reason>`).

## Bypass

When working in a project where the rate of legitimate mutations is high enough that scattered suppression markers would pollute the source (transaction accumulators, advisory-lock patterns, in-memory caches that mirror persisted state, fire-and-forget Redis `client.set` flagged as false-positive `Map.set`), set the env var instead of writing markers into the project's files.

```sh
export MUTATION_METHOD_DISABLE=1
```

Markers in source code are a personal-tooling artifact; they should not appear in the project repository. Prefer one of these per-machine activation paths:

| Scope | How |
|-------|-----|
| Single Claude Code session | Export `MUTATION_METHOD_DISABLE=1` in the parent shell before launching the CLI |
| Per-project, machine-side | A `.envrc` in the local checkout with `export MUTATION_METHOD_DISABLE=1`. Loaded by `direnv`. The `.envrc` is not committed |
| Always-on for one workspace | The `env` block in `~/.claude/settings.local.json` for that workspace |

Per the bypass philosophy shared with `BANNED_PROSE_CHARS_DISABLE` and `CONFIG_LEAKAGE_DISABLE`: the env var is fully audit-logged. Use it when the alternative is dozens of `// allow-mutation -- ...` comments staining a shared repository.

## Three Legs of Data Integrity

Idempotent writes, atomic transactions, and immutable in-process state are three legs of the same stool. The first two are enforced at the boundary of the system (database, queue, network). The third is enforced inside the process by the mutation hook. Drop any leg and the others stop carrying weight: a transactional write of state that was mutated mid-flight commits the wrong values; an idempotent handler that mutates a shared cache between retries produces divergent results across attempts.

See [`checklists/checklist.md`](checklists/checklist.md) category 5 (Data Integrity) for the matching boundary checks: write idempotency keys, transaction scope, and constraint alignment between validators and the database.

## Date and Time Handling

Use a date library for all date operations. Never use raw `Date` methods for formatting, parsing, comparison, or arithmetic.

The Temporal API reached TC39 Stage 4 on 2026-03-11 and is included in ES2026. Native support is shipping in Chrome 144+, Firefox 139+, and Edge 144+. When Temporal is available in the project (native runtime or `@js-temporal/polyfill`), prefer it over date-fns. Temporal types (`PlainDate`, `PlainTime`, `PlainDateTime`, `ZonedDateTime`, `Duration`, `Instant`) are immutable: `.with({ month })`, `.add(Duration.from({ days: 1 }))`, and `.subtract(...)` return new values rather than mutating the receiver, which is exactly the pattern this rule prefers.

| Raw Date pattern | Preferred (Temporal, ES2026 / Stage 4) | Fallback (date-fns) |
|-----------------|----------------------------------------|---------------------|
| `new Date().getFullYear()` | `Temporal.Now.plainDateISO().year` | `getYear(new Date())` |
| `date.toISOString()` | `Temporal.Instant.from(date.toISOString()).toString()` or stay in Temporal end-to-end | `formatISO(date)` |
| `new Date(isoString)` | `Temporal.Instant.from(isoString)` or `Temporal.PlainDate.from(isoString)` | `parseISO(isoString)` |
| `dateA < dateB` | `Temporal.Instant.compare(a, b) < 0` (and friends per type) | `isBefore(dateA, dateB)` |
| `new Date(d.setMonth(...))` | `Temporal.PlainDate.from(d).with({ month })` or `instant.add({ months: n })` | `subMonths(d, n)` / `addMonths(d, n)` |
| `date.toLocaleDateString()` | `temporal.toLocaleString(locale, options)` | `format(date, pattern)` |

The mutation-method-blocker hook automatically tailors its fix suggestions: files that import or reference `Temporal.*` get a Temporal-first hint, while other files get the date-fns fallback hint with a Temporal pointer for new code.

- `new Date()` for creating a timestamp to pass to a database ORM is acceptable since the ORM needs a Date object
- For TypeScript projects, `Temporal` is preferred when available, `date-fns` is the fallback. For other languages, use the equivalent standard library
- All date formatting must respect user locale or configurable format preferences, never hardcode a single format
- Every `format()` call that renders user-visible text must receive the dynamic locale from the app's locale context, never a hardcoded locale import
