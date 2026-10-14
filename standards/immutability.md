# Immutability Across Languages

Immutable by default, mutable by exception, in every language the project uses. Loaded on demand. Triggers in [`../rules/index.yml`](../rules/index.yml).

## Scope

| Concern | Owner |
|---------|-------|
| Cross-language expression of immutability, boundary copies, persistence-level immutability | This file |
| The TypeScript mutation surface, ES2024 replacements, framework allowlists, the hook | [`../rules/lang/typescript-immutability.md`](../rules/lang/typescript-immutability.md) |
| Python typing and dataclass specifics | [`../rules/lang/python.md`](../rules/lang/python.md) |
| Rust ownership, JVM records, Go idiom | [`rust.md`](rust.md), [`jvm.md`](jvm.md), [`go.md`](go.md) |
| Write-time enforcement for every language above | The hooks in the Enforcement section |
| Races that immutability does not remove | [`concurrency.md`](concurrency.md) |

## Why

Three separate arguments, and the third is the one usually left unsaid.

1. **Aliasing.** A value handed to a function can come back changed. Every caller of that function now depends on an effect that is invisible at the call site.
2. **Concurrency.** A value that never changes cannot be observed half-changed. Immutability removes torn reads and read-modify-write hazards on in-process state outright. It does not remove database races, which is why [`concurrency.md`](concurrency.md) exists.
3. **Reasoning and audit.** A value that never changes has a history. Systems that must answer "what did this look like on Tuesday" cannot be built on values that were overwritten on Wednesday.

## The Default

Every value starts readonly. Mutability is a decision with a reason, written where the mutation happens.

- Never mutate a parameter. Copy, change the copy, return it.
- Never mutate a value after publishing it to another module, thread, or goroutine.
- Derive rather than cache. A computed value stored as a mutable field drifts out of sync with its inputs.
- Prefer a fresh instance to an in-place edit whenever a non-mutating alternative exists in the language.

## Per-Language Expression

| Language | Declare immutable | Copy with change | Enforced by | Escape hatch to avoid |
|----------|-------------------|------------------|-------------|-----------------------|
| TypeScript | `readonly` fields, `readonly T[]`, `ReadonlyMap`, `as const` | `{ ...obj, k: v }`, `arr.with(i, v)`, `arr.toSorted()` | Compiler, plus [`../hooks/mutation-method-blocker.py`](../hooks/mutation-method-blocker.py) | `as any`, `Object.freeze` used as a substitute for types |
| Python | `@dataclass(frozen=True, slots=True)`, `Final`, `tuple`, `Mapping` parameters | `dataclasses.replace(obj, k=v)`, `(*items, new)` | `mypy --strict` or `pyright`, plus [`../hooks/python-mutation-guard.py`](../hooks/python-mutation-guard.py) | `object.__setattr__` on a frozen instance |
| Go | Unexported fields with value receivers, returning copies | `slices.Clone`, `maps.Clone`, struct copy | [`../hooks/polyglot-immutability-guard.py`](../hooks/polyglot-immutability-guard.py) for package-level state and writes into slice or map parameters; `golangci-lint` with `reassign`, `gocritic` and `revive` | Returning a slice or map that aliases internal state |
| Rust | Bindings are immutable unless `mut`, shared references are readonly | `Clone` then mutate the clone, or a struct update expression | The compiler; the polyglot hook blocks `static mut` | `unsafe`, `static mut`, interior mutability without a stated reason |
| C and C++ | `static const` and `constexpr` tables, `const` pointers and parameters | Copy into a local, return by value | The polyglot hook for file-scope tables; `clang-tidy` `misc-const-correctness` for the rest | A writable table that never changes, which also costs RAM on embedded targets |
| Java | `record`, `final` fields, `List.copyOf` and friends | Canonical constructor, or a `with`-style builder | The polyglot hook for static state; Error Prone `@Immutable`, PMD | Returning the backing collection from a getter |
| Kotlin | `val`, `data class`, read-only `List` interfaces | `copy(k = v)` | The polyglot hook; detekt `DataClassShouldBeImmutable` | Casting a read-only `List` to `MutableList` |
| C# | `record`, `readonly record struct`, `init` accessors, `ImmutableArray`, `FrozenDictionary` | `with { K = v }` | The polyglot hook; analyzers IDE0044 and CA2227 | Exposing a `List<T>` field as a property |
| Swift | `let`, `struct` value semantics | `var copy = value` then mutate the copy | Compiler warnings as errors; the polyglot hook warns on `static var` | Shared `static var` and top-level `var` |
| Dart | `final`, `const` constructors, `@immutable`, `@freezed` | `copyWith` | The analyzer with `must_be_immutable` and `prefer_final_fields`; the polyglot hook for widget fields | `@unfreezed`, `makeCollectionsUnmodifiable: false` |
| Ruby | `# frozen_string_literal: true`, `.freeze` on constants, `Ractor.make_shareable` | `dup` then change, or `merge` | The polyglot hook; RuboCop `Style/MutableConstant` | A constant holding a mutable array or hash |
| Lua | `local`, `local x <const>` in Lua 5.4 | Build a new table | luacheck; the polyglot hook warns on implicit globals | `rawset` on a read-only table |
| Shell | `readonly`, `declare -r`, `local -r`, zsh `typeset -r` | Assign a new name | ShellCheck | Reassigning an exported variable another script reads |
| Elixir and Clojure | Immutable by default | Every update returns a new value | The language | ETS tables, process state, atoms; see [`idempotency.md`](idempotency.md) |

