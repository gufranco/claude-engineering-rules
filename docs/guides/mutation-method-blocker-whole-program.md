# Whole-Program Mutation Tracking

Opt-in inter-file analysis for the mutation-method-blocker hook. Default OFF.

## When to enable

| Scenario | Recommendation |
|----------|---------------|
| Library codebase where exports cross module boundaries | Enable in CI on `main` |
| Single-file edits during day-to-day work | Leave disabled. The per-file detector covers 95% of cases |
| Pre-release audits or refactors that move shared state | Enable temporarily |
| Sub-200ms PreToolUse budget required | Leave disabled. Cold-cache analysis can exceed 500ms |

## Enabling

Set the env var before invoking the hook or in your shell profile.

```bash
export MUTATION_METHOD_WHOLE_PROGRAM=1
```

For CI, pin the limits explicitly:

```yaml
env:
  MUTATION_METHOD_WHOLE_PROGRAM: "1"
  MUTATION_METHOD_WP_MAX_FILES: "5000"
  MUTATION_METHOD_WP_TIMEOUT_MS: "2000"
```

## What it does

1. Walks the project root, which is the nearest ancestor of the edited file containing `.git` or `package.json`.
2. Parses each JS/TS file for `import` and `export` declarations using lightweight regex matching.
3. Builds an inter-file call graph: nodes are files, edges are import specifiers.
4. After the per-file detector runs, cross-references symbols that mutate AND are exported AND are imported elsewhere.
5. Each cross-module hit is annotated as advisory: the hook does not block on it, but surfaces it in the SARIF output and audit log.

## What it does NOT do

- Full type resolution. Use the ts-morph bridge for that, see below.
- Re-export following across barrels. A symbol re-exported through `index.ts` may evade detection.
- Dynamic `import()` analysis.
- Call-site argument flow tracking. A mutation flagged as "leaked" may not actually be reachable from callers.

Treat findings as hints, not verdicts. The hook never blocks on whole-program output alone.

## Performance budget

| Project size | Cold cache | Warm cache |
|--------------|-----------|------------|
| 100 files | <50 ms | <10 ms |
| 1000 files | <500 ms | <50 ms |
| 5000 files | <2000 ms | <200 ms |

Beyond 5000 files, the tracker truncates and sets `graph.truncated=True`. Cache is invalidated on `package.json` or `tsconfig.json` changes.

## Type bridge integration

When `MUTATION_METHOD_TYPE_BRIDGE=1` is also set, the tracker delegates ambiguous receivers to `scripts/mutation_type_bridge.py`, which spawns a `ts-morph`-based Node helper. The bridge has a hard 200ms per-query timeout. See `scripts/mutation_type_bridge.py` docstring for full details.

If you have TypeScript 5.6+, opt into the new Project Service protocol for faster queries:

```bash
export MUTATION_METHOD_TS_PROJECT_SERVICE=1
```

## Disabling

Unset the env var. The hook returns to its default per-file mode.

```bash
unset MUTATION_METHOD_WHOLE_PROGRAM
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hook latency >1s on every Edit | Whole-program enabled with no cache | Move `MUTATION_METHOD_WHOLE_PROGRAM` out of the default profile, enable only in CI |
| `truncated=True` on every run | Project exceeds 5000 files | Increase `MUTATION_METHOD_WP_MAX_FILES` or narrow scope |
| Cross-module hits with no actionable info | Bridge disabled | Set `MUTATION_METHOD_TYPE_BRIDGE=1` and `pnpm install ts-morph` |
| Helper exits with code 1 silently | `ts-morph` not installed | Run `pnpm install ts-morph` at the project root |

## Cross-references

- `scripts/mutation_whole_program.py`, the implementation.
- `scripts/mutation_type_bridge.py`, the ts-morph bridge.
- `scripts/ts_bridge_helper.js`, the Node helper for the bridge.
- `rules/lang/typescript-immutability.md`, Mutation Surface section.
