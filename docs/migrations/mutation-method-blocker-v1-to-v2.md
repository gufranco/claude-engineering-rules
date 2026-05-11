# Migration Guide: mutation-method-blocker v1 to v2

**Audience:** users on a Claude Code config that pre-dates the v2 expansion of mutation detection. Read this before upgrading to confirm what changes, what stays the same, and what to verify after the upgrade.

## At a glance

| Area | v1 | v2 |
|------|----|----|
| Detector count | ~10 patterns, single category (array methods) | 50+ patterns across 9 categories |
| Output channel | stderr + `sys.exit(2)` | v2 envelope on stdout AND v1 stderr (dual-emit) |
| Detection engine | regex only | regex with optional AST escalation via `ast-grep` |
| Bypass surface | `MUTATION_METHOD_DISABLE=1` global | global env var, `eslint-disable-next-line`, `@ts-expect-error`, project-local config |
| Output format | human stderr only | human stderr (default), SARIF 2.1.0 (`MUTATION_METHOD_OUTPUT=sarif`) |
| Confidence | binary block-or-allow | 1-10 score; below 5 emits warning, 5-6 emits block with caveat, 7-10 emits block |
| Performance budget | p95 < 200ms | p95 < 180ms with AST on, p99 < 250ms, mean < 60ms |
| Hook version | < 2.0.0 | 2.0.0 |

## Breaking changes

There are no hard breaking changes. Every v1 contract is preserved. The migration is additive.

| What you might assume changed | What actually changed |
|-------------------------------|------------------------|
| stderr is the primary block channel | stderr is still emitted on every block. v2-aware tooling reads stdout. v1 scrapers keep working |
| `MUTATION_METHOD_DISABLE=1` was renamed | Same name, same behavior |
| Exit code on block | Still `2` |
| `sys.exit(2)` was removed | Still called when `CLAUDE_HOOK_API_VERSION` is unset or `1` |

## New env vars

| Variable | Purpose | Default |
|----------|---------|---------|
| `MUTATION_METHOD_AST` | Enable or disable AST escalation | `1` if `ast-grep` is on PATH, else `0` |
| `MUTATION_METHOD_OUTPUT` | Switch output format | `human` (stderr). Set to `sarif` for SARIF 2.1.0 on stdout |
| `MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN` | Enable the experimental optional-chain-assignment detector (`obj?.field = v`) | unset (off) |
| `CLAUDE_HOOK_API_VERSION` | Hook output protocol version | Set by the runtime. Hook degrades to v1 on any non-`2` value |

## Renamed env vars

None. Every v1 env var keeps its v1 name.

## New audit log fields

The audit log entry per block now includes:

| Field | Type | Notes |
|-------|------|-------|
| `confidence` | int (1-10) | Computed score; emitted on every finding |
| `detector` | string | Detector identity, e.g. `array.push`, `object.assign`, `delete-operator` |
| `ast_confirmed` | bool | True if AST escalation confirmed the match |
| `receiver_known` | bool | True if the receiver type was identified (from import scope or AST) |
| `category` | string | One of: `array`, `object`, `collection`, `typed-array`, `date-setter`, `delete`, `global`, `param-reassign`, `let-could-be-const` |

Existing fields (`timestamp`, `tool_name`, `file_path`, `decision`, `reason`) are unchanged.

## New fixtures

The corpus at `tests/corpus/mutation-method-blocker/` expands to cover:

- Pinia stores (`*Store.ts` and `defineStore({ ... })`)
- Redux Toolkit slices (`*Slice.ts` and `createSlice({ reducers })`)
- MobX (`makeAutoObservable`, `runInAction`, `action`)
- Zustand with `produce` (Immer middleware)
- Yjs CRDTs (`new Y.Array`, `new Y.Map`, `new Y.Text`)
- Valtio proxies
- TypedArray hot paths (`crypto`, `codec`, `image`, `audio`, etc.)
- Date setter contexts (raw `Date.prototype.setMonth` flagged; date-fns `setMonth(date, m)` allowed)
- DOM read/write divides (`element.dataset.foo = ...` flagged; `element.classList.add(...)` allowed)
- Framework navigation receivers (`router.push`, `history.push`, `redirect.push`)

Each fixture is a `clean.ts` (must pass) or `dirty.ts` (must block) file in a category subdirectory.

## Step-by-step migration

### 1. Verify the current hook version

```bash
python3 hooks/mutation-method-blocker.py --version
```

Output should print `2.0.0`. If it prints something earlier, pull the latest config.

### 2. Confirm dual-emit works

Run the regression tests:

```bash
python3 -m pytest tests/hooks/mutation-method-blocker/test_v1_backward_compat.py -v
```

All four tests must pass:

- `test_v1_stderr_emitted_when_api_version_unset`
- `test_v1_stderr_emitted_when_api_version_1`
- `test_v2_envelope_emitted_alongside_v1`
- `test_v1_stderr_emitted_when_api_version_garbage`

### 3. Enable AST escalation (recommended)

```bash
which ast-grep || brew install ast-grep
```

The hook detects `ast-grep` at startup and uses it automatically. Disable explicitly with `MUTATION_METHOD_AST=0` if needed.

### 4. Wire SARIF for CI (optional)

In your CI workflow, set:

```yaml
env:
  MUTATION_METHOD_OUTPUT: sarif
```

Then upload the captured stdout to GitHub Code Scanning via `actions/upload-sarif`.

### 5. Add a project-local config (optional)

Create `<project-root>/.claude/mutation-allowlist.yml`:

```yaml
version: 1
framework_receivers:
  - "myCustomRouter"
hot_path_segments:
  - "src/codec"
disable_detectors:
  - "let-could-be-const"
```

The schema is at `schemas/mutation-allowlist.schema.json`. Unknown fields produce warnings, not errors.

### 6. Watch the audit log

After the upgrade, run a normal day's work and check the audit log:

```bash
python3 scripts/audit_log_summary.py --hook mutation-method-blocker --since 1d
```

A spike in low-confidence findings indicates a corpus gap (new pattern that needs an allowlist) or a detector regression. File a fixture and tighten the rule.

## Rollback

The hook honors a global disable for emergency rollback:

```bash
export MUTATION_METHOD_DISABLE=1
```

Set this in the shell or in `settings.json` and the hook will allow every operation. Use only as a stopgap; the rule itself remains in effect.

To roll back to a v1 version of the hook, check out the previous commit on the config repo and reinstall. v1 fixtures in the corpus stay valid.

## Verification checklist

After migrating:

- [ ] `python3 -m pytest tests/hooks/mutation-method-blocker/` passes with zero failures and zero warnings
- [ ] `python3 scripts/corpus_manage.py validate --fail-under 99.0` returns success
- [ ] A test Write of a known-mutation produces both v1 stderr AND v2 stdout JSON
- [ ] A test Write of a known-clean Immer/Pinia/Redux scope is allowed
- [ ] If SARIF was enabled, the document validates against the OASIS 2.1.0 schema
- [ ] The audit log shows the new fields (`confidence`, `detector`, `ast_confirmed`, `receiver_known`, `category`)