### Severity: collections block, attributes warn

Decided 2026-10-14. Collection mutation through a parameter blocks in every guard: a method mutator such as `append` or `push`, item assignment, `del`, and in-place `+=` on a collection. A plain attribute write on a parameter object, such as `cpu.registers.de = value` or `setattr(obj, ...)`, is advisory. Emulator and hardware-model code mutates state objects by design, and 107 of 173 Python parameter hits across the Workspace on that date were attribute writes in those repositories. Shared state at module, package, class, or static level blocks in every language.

Two cross-cutting notes. A read-only interface over a mutable object is not immutability; the holder of the concrete type can still change it under you. And shallow immutability stops at the first nested reference, so a frozen object holding a mutable array is mutable where it matters.

## Boundaries

The boundary is where aliasing bugs are born, because that is where a reference crosses from code you control to code you do not.

| Boundary | Rule |
|----------|------|
| Public function parameter | Accept the read-only type. `readonly T[]`, `Sequence[T]`, `List<T>` as read-only, `&[T]` |
| Public function return | Return a copy or an immutable view, never the internal collection itself |
| Constructor input | Copy collections in. The caller keeps their reference and may mutate it later |
| Getter | Return a copy, an immutable wrapper, or a value type. Never the field |
| Cache entry | Store a copy and hand out copies, or store a deeply immutable value. A shared mutable cache entry is a race and an aliasing bug at once |
| Cross-thread or cross-goroutine handoff | Transfer ownership or hand over an immutable value. Sharing a mutable value requires a lock, and the lock is now yours to maintain |
| Trust boundary, such as a plugin or third-party callback | Freeze at runtime, because the type system does not constrain the other side |

Defensive copying has a cost, and the cost is almost always smaller than one aliasing bug. Measure before deciding it is too expensive.

## Collections and Structural Sharing

Copy-on-write is fine at small sizes. When a large collection is updated in a hot path, reach for structural sharing rather than abandoning immutability.

| Language | Option |
|----------|--------|
| TypeScript | Immer for draft-based updates, Immutable.js or `mori` for persistent structures |
| Python | `pyrsistent` for persistent collections |
| Java and Kotlin | `kotlinx.collections.immutable`, Guava immutable collections, Vavr |
| C# | `System.Collections.Immutable` |
| Rust | `im` |
| Go | No idiomatic library. Prefer append-only slices and copy on write |

Draft-based libraries such as Immer localize mutation to a controlled scope. The mutation stays inside the draft callback, and the rest of the code sees a new immutable value. Framework-internal mutation stays at the framework boundary, per [`../rules/lang/typescript-immutability.md`](../rules/lang/typescript-immutability.md).

## Persistence-Level Immutability

In-memory immutability with an UPDATE-everything database gives up most of the benefit. The same discipline applies to stored data.

| Data class | Rule |
|-----------|------|
| Money movements | Append-only. Never UPDATE a ledger row. A correction is a new compensating entry, and the balance is derived |
| Audit and access logs | Append-only, no UPDATE, no DELETE outside retention policy. An audit trail you can edit is not evidence |
| Domain events | Immutable once published. A corrected event is a new event, never an edited one |
| Historical state | Bitemporal columns, `valid_from` and `valid_to`, or a history table written by trigger |
| Business entities | Mutable rows are fine, with `updated_at` and an audit trail of what changed |
| Soft delete | A `deleted_at` marker is retention, never erasure. Privacy erasure must actually remove or irreversibly anonymize, per [`../rules/privacy-defaults.md`](../rules/privacy-defaults.md) |

Event sourcing is the strongest form: state is the fold over an immutable event log. It buys perfect history and time travel, and costs a projection layer, schema evolution on events, and a snapshot strategy. Adopt it for domains where history is the product, such as ledgers, and avoid it for CRUD.

Two rules that hold regardless of the storage model:

