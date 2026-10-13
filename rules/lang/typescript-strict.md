# TypeScript Strict Mode

`"strict": true` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`, `noFallthroughCasesInSwitch`, `forceConsistentCasingInFileNames`, and `verbatimModuleSyntax`.

- Enable every new strictness flag on upgrade; never lower strictness to compile.
- `target` and `module` match the runtime version.
- Use `using` for resources; set `--erasableSyntaxOnly` when `.ts` runs directly.

Full rule, examples, and rationale: [`standards/typescript-strict.md`](../../standards/typescript-strict.md). Read it before editing a tsconfig.

## Provenance

Added 2026-05-11, recurrence not recorded. Origin: not recorded at creation.
