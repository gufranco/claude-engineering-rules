# ts-strictness-pack

Maximum TypeScript strictness bundle: immutability by default, branded types, ORM migration parity, and a 90+ pattern mutation blocker.

## Status

**Skeleton.** The manifest at [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) enumerates the files this plugin would distribute, but the files themselves still live in the top-level config tree.

## Highlights

- **Immutability is the default.** `const` over `let`. Spread over `.push()`. `.toSorted()` over `.sort()`. ES2024+ replacements for every mutating method. Mechanical enforcement via the mutation-method-blocker hook covering Array, Object, Map, Set, TypedArray, DataView, Date setters, `Atomics`, Proxy traps, WeakRef chains, and FinalizationRegistry callbacks.
- **Branded types prevent ID confusion.** `UserId` and `OrderId` are both strings; the type system makes mixing them a compile error.
- **Discriminated unions for state.** No boolean blindness. Exhaustive matching enforced with `satisfies never`.
- **Type-state pattern for workflows.** Each state is a distinct type; methods return the next valid state; invalid transitions do not exist in the API.
- **Maximum compiler strictness.** Every TypeScript strictness flag enabled, including `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`, `verbatimModuleSyntax`.
- **ORM migration parity.** Schema source and migration history are two views of the same state. Per-ORM hooks for Drizzle, Prisma, Sequelize, TypeORM block raw-SQL escape hatches and check schema-migration sync on every write.

## Compatibility

- TypeScript 5.7+
- Node 18+
- All four major SQL ORMs covered (Prisma, Drizzle, Sequelize, TypeORM)

## Migration plan

When the flat-to-plugin migration ships:

1. Move the files listed in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) into this directory under matching subpaths.
2. Update the top-level rule loader to discover via the plugin manifest.
3. Bump version to `1.0.0` and remove the `status: skeleton` marker.

## Cross-references

- [`compliance-pack`](../compliance-pack/) covers the orthogonal compliance baseline (privacy, accessibility, cybersecurity).