- A migration that rewrites historical rows destroys the record it is rewriting. Add a corrected column and backfill forward, keeping the original.
- A derived value stored alongside its inputs will drift. Either compute it on read, or make the inputs immutable so it cannot drift.

## What Immutability Does Not Fix

Immutability removes a class of races in memory. It does not remove the races in [`concurrency.md`](concurrency.md).

| Race | Removed by immutability? |
|------|--------------------------|
| Torn read of a partially updated in-memory object | Yes |
| Two goroutines writing one map | Yes, by construction |
| Read-modify-write on shared in-process state | Yes, when the state is replaced atomically rather than edited |
| Check-then-act against a database | No |
| Lost update across two transactions | No |
| Duplicate message delivery | No |
| Two replicas racing on one row | No |

A pure functional core does not make the write at the edge safe. It makes the edge easier to find, which is the actual benefit.

## Performance

Immutability costs allocations. The cost matters in a narrow set of places and is noise everywhere else.

- Hot loops over large arrays, binary buffers, and pixel or audio data are the genuine exception. Mutate in place there, keep the mutation inside a function whose signature returns a fresh value, and measure.
- `readonly` in TypeScript, `final` in Java, and immutable bindings in Rust are compile-time only and cost nothing at runtime.
- `Object.freeze` and equivalents are runtime and shallow. Reserve them for trust boundaries.
- Before optimizing away a copy, measure with realistic data sizes, per [`../rules/testing.md`](../rules/testing.md). A copy that never showed up in a profile is not a cost.

## Anti-Patterns

| Anti-pattern | Why it fails |
|--------------|--------------|
| Mutating a parameter and also returning it | Callers cannot tell whether the original changed, and half of them will assume wrong |
| Returning the backing collection from a getter | Every caller now holds a handle to your internal state |
| A read-only interface over a mutable instance held elsewhere | The other holder can still mutate it |
| `Object.freeze` used where a `readonly` type belongs | Runtime cost, shallow depth, no compile-time signal |
| Storing a derived value as a mutable field | Drifts from its inputs at the first missed update |
| UPDATE on a ledger or audit row | Destroys the record the row exists to preserve |
| Soft delete presented as erasure | Fails privacy obligations while looking compliant |
| A frozen object holding a mutable array | Immutable at the level nobody was going to mutate anyway |
| Copying inside a hot loop with no measurement | The one case where the reflex is wrong, applied without evidence |

## Enforcement

| Layer | Coverage |
|-------|----------|
| [`../hooks/mutation-method-blocker.py`](../hooks/mutation-method-blocker.py) | TypeScript and JavaScript: array, collection, property, prototype, destructuring and loop-target writes, plus framework state rules |
| [`../hooks/python-mutation-guard.py`](../hooks/python-mutation-guard.py) | Python, parsed with `ast`: mutable defaults, parameter mutation, `object.__setattr__` outside init hooks, `global`, module-level and class-level containers, and dataclasses without `frozen=True` as advisory |
| [`../hooks/polyglot-immutability-guard.py`](../hooks/polyglot-immutability-guard.py) | Go, Rust, C, C++, Swift, Java, Kotlin, C#, Dart, Ruby, Lua |
| [`../hooks/immutability-analyzers.py`](../hooks/immutability-analyzers.py) | End of turn: clang-tidy, golangci-lint, ruff, pyright, rubocop, luacheck, detekt, PMD, swiftlint and the Dart analyzer on every edited file; see Analyzer Catalog |
| Type checkers | `tsc` with the strict flag set, `mypy --strict` or `pyright`, the Rust, Swift, Kotlin and Java compilers |
| Linters | `@typescript-eslint/prefer-readonly-parameter-types`, `ruff` B006 and RUF012, `golangci-lint`, `clang-tidy`, detekt, RuboCop, luacheck, the Dart analyzer |
| Review | [`../checklists/checklist.md`](../checklists/checklist.md) categories 1 and 5 |

Checks that need type information stay with the real tool: aliasing returns in Go, needless `&mut` in Rust, const correctness in C and C++, `ImmutableField` in Java, and IDE0044 in C#. A text hook cannot see the types those rules depend on.

## Analyzer Catalog

Decided 2026-10-14. Literal 100% detection is impossible from source alone: writes through aliased pointers, reflection, FFI and native code escape every tool. The guarantee is narrower and checkable: every rule below is enforced, and each one is proven by a fixture that makes the real tool report it.

Three layers enforce the directives:

