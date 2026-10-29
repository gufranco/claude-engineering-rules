# TypeScript Type Constructs

- `interface` for object shapes; `type` for unions, mapped, and conditional types; string `enum` for runtime domain values.
- Model dependent fields as discriminated unions, matched exhaustively with `satisfies never`.
- Brand structurally identical primitives: `type UserId = Brand<string, 'UserId'>`.
- Encode legal state transitions with the type-state pattern.

Full rule, examples, and rationale: [`standards/typescript-types.md`](../../standards/typescript-types.md). Read it before designing domain types.

## Enforcement

Enforced by: [`hooks/as-any-blocker.py`](../../hooks/as-any-blocker.py).
