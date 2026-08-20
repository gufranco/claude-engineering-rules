# Functional Index Fidelity

## Scope

Loaded when a task writes a query whose predicate wraps a column in a function or expression, or when a task adds an expression index. Triggers in [`index.yml`](index.yml).

## Core Rule

A database uses an expression index only when the query's expression is **identical** to the indexed one. Not equivalent, not logically the same, identical. Reuse the indexed expression verbatim rather than rewriting it.

An equivalent rewrite is the dangerous case, because nothing reports it. The query is correct, the tests pass on small fixtures, the plan silently degrades to a sequential scan, and the cost appears later as latency on a table large enough to matter.

## What Counts As A Different Expression

Each of these defeats the index while preserving the result:

| Change | Example |
|---|---|
| A different but equivalent pattern | `regexp_replace(col, '[^0-9]', '', 'g')` against an index built on `'\D'` |
| Dropping a wrapper that looks redundant | Omitting `COALESCE(col, '')` when the index includes it |
| Reordering commutative arguments | `b \|\| a` against an index on `a \|\| b` |
| A different cast spelling | `col::text` against `CAST(col AS text)` where the planner does not normalize |
| Changing collation or case handling | `upper(col)` against an index on `lower(col)` |
| A predicate shape the index does not cover | A range or prefix scan against an index that only supports exact match |

The last row is the subtle one: an index on `fn(col)` supports `fn(col) = value` and nothing else. A `LIKE`, a range, or an inequality on the same expression does not use it.

## Obligations

- **Centralize the expression.** When a functional index exists, the expression belongs in one exported helper that both the migration and every query import. Two hand-written copies drift, and the drift is invisible.
- **Name the index the expression serves.** A comment cannot carry this, per the comments policy, so the helper's name does: `userPhoneDigitsSql` reads as the thing the `..._phone_digits_idx` index is built on.
- **Verify the plan, not the result.** A test asserting the right rows says nothing about whether an index was used. When the query matters, check the plan on data large enough for the planner to prefer a scan, since it will use an index on a tiny table regardless.
- **Verify after any edit to the predicate.** A refactor that tidies an expression is exactly how this regresses.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Hand-writing an expression that a functional index already covers | Any divergence, however small, drops the index |
| Rewriting an indexed expression into an equivalent form | Silent sequential scan with no error and no failing test |
| Asserting query correctness as evidence of index use | Correct rows and a full scan are entirely compatible |
| Adding an expression index without routing callers through one shared expression | Guarantees drift as soon as a second caller appears |
| Benchmarking index use on a fixture table | The planner picks a scan on small tables regardless, so the result is meaningless |

## Cross-References

- [`../standards/database.md`](../standards/database.md): general query and schema concerns.
- [`../standards/postgresql.md`](../standards/postgresql.md): PostgreSQL specifics.
- [`code-style.md`](code-style.md): the single-source-of-truth principle the shared helper applies.
- [`verification.md`](verification.md): why the plan rather than the result is the evidence here.