1. Write-time hooks block the change before it lands; see Enforcement.
2. [`../hooks/immutability-analyzers.py`](../hooks/immutability-analyzers.py) records every in-scope file edited in a turn and, at the end of the turn, runs that language's analyzer with the configuration in [`../analyzers/`](../analyzers/). The configuration is passed explicitly, so a project's own lint config cannot drop a directive.
3. Findings on lines changed against `HEAD` block the end of the turn; findings on untouched lines are listed as advisory, so a legacy file never blocks an unrelated edit. A missing or crashing analyzer blocks. When identical findings survive one block, they are shown to the user instead of blocking again.

| Language | Tool | Rule | Severity |
|----------|------|------|----------|
| C, C++ | `clang-tidy` | `cppcoreguidelines-pro-type-const-cast` | Blocks |
| C, C++ | `clang-tidy` | `misc-const-correctness` | Blocks |
| C, C++ | `clang-tidy` | `readability-make-member-function-const` | Blocks |
| C, C++ | `clang-tidy` | `readability-non-const-parameter` | Blocks |
| C, C++ | `clang-tidy` | `cppcoreguidelines-avoid-non-const-global-variables` | Warns |
| Go | `golangci-lint` | `gocritic` | Blocks |
| Go | `golangci-lint` | `reassign` | Blocks |
| Go | `golangci-lint` | `revive` | Blocks |
| Go | `golangci-lint` | `gochecknoglobals` | Warns |
| Python | `ruff` | `B006` | Blocks |
| Python | `ruff` | `B008` | Blocks |
| Python | `ruff` | `B020` | Blocks |
| Python | `ruff` | `B909` | Blocks |
| Python | `ruff` | `PLW0602` | Blocks |
| Python | `ruff` | `PLW0603` | Blocks |
| Python | `ruff` | `PLW0642` | Blocks |
| Python | `ruff` | `PLW2901` | Blocks |
| Python | `ruff` | `RUF008` | Blocks |
| Python | `ruff` | `RUF009` | Blocks |
| Python | `ruff` | `RUF012` | Blocks |
| Python | `pyright` | `reportConstantRedefinition` | Blocks |
| Ruby | `rubocop` | `Style/ClassVars` | Blocks |
| Ruby | `rubocop` | `Style/FrozenStringLiteralComment` | Blocks |
| Ruby | `rubocop` | `Style/GlobalVars` | Blocks |
| Ruby | `rubocop` | `Style/MutableConstant` | Blocks |
| Lua | `luacheck` | `W121` | Blocks |
| Lua | `luacheck` | `W122` | Blocks |
| Lua | `luacheck` | `W142` | Blocks |
| Lua | `luacheck` | `W111` | Warns |
| Lua | `luacheck` | `W112` | Warns |
| Kotlin | `detekt` | `DataClassShouldBeImmutable` | Blocks |
| Java | `pmd` | `ArrayIsStoredDirectly` | Blocks |
| Java | `pmd` | `AssignmentToNonFinalStatic` | Blocks |
| Java | `pmd` | `AvoidReassigningParameters` | Blocks |
| Java | `pmd` | `ImmutableField` | Blocks |
| Java | `pmd` | `MethodReturnsInternalArray` | Blocks |
| Java | `pmd` | `MutableStaticState` | Blocks |
| Swift | `swiftlint` | `shared_static_var` | Warns |
| Swift | `swiftlint` | `top_level_var` | Warns |
| Dart | `dart` | `PREFER_FINAL_FIELDS` | Blocks |
| Dart | `dart` | `PREFER_FINAL_IN_FOR_EACH` | Blocks |
| Dart | `dart` | `PREFER_FINAL_LOCALS` | Blocks |

Editor and command-line runs apply the same rules through user-level configs that the dotfiles installer links into `~/.clang-tidy`, `~/.golangci.yml`, `~/.config/ruff/ruff.toml`, `~/.config/rubocop/config.yml`, `~/.config/luacheck/.luacheckrc` and `~/analysis_options.yaml`; where the tool supports an include, those files include the configs in [`analyzers/`](../analyzers/) rather than copying them.

The catalog is held to the code by [`tests/scripts/test_analyzer_catalog.py`](../tests/scripts/test_analyzer_catalog.py), and every row is proven against the real tool by `make test-analyzers`, which runs locally because CI runners do not carry these analyzers. Rules that need type information the tools lack outside a full build, such as detekt `VarCouldBeVal` and Dart `must_be_immutable`, are covered by the write-time hooks instead.

## Related Standards

- [`../rules/lang/typescript-immutability.md`](../rules/lang/typescript-immutability.md): the TypeScript depth, mutation surface, and hook behavior
- [`concurrency.md`](concurrency.md): the races immutability leaves for you to handle
- [`idempotency.md`](idempotency.md): why append-only storage makes replay trivial
- [`ddd-tactical-patterns.md`](ddd-tactical-patterns.md): value objects, entity identity, domain events
- [`database.md`](database.md): history tables, temporal columns, transaction strategy
