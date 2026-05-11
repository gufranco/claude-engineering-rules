# Troubleshooting mutation-method-blocker

A reference for diagnosing the four kinds of trouble: false positives, false negatives, performance issues, and audit log questions.

## False positives (the hook blocked legitimate code)

A false positive is the hook blocking code that follows the rule. Common causes and fixes.

### Symptom: known state-library code is blocked

The hook flagged `state.count = 1` inside a recognized Pinia store, MobX action, Redux Toolkit reducer, or similar.

**Diagnose.** Check whether the file has the expected signal:

```bash
grep -c "import .* from 'pinia'" path/to/file.ts
```

If the import is missing, the hook fell back to filename-pattern matching, which may have failed. If the import is present, the AST signal may have failed silently (e.g., `ast-grep` not installed or version mismatch).

**Fix options.**

| Cause | Fix |
|-------|-----|
| Filename does not match the library's convention | Rename the file or extend the filename pattern in the allowlist |
| `ast-grep` not installed | Install it (`brew install ast-grep`) and rerun |
| Library variant uses unconventional API | Add a fixture and extend the receiver tracker |
| Genuine edge case the library lets through | Use `eslint-disable-next-line` on the specific line with a justification |

### Symptom: legitimate framework navigation flagged

The hook blocked `router.push('/path')` or similar. The framework navigation receivers should be auto-allowed.

**Diagnose.** Confirm the receiver name matches the auto-allowed list (`router`, `history`, `navigation`, `redirect`).

**Fix.** If the project uses a custom router, add the receiver name to the project-local config:

```yaml
version: 1
framework_receivers:
  - "myCustomRouter"
```

Save as `<project-root>/.claude/mutation-allowlist.yml` and rerun.

### Symptom: TypedArray code in a hot-path directory flagged

The hook blocked `buffer.set(...)` or `array.fill(...)` in code that is genuinely a codec, parser, image processor, or similar performance-critical scope.

**Diagnose.** Check whether the file path contains one of the auto-allowed segments (`crypto`, `codec`, `image`, `audio`, `parser`, `wasm`, `canvas`, `encoder`, `decoder`, `simd`, `webgl`, `pixel`, `hash`, `cipher`).

**Fix.** Either move the file into one of the recognized segments, or extend the allowlist via the project-local config:

```yaml
version: 1
hot_path_segments:
  - "src/my-custom-decoder"
```

### Symptom: `let`-could-be-`const` flagged on a real reassignment

The hook claimed a `let` could be `const` even though the variable is reassigned later in the file.

**Diagnose.** This detector runs only on full-file Write payloads. If the reassignment is in a different file (cross-file flow), the detector cannot see it. If the reassignment is inside a closure that the regex did not parse, the detector may have missed it.

**Fix.** Open an issue with the offending file as a fixture. The detector should escalate to AST analysis to handle closures correctly. As a stopgap, suppress with `// eslint-disable-next-line prefer-const` plus a justification.

## False negatives (the hook allowed bad code)

A false negative is the hook missing a real mutation. These hurt more than false positives because the rule degrades silently.

### Symptom: a mutation pattern was not caught

A user wrote `obj['prop'] = value` (bracket-string assignment) and the hook did not block it.

**Diagnose.** Run the detector directly:

```bash
python3 -c "
from mutation_detectors_assignments import detect_property_assignment
import json
matches = detect_property_assignment('obj[\"prop\"] = value;', 'ts', '/tmp/x.ts')
print(json.dumps([{'detector': m.detector, 'line': m.line} for m in matches], indent=2))
"
```

If the function returns no matches, the detector logic missed the case. If the function returns matches but the hook still allowed the operation, an allowlist signal is over-firing.

**Fix.** Add the case as a `dirty.ts` fixture in the corpus. Run `corpus_manage.py validate` and confirm the fixture is now caught. If not, extend the detector regex or AST query.

### Symptom: a known state library missed mutation outside the recognized scope

The hook allowed `state.count = 1` even though `state` was a plain object, not a Pinia/MobX/Redux store.

**Diagnose.** The allowlist is over-firing. Check whether the file has any signal that triggered the allowlist:

```bash
grep -E "(defineStore|createSlice|makeAutoObservable|proxy\()" path/to/file.ts
```

If any of those tokens appear, the file-level allowlist may have applied even though the specific variable was not a tracked state object.

**Fix.** Tighten the receiver tracker. The allowlist should only apply to mutations whose receiver is a tracked variable, not to all mutations in any file that imports the library.

## Performance issues

### Symptom: the hook is slow

The hook takes more than the budget (p95 < 180ms with AST on, p99 < 250ms, mean < 60ms).

**Diagnose.** Run the perf benchmark:

```bash
python3 -m pytest tests/test_mutation_blocker_perf.py -v
```

Profile the hot path:

```bash
python3 scripts/bench_mutation_blocker.py --profile
```

The output lists the top time-consuming functions. Common culprits:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `_iter_lines` dominates | Source is being scanned multiple times | Cache the masked-string view |
| AST escalation runs on every detector | `ast-grep` is invoked per detector instead of once | Parse once, reuse the AST |
| Regex compilation in hot loop | Pattern is being compiled inside the function | Move `re.compile` to module scope |
| State-library tracker walks the full file | Receiver scan is unbounded | Pre-filter by import presence |

### Symptom: the hook is slow only on specific files

The hook is fast on small files but slow on large ones (>10KB).

**Diagnose.** Read the file size threshold for AST escalation. Large files may exceed the parse budget for `ast-grep`.

**Fix.** Add a size guard: files over a configurable threshold (e.g., 50KB) skip AST escalation and use regex only. Document the threshold in the perf budget.

