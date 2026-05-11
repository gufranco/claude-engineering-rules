# How to Add a New State Library to mutation-method-blocker

This guide walks through extending the hook's allowlist to recognize a new state-management library. Worked example: adding Valtio.

## When this applies

A state-management library that uses local mutation as the intended pattern. Typical signals:

- The library exports a factory that wraps state in a proxy or draft (`proxy()`, `produce()`, `createSlice()`, `defineStore()`).
- Inside that factory's callback or scope, `=`, `.push()`, `delete`, etc. are the documented usage.
- The library is widely adopted enough that user fixtures will trip the hook.

If the library does not encourage mutation (e.g. Recoil, Jotai with `set` callbacks), the hook already handles it via the standard immutable patterns. No allowlist needed.

## Worked example: Valtio

Valtio v5 ships a `proxy()` factory that wraps a target object. Mutations on the proxied value (`state.count = 1`, `state.items.push(item)`) trigger reactivity. The hook must allowlist mutations whose receiver is a tracked Valtio proxy variable.

### Step 1: Document the library's mutation surface

Read the library's docs and write the surface:

| Mutation kind | Example | Allow? |
|---------------|---------|--------|
| Direct property assignment | `state.count = 1` | yes |
| Nested property assignment | `state.user.name = 'a'` | yes |
| Array push on tracked array | `state.items.push(item)` | yes |
| `delete` on tracked object | `delete state.user.email` | yes |
| Mutation on non-tracked variable in same file | `const local = {}; local.x = 1` | no |

### Step 2: Identify allowlist signals

The hook recognizes scopes through three signals:

| Signal | Strength | Cost |
|--------|----------|------|
| Filename pattern (`*.valtio.ts`, `*.proxy.ts`) | Weak | Free |
| Import statement (`import { proxy } from 'valtio'`) | Strong | Cheap (regex over file head) |
| AST receiver tracking (variable assigned from `proxy(...)`) | Strongest | Requires `ast-grep` |

Pick the strongest signal available. Combine signals for defense in depth.

### Step 3: Add an entry to the allowlist registry

Open `hooks/mutation_allowlists.py` and locate the `STATE_LIBRARIES` registry. Append:

```python
STATE_LIBRARIES.append(StateLibrary(
    name="valtio",
    import_pattern=re.compile(r"from ['\"]valtio['\"]"),
    factory_names=("proxy", "ref", "snapshot"),
    filename_patterns=(re.compile(r".*\.valtio\.tsx?$"), re.compile(r".*\.proxy\.tsx?$")),
    receiver_tracker=track_valtio_receivers,
))
```

`track_valtio_receivers` is a function that walks the AST (when `ast-grep` is available) and returns the set of variable names assigned from `proxy(...)`. The hook uses this set to allowlist mutations whose receiver is in the set.

### Step 4: Implement the receiver tracker

Add to `hooks/mutation_detectors_state.py`:

```python
def track_valtio_receivers(source: str, ast_root: AstNode | None) -> set[str]:
    if ast_root is None:
        return set()
    receivers: set[str] = set()
    for node in ast_root.find_all("call_expression"):
        callee = node.child_by_field_name("function")
        if callee is None or callee.text != "proxy":
            continue
        parent = node.parent
        if parent is None or parent.type != "variable_declarator":
            continue
        identifier = parent.child_by_field_name("name")
        if identifier is not None:
            receivers.add(identifier.text)
    return receivers
```

When `ast-grep` is unavailable, `ast_root` is `None` and the function returns an empty set; the hook then falls back to the filename pattern signal.

### Step 5: Add fixtures

In `tests/corpus/mutation-method-blocker/state-libraries/valtio/`:

`clean.ts` (must pass):
```typescript
import { proxy } from 'valtio';

const state = proxy({ count: 0, items: [] as number[] });
state.count = 1;
state.items.push(2);
```

`dirty.ts` (must block):
```typescript
import { proxy } from 'valtio';

const state = proxy({ count: 0 });
const other = { count: 0 };
other.count = 1;
```

The `dirty.ts` fixture has a Valtio import but mutates a non-tracked variable (`other`). The hook must still flag that mutation.

### Step 6: Update fixture index

Add the fixtures to the corpus index file so `corpus_manage.py validate` finds them:

```json
[
  {"path": "state-libraries/valtio/clean.ts", "expected": "pass", "category": "state-library"},
  {"path": "state-libraries/valtio/dirty.ts", "expected": "block", "category": "state-library"}
]
```

### Step 7: Add a unit test

Create `tests/hooks/mutation-method-blocker/test_valtio_allowlist.py`:

```python
def test_valtio_proxy_assignment_allowed() -> None:
    code, err = _run_hook(_payload(VALTIO_CLEAN, ".ts"))
    assert code == 0
    assert "Blocked" not in err


def test_valtio_non_tracked_assignment_blocked() -> None:
    code, err = _run_hook(_payload(VALTIO_DIRTY, ".ts"))
    assert code == 2
    assert "Blocked" in err
```

### Step 8: Run the corpus benchmark

```bash
python3 scripts/corpus_manage.py validate
```

The output must show 100% pass rate including the new fixtures. If a fixture fails, debug:

- Filename signal not firing? Check the regex against the actual fixture path.
- Import signal not firing? Verify the import line matches the pattern.
- AST receiver tracker not firing? Run `ast-grep` manually on the fixture; the AST shape may differ from what the tracker expects.

### Step 9: Update documentation and triggers

Add Valtio to:

| Surface | What to add |
|---------|-------------|
| Mutation Surface section in the project guidelines | Auto-allowed scopes list |
| Index of on-demand triggers | The keyword `valtio` |
| Hook Coverage table in the project README | Increment the state-library count |
| Language standards documentation | A note about Valtio's mutation pattern under Immutability |

### Step 10: Confidence scoring

Verify that the allowlist signals feed into the confidence scorer. A mutation inside a recognized Valtio scope should produce a low score (1-4), which emits a warning rather than a block. Run a known-clean Valtio fixture through the hook with `MUTATION_METHOD_DEBUG=1` and inspect the score in the audit log.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Filename pattern too greedy | Unrelated `*.proxy.ts` files allow all mutations | Narrow the pattern, require an import-based confirmation |
| Import pattern matches type-only imports | `import type { Proxy } from 'valtio'` triggers allowlist | Use `import {.*}.*from` not just `from` |
| Receiver tracker misses destructured assignments | `const { state } = proxy({...})` not tracked | Extend the tracker to handle destructuring |
| AST shape changes across `ast-grep` versions | Tracker silently returns empty set | Pin the minimum `ast-grep` version; add a regression test |
| Fixture `clean.ts` accidentally has a real mutation | Test fails for the wrong reason | Read the fixture against the docs; valid library use only |

## Validation gate

A new state-library entry is complete when:

- Two fixtures (`clean.ts`, `dirty.ts`) exist and pass.
- Unit test asserts both directions.
- Corpus benchmark stays at 100%.
- Performance benchmark is within budget (p95 < 180ms with AST on).
- The Mutation Surface section, the project README, and the on-demand trigger index reference the new library.
- A note in the relevant standards documentation describes the library's mutation pattern.
