# Monorepo

## Package Manager

Use pnpm with workspaces. pnpm's content-addressable storage deduplicates dependencies across packages, and strict node_modules isolation prevents phantom dependencies.

- Define workspaces in `pnpm-workspace.yaml`.
- Pin the pnpm version with Corepack: `"packageManager": "pnpm@9.x.x"` in the root `package.json`.
- Commit `pnpm-lock.yaml`. Never `.npmrc` overrides that change hoisting behavior without team agreement.

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/*"
  - "packages/*"
  - "tools/*"
```

## Task Orchestration

Use Turborepo or Nx to orchestrate builds, tests, and linting across packages. Both provide dependency-aware task scheduling and remote caching.

| Concern | Turborepo | Nx |
|---------|-----------|-----|
| Config format | `turbo.json` | `nx.json` + `project.json` per package |
| Task dependencies | `dependsOn` array | `targetDefaults` with dependency config |
| Remote cache | Vercel Remote Cache or self-hosted | Nx Cloud or self-hosted |
| Affected detection | Git diff based | Dependency graph + git diff |
| Learning curve | Lower, convention over configuration | Higher, more flexible |

Pick one and commit to it. Mixing orchestrators creates confusion.

## Internal Package References

Use the `workspace:*` protocol for all internal dependencies. This ensures the local version is always used during development and resolved to the published version on `pnpm publish`.

```json
{
  "dependencies": {
    "@acme/shared-utils": "workspace:*",
    "@acme/ui-components": "workspace:*"
  }
}
```

Never use `file:` or `link:` protocols. They create inconsistencies between development and published artifacts.

## Changeset-Based Versioning

Use `@changesets/cli` for versioning and changelog generation.

1. Developer adds a changeset: `pnpm changeset`. Selects affected packages and bump type.
2. The changeset file is committed with the PR.
3. CI creates a "Version Packages" PR that applies all pending changesets.
4. Merging that PR bumps versions and publishes.

- Every PR that changes package behavior must include a changeset. CI checks for this.
- Internal packages that are not published still benefit from changesets for changelog tracking.

## Per-Package Build Ownership

Each package owns its build configuration and scripts. The root `package.json` orchestrates, not builds.

| Location | Responsibility |
|----------|---------------|
| Root `package.json` | Workspace-level scripts: `build`, `test`, `lint` delegated to orchestrator |
| Root `turbo.json` / `nx.json` | Task dependency graph, caching config |
| Package `package.json` | Package-specific `build`, `test`, `lint`, `typecheck` scripts |
| Package `tsconfig.json` | Package-specific TypeScript config extending a shared base |

A package must build independently. Running `pnpm build` inside any package must produce a working artifact without relying on other packages being built first, except for declared dependencies in the task graph.

## Shared Configuration

Deduplicate configuration through shared packages.

```
packages/
  config-typescript/    # Shared tsconfig bases
  config-eslint/        # Shared ESLint configs
  config-prettier/      # Shared Prettier config
```

Each consuming package extends the shared config:

```json
{
  "extends": "@acme/config-typescript/base.json",
  "compilerOptions": {
    "outDir": "dist"
  }
}
```

## Cache Hit Rate Targets

Remote caching is the primary productivity benefit of a monorepo orchestrator. Track and maintain cache hit rates.

| Metric | Target | Action if below |
|--------|--------|----------------|
| Local cache hit rate | 80%+ | Check `inputs` and `outputs` config in turbo.json |
| Remote cache hit rate | 70%+ | Verify CI populates the cache, check hash inputs |
| Cache miss on unchanged package | 0% | Audit environment variables leaking into hash |

Common cache-busting culprits: timestamps in build output, environment variables not listed in `globalEnv`, non-deterministic code generation.

## Dependency Boundaries

No cross-package source imports. Packages consume each other through their published entry points, never by reaching into `src/` directly.

```typescript
// Wrong: importing source files across package boundary
import { formatDate } from "@acme/shared-utils/src/date";

// Correct: importing from the package entry point
import { formatDate } from "@acme/shared-utils";
```

Enforce this with an ESLint rule. `eslint-plugin-boundaries` or `@nx/enforce-module-boundaries` prevent cross-package source access at lint time.

## Golden Paths for New Packages

Provide a template or generator for creating new packages. Every new package starts with the correct structure, dependencies, and config.

A generator must produce:

- `package.json` with correct `name`, `version`, shared config references, and standard scripts
- `tsconfig.json` extending the shared base
- ESLint and Prettier configs extending shared bases
- A `src/index.ts` entry point
- A basic test file
- Registration in the orchestrator's workspace config

Use `pnpm create` with a workspace template, Nx generators, or Turborepo's `gen` command. Never copy-paste an existing package and rename, that carries stale config and unnecessary dependencies.

## CI Pipeline Structure

Structure CI to leverage the orchestrator's dependency graph.

1. Install dependencies: `pnpm install --frozen-lockfile`.
2. Run affected tasks only: `turbo run build test lint --filter=...[origin/main]`.
3. On main branch: run all tasks to populate the remote cache.
4. Cache `node_modules` and `.turbo` between CI runs.

Never run `pnpm -r build` or iterate over packages manually. The orchestrator handles parallelism, ordering, and caching.