### Symptom: AST escalation makes things worse

With `MUTATION_METHOD_AST=1`, the hook is slower than with AST off, even on systems with `ast-grep` installed.

**Diagnose.** Check the `ast-grep` version:

```bash
ast-grep --version
```

Older versions had cold-start costs that exceeded warm-parse savings. The hook expects 0.16+.

**Fix.** Upgrade `ast-grep`. If upgrading is not an option, set `MUTATION_METHOD_AST=0` and accept the regex baseline.

## Audit log inspection

The audit log is the source of truth for what the hook decided and why. Inspect it when symptoms are unclear.

### Find recent blocks

```bash
python3 scripts/audit_log_summary.py --hook mutation-method-blocker --since 1d
```

Outputs counts by detector and decision. A detector that fires more often than expected may have a false-positive bias.

### Inspect a specific finding

```bash
python3 scripts/audit_log_summary.py \
  --hook mutation-method-blocker \
  --since 1h \
  --detector "array.push" \
  --format json | head -20
```

Each entry has: `timestamp`, `detector`, `decision`, `file_path`, `line`, `confidence`, `ast_confirmed`, `receiver_known`, `category`. The `confidence` field is the primary diagnostic for false-positive concerns: low confidence on a frequent block suggests the detector is firing on lookalikes.

### Find files with a high block rate

```bash
python3 scripts/audit_log_summary.py \
  --hook mutation-method-blocker \
  --since 7d \
  --group-by file_path | sort -t= -k2 -n -r | head -20
```

Files with many blocks may be candidates for an allowlist (they are state-management modules, hot-path code, or generated code).

## Bypass paths

When all else fails, escape hatches in order of preference:

| Escape | When to use |
|--------|-------------|
| `eslint-disable-next-line` with justification | A specific line is a documented exception |
| `@ts-expect-error` with comment | TypeScript suppression that doubles as the mutation suppression |
| Project-local config (`mutation-allowlist.yml`) | A repeatable pattern the hook does not yet recognize |
| `MUTATION_METHOD_DISABLE=1` | Emergency-only. The rule is still in effect even when the hook is silent |

Never disable globally as a long-term solution. Every disable is a missing fixture or detector improvement.

## When to file an issue

If after diagnosing you still cannot resolve the trouble, file an issue with:

- The minimal reproduction (a `clean.ts` or `dirty.ts` snippet).
- The expected behavior (block or allow).
- The actual behavior (with hook output).
- The relevant audit log entries.
- The hook version (`hooks/mutation-method-blocker.py --version`).
- The `ast-grep` version if AST escalation is expected.

A fixture-shaped reproduction can drop straight into the corpus and prevent regression once fixed.

## Integrating with task runners and pre-commit frameworks

The hook runs in batch mode when given filenames on stdin and `MUTATION_METHOD_BATCH_MODE=1`. The exit code is the standard CI contract: 0 on no findings, 2 on findings at or above the configured threshold.

### pre-commit (pre-commit.com framework)

The repo ships `.pre-commit-hooks.yaml` at the root. Consumers add the following to their `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/onyxodds/dot-claude
    rev: v3.0.0
    hooks:
      - id: mutation-method-blocker
```

Run manually with `pre-commit run mutation-method-blocker --all-files`. The pre-commit framework handles file selection, parallelism, and the staging-area diff.

### Husky

Husky stores hooks in `.husky/`. To wire the mutation-method-blocker into the pre-commit gate:

1. Initialize Husky once per repo: `pnpm dlx husky init`.
2. Append the runner to `.husky/pre-commit`:

```bash
#!/usr/bin/env sh
. "$(dirname -- "$0")/_/husky.sh"

git diff --cached --name-only --diff-filter=AM \
  | grep -E '\.(ts|tsx|js|jsx|mjs|cjs)$' \
  | MUTATION_METHOD_BATCH_MODE=1 \
    MUTATION_METHOD_FAIL_THRESHOLD=error \
    python3 hooks/mutation-method-blocker.py
```

Husky propagates the non-zero exit code, so a finding aborts the commit. To allow warnings without failing, set `MUTATION_METHOD_FAIL_THRESHOLD=note`.

### Lefthook

Lefthook reads `lefthook.yml`. Add a `pre-commit` group:

```yaml
pre-commit:
  parallel: true
  commands:
    mutation-method-blocker:
      glob: "*.{ts,tsx,js,jsx,mjs,cjs}"
      runner_args:
        - python3
        - hooks/mutation-method-blocker.py
      run: echo {staged_files} | tr ' ' '\n' | {runner}
      env:
        MUTATION_METHOD_BATCH_MODE: "1"
        MUTATION_METHOD_FAIL_THRESHOLD: "error"
      exclude:
        - "**/dist/**"
        - "**/build/**"
        - "**/node_modules/**"
```

Lefthook glob matching avoids invoking the hook on non-JS files.

### Biome

Biome (the Rust-based linter and formatter) does not support custom plugins as of v1.x. The recommended pattern is to run the mutation-method-blocker alongside Biome through the pre-commit framework or a `pnpm` script:

```json
{
  "scripts": {
    "lint": "biome check . && pnpm lint:mutations",
    "lint:mutations": "git ls-files '*.ts' '*.tsx' '*.js' '*.jsx' | MUTATION_METHOD_BATCH_MODE=1 python3 hooks/mutation-method-blocker.py"
  }
}
```

Biome's `--reporter=json` output is incompatible with SARIF, so they cannot be aggregated into a single report. Treat them as two independent gates: Biome enforces formatting and the lint rules it ships with, and the mutation-method-blocker enforces immutability.
