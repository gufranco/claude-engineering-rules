# TypeScript Strict Mode

## Compiler Strictness Baseline

`"strict": true` plus every additional flag not covered by `strict`: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`, `noFallthroughCasesInSwitch`, `forceConsistentCasingInFileNames`, `verbatimModuleSyntax`. When a new strictness flag is added to TypeScript, enable it.

The cross-language strictness principle and per-language requirements live in [`rules/code-style.md`](../code-style.md) under "Maximum Compiler and Checker Strictness". This file covers TypeScript specifics.

## Target and Module Settings

For Node.js projects, `target` and `module`/`moduleResolution` must match the runtime version. Use the `@tsconfig/node{version}/tsconfig.json` base or set equivalent values manually. Running ES2024+ features through downlevel compilation when the runtime supports them natively adds overhead and hides bugs.

Browser projects: target the lowest supported browser baseline. When using a build tool that handles transpilation, Vite, esbuild, swc, `target` in `tsconfig.json` controls type checking only; the bundler controls emission. Keep both aligned to avoid type-check passes claiming features the bundler will not emit.

## TypeScript 5.x Patterns

- Use `using` / `await using` for resource management instead of manual try/finally. Implement `Symbol.dispose` / `Symbol.asyncDispose` on classes that manage connections, file handles, or sessions
- Use `NoInfer<T>` on fallback parameters in generic functions to prevent type widening from the default value
- Enable `verbatimModuleSyntax` in all new projects. Require explicit `import type` declarations
- Enable every new strictness flag when upgrading TypeScript versions

## TypeScript 5.8 Specifics

TypeScript 5.8 is the current stable release as of 2026. Adopt these flags in new projects and consider them when upgrading existing ones.

| Flag or Feature | Behavior |
|----------------|----------|
| `--erasableSyntaxOnly` | Errors on TypeScript-specific constructs that have runtime behavior. Required when the project relies on Node.js direct `.ts` execution or any toolchain that strips types without compiling them |
| `--module node18` | Stabilized as a fixed reference point for Node.js 18 projects. Use it when the runtime is pinned to Node.js 18 and the project does not need `nodenext` semantics |
| `require()` of ESM under `--module nodenext` | TypeScript no longer errors when CommonJS files call `require()` on ESM siblings. Matches the Node.js runtime behavior |
| Granular conditional-branch return checks | Errors point at the specific branch with the wrong return type rather than the whole function. Acts as a verification surface for switch-style logic |

When direct execution of `.ts` files is part of the runtime path, pair `--erasableSyntaxOnly` with a tsconfig that targets the runtime's actual version. Build pipelines that compile to JavaScript do not need the flag.
