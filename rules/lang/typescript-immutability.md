# TypeScript Immutability

Immutable by default. Never mutate arguments; produce new values. Banned mutators and replacements:

- `.push(x)`: `[...arr, x]`
- `.sort()`: `.toSorted()`
- `.reverse()`: `.toReversed()`
- `.splice()`: `.toSpliced()`
- `arr[i] = v`: `arr.with(i, v)`
- `obj.p = v`, `Object.assign(target, s)`: `{ ...obj, p: v }`
- `delete obj.p`: `const { p, ...rest } = obj`
- `map.set`, `set.add`: `new Map([...map, [k, v]])`, `new Set([...set, v])`
- Date setters: Temporal `.with()` or `date-fns`
- `let` never reassigned: `const`

Parameters take `readonly T[]` or `Readonly<T>`; literals use `as const`. `router.push` and Immer drafts are exempt.

Full rule, surface list, and rationale: [`standards/typescript-immutability.md`](../../standards/typescript-immutability.md). Read it before a mutation hook blocks you.
