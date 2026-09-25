# Code Style

Always choose the complete implementation, and write code that is self-explanatory, strongly typed, immutable by default, and free of silent failures.

## Completeness

- No TODOs, no "later", no shortcuts. Finish tests, every error path, validation, edge cases, docs, accessibility, both up and down migrations, and cleanup of dead code and unused imports.
- New database models ship `@faker-js/faker` seed data with a quantity set by an env var such as `SEED_SCALE`.
- New user-facing strings are translated into every supported locale before delivery.
- Tables showing backend data support server-side sorting with URL-persisted state.
- Multi-week or cross-cutting work is flagged as a separate task; inside the declared scope, finish to production quality.

## Size And Structure

- Functions under 30 lines. Files under 500 lines.
- Files may exceed 500 lines without a waiver only for: a state machine whose cases change with their guards, generated code, a single calculation engine sharing intermediate state, or a service whose operations share private state.
- Functions may exceed 30 lines only for a flat branchless step sequence, or an exhaustive one-line-per-branch match over a closed union.
- If splitting makes the code harder to understand, keep it together, and say why in the PR body. Anything else needs a waiver.
- Max 3 levels of nesting. Use guard clauses and early returns.
- No magic numbers or strings: a literal used more than once becomes a named constant in a central config or constants file.
- Single export per file. Many arguments become one options object. Return objects.
- Functional core, imperative shell. Use-case functions are flat sequential calls with no conditionals, loops, or exception handling.
- Never branch business logic on `NODE_ENV` or `APP_ENV`; externalize via config.
- No module-level side effects: no connections, listeners, timers, or I/O at import time.
- Braces on every control structure. Law of Demeter: no chains through transitive objects.
- Every loop, retry, poll, and pagination has an explicit upper bound. No unbounded `while (true)`.
- Declare variables at the smallest scope. Avoid recursion unless the data is recursive, and then add a depth limit.
- Never run CPU-heavy work or synchronous I/O on the request-handling thread.
- Services throw domain errors; a boundary filter maps them to HTTP. In NestJS, register validation globally, never per-parameter pipes.

## Comments

- Comments are not permitted in project source code in any language, test files included.
- The only exemption is a tool directive a tool parses, at the start of the comment: eslint, biome, ruff, noqa, pylint, shellcheck, `@ts-expect-error`, prettier-ignore, istanbul/c8, `//go:build`, `//nolint`, webpack magic comments, SPDX headers, Rust `// SAFETY:`.
- A project convention requiring JSDoc is an existing violation, not permission. Put that reasoning in the PR description.
- When code needs a comment, rename, extract a named function, or encode the contract in types instead.

## Errors And Logging

- Never swallow errors: no empty `catch`. Every catch logs with context, then rethrows or returns a typed error.
- Every catch classifies the error: transient with backoff, permanent fails fast, ambiguous retries with a limit.
- Every `void promise` ends with `.catch((error: unknown) => logger.error({ err: error }, 'description'))`.
- Never ignore return values. Enable `@typescript-eslint/no-floating-promises`.
- Use the project logger. No `console.log`, `console.error`, `console.warn`, `console.info` in production code; only Next.js `error.tsx` is exempt.
- Prefer `Result<T, E>` for expected domain failures; exceptions for broken invariants.

## Types And Data

- Explicit types on parameters, returns, and public interfaces. Never `any`; use `unknown` and narrow. Replace `any` in code you touch.
- String enums over string literal unions for domain values.
- Maximum strictness: TypeScript `strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`, `noFallthroughCasesInSwitch`, `forceConsistentCasingInFileNames`, `verbatimModuleSyntax`. Never lower strictness to compile.
- No raw SQL when an ORM exists, including `$queryRaw`, `$executeRaw`, and their unsafe variants, in tests too. SQL belongs only in migration files.
- Routers, controllers, and handlers never import the ORM; all data access goes through services.
- Never use `Record<string, unknown>` for ORM where, data, or orderBy; use the generated input types.
- Zod for validation. Parse, don't validate: return branded types. Required ID strings use `.min(1)`; money and quantities use `.positive()`.
- No `eval`, `Function()`, or runtime code generation. No barrel imports.

## Immutability And CQS

- Immutable by default: `const`, never mutate arguments, copy and return, state transitions produce new state, derive instead of caching.
- A function is either a command returning void or a `Result`, or a query with no side effects. Never both.
- Before any mutation answer: idempotent, atomic, duplicates, concurrent. A read that decides a write sits in one transaction, an upsert, or behind a unique constraint.
- Shared calculations are one function called by every delivery path: REST, WebSocket, jobs, push.

## Dependencies And Other Rules

- Never add a dependency without approval. Check the platform first: `URL`, `URLSearchParams`, `AbortSignal.timeout`, `structuredClone`, `crypto.randomUUID`.
- Compare the top 3-5 options on measurable criteria. Pin exact versions, commit the lockfile, pin the package manager.
- Grep every consumer before removing or renaming any resource.
- Use Temporal or `date-fns`, never raw `Date` methods for formatting or arithmetic; pass the app locale to every `format()`.
- Destructive single-click actions show a framework confirmation dialog, never `window.confirm()`.
- Treat LLM output as untrusted input: validate shape, sanitize, allowlist URLs.
- Commits: separate renames from behavior changes, never mix formatting with logic, each commit builds and passes tests.

Full rule, examples, and rationale: [`standards/code-style.md`](../standards/code-style.md). Read it before exceeding a size threshold, choosing a dependency, designing error returns, or writing locale-aware or i18n code.

## Enforcement

Enforced by: [`hooks/config-protection.py`](../hooks/config-protection.py).
Enforced by: [`hooks/console-log-blocker.py`](../hooks/console-log-blocker.py).
Enforced by: [`hooks/interactive-cmd-blocker.py`](../hooks/interactive-cmd-blocker.py).
Enforced by: [`hooks/settings-hygiene.py`](../hooks/settings-hygiene.py).
