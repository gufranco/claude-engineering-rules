# Functional Index Fidelity

Applies when a query wraps a column in a function, or when adding an expression index.

- The query's expression must be identical to the indexed one, never merely equivalent; an index on `fn(col)` serves only `fn(col) = value`.
- Put the expression in one exported helper that the migration and every query import.
- Verify index use with the query plan on realistic data, never with result correctness.

Full rule, examples, and rationale: [`standards/functional-index-fidelity.md`](../standards/functional-index-fidelity.md). Read it before writing or editing such a predicate.
