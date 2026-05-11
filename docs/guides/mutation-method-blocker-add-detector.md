# How to Add a New Detector to mutation-method-blocker

This guide walks through adding a new mutation detector to the hook. Worked example: detecting mutation methods on `URLSearchParams`.

## When this applies

A new detector is warranted when:

- A built-in JavaScript or DOM API has mutation methods that produce non-obvious side effects.
- The mutation pattern is not already covered by an existing detector.
- Users are likely to write the mutation by reflex, expecting an immutable result.

`URLSearchParams.set`, `.append`, `.delete`, and `.sort` all mutate the underlying params object in place. Code that does `const next = params.set('q', '1')` silently produces `undefined`. A detector flags the mutation and suggests `new URLSearchParams([...params, ['q', '1']])`.

## Worked example: URLSearchParams

### Step 1: Catalog the mutation surface

Read MDN for the API and list every mutating method:

| Method | Effect | Returns |
|--------|--------|---------|
| `set(name, value)` | Replaces all values for `name` | `undefined` |
| `append(name, value)` | Adds a new entry | `undefined` |
| `delete(name)` | Removes all entries for `name` | `undefined` |
| `sort()` | Sorts entries in place | `undefined` |

Non-mutating methods (`get`, `getAll`, `has`, `entries`, `keys`, `values`, `toString`, `forEach`) are safe and not flagged.

### Step 2: Define the detection signal

Three options:

| Signal | Strength | Cost |
|--------|----------|------|
| Receiver name heuristic (variable named `params`, `searchParams`, `query`) | Weak | Free |
| Constructor tracking (`new URLSearchParams(...)` assignment) | Strong | Cheap with regex over preceding lines |
| AST type analysis (variable typed `URLSearchParams`) | Strongest | Requires `ast-grep` |

Start with constructor tracking. Add AST type analysis as the escalation path when `ast-grep` is on PATH. Receiver-name heuristic is too weak; it would over-flag `params` arguments to unrelated functions.

### Step 3: Add the detector function

Open `scripts/mutation_detectors_dom.py` (or create it if it does not yet exist for the category). Add:

```python
URLSEARCHPARAMS_CONSTRUCTOR_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<var>[a-zA-Z_$][\w$]*)\s*=\s*new\s+URLSearchParams\b"
)

URLSEARCHPARAMS_MUTATION_METHODS = ("set", "append", "delete", "sort")


def detect_urlsearchparams_mutation(
    text: str,
    lang: str,
    file_path: str,
) -> list[Match]:
    if lang not in ("ts", "tsx", "js", "jsx"):
        return []
    tracked: set[str] = set()
    for m in URLSEARCHPARAMS_CONSTRUCTOR_PATTERN.finditer(text):
        tracked.add(m.group("var"))
    if not tracked:
        return []

    results: list[Match] = []
    method_alt = "|".join(URLSEARCHPARAMS_MUTATION_METHODS)
    pattern = re.compile(
        rf"(?P<recv>[a-zA-Z_$][\w$]*)\.(?P<method>{method_alt})\("
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in pattern.finditer(masked):
            if m.group("recv") not in tracked:
                continue
            results.append(_make_match(
                detector="dom.url-search-params-mutation",
                line=lineno,
                col=m.start(),
                source_line=raw,
                fix_hint=(
                    "URLSearchParams mutation methods modify in place. "
                    "Use `new URLSearchParams([...params, [name, value]])` "
                    "to produce a new instance."
                ),
                metadata={"receiver": m.group("recv"), "method": m.group("method")},
            ))
    return results
```

### Step 4: Register the detector

Open `hooks/mutation-method-blocker.py` and add the import:

```python
from mutation_detectors_dom import detect_urlsearchparams_mutation
```

In `_collect_matches()`, append the call:

```python
matches.extend(detect_urlsearchparams_mutation(text, lang, file_path))
```

If the detector should be experimental, gate it with `_experimental_enabled("URL_SEARCH_PARAMS_MUTATION")` instead.

### Step 5: Add a confidence score adjustment

Open `hooks/mutation_confidence.py` and add a case for the new detector:

```python
if detector == "dom.url-search-params-mutation":
    score += 3  # canonical pattern match
    if ast_confirmed:
        score += 2
    if receiver_known:  # variable typed as URLSearchParams via ts type
        score += 2
    return min(max(score, 1), 10)
```

A typical match scores 6 (3 base + 3 canonical) without AST and 8 with AST + receiver type.

### Step 6: Add fixtures

`tests/corpus/mutation-method-blocker/dom/url-search-params/dirty.ts`:

```typescript
const params = new URLSearchParams(window.location.search);
params.set('q', 'hello');
params.append('tag', 'a');
params.delete('old');
params.sort();
```

`tests/corpus/mutation-method-blocker/dom/url-search-params/clean.ts`:

```typescript
const params = new URLSearchParams(window.location.search);
const next = new URLSearchParams([...params, ['q', 'hello']]);
const filtered = new URLSearchParams(
  [...params].filter(([k]) => k !== 'old'),
);
const sorted = new URLSearchParams([...params].toSorted());
```

Update the corpus index with the new fixtures.

### Step 7: Add unit tests

Create `tests/hooks/mutation-method-blocker/test_urlsearchparams_detector.py`:

```python
def test_set_method_blocked() -> None:
    code, err = _run_hook(_payload("const p = new URLSearchParams(); p.set('a', 'b');"))
    assert code == 2
    assert "url-search-params" in err.lower()


def test_non_tracked_variable_not_flagged() -> None:
    code, _ = _run_hook(_payload("const p = makeMyOwnSet(); p.set('a', 'b');"))
    assert code == 0


def test_get_method_not_flagged() -> None:
    code, _ = _run_hook(_payload("const p = new URLSearchParams(); p.get('a');"))
    assert code == 0
```

### Step 8: Verify performance

Run the perf benchmark:

```bash
python3 -m pytest tests/test_mutation_blocker_perf.py -v
```

The added detector must not push the suite outside the budget (p95 < 180ms with AST on, p99 < 250ms, mean < 60ms). If the budget is exceeded, the detector is too expensive: cache the constructor scan, narrow the regex, or skip files that obviously do not use the API.

### Step 9: Run the corpus

```bash
python3 scripts/corpus_manage.py validate --fail-under 99.0
```

The result must stay at or above 99.0% pass rate. A new detector that drops the rate below threshold is over-flagging; tighten the receiver tracker or add allowlist signals.

### Step 10: Update documentation and triggers

| Surface | What to add |
|---------|-------------|
| Mutation Surface section | New row for URL/Web API mutation methods |
| Hook Coverage table in the project README | Increment the DOM/Web API count |
| Index of on-demand triggers | Keywords like `urlsearchparams`, `url-search-params` |
| Standards documentation for the relevant runtime | A note about non-mutating alternatives |

## Detector design checklist

Before merging a new detector:

- [ ] Receiver discrimination: does the detector flag only the intended type, not lookalikes?
- [ ] Mutation surface: are all mutating methods covered, with non-mutating methods excluded?
- [ ] Confidence inputs: does the detector contribute AST and receiver-type signals to the scorer?
- [ ] Allowlist alignment: does the detector skip files in known auto-allowed scopes?
- [ ] Performance: does the detector stay within its share of the budget?
- [ ] Fixture symmetry: are there both `clean.ts` and `dirty.ts` fixtures?
- [ ] Regression test: does the unit test cover the negative case (lookalike receiver)?
- [ ] Fix hint: does the message suggest a non-mutating replacement?

## Common pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Receiver name collision | `request.set(...)` flagged when `request` is unrelated | Use constructor tracking, not name heuristic |
| Type-only import miss | Variable is typed via type-only import; constructor tracker misses it | Add an import-pattern signal |
| Method name overlap | Different APIs use the same method name (e.g., `Map.set` vs `URLSearchParams.set`) | Restrict the detector to receivers known to be of the target type |
| String literal false positive | Regex matches `"params.set('a', 'b')"` inside a comment or string | Use the `_iter_lines` masked-string helper which strips strings and comments |
| Performance hit on large files | Detector scans every line for every match | Pre-filter: bail out early if the constructor pattern is not present |

## Validation gate

A new detector is complete when:

- Detector function lives in the appropriate `scripts/mutation_detectors_*.py` file.
- Hook orchestrator registers and calls it.
- Confidence scoring contributes the new detector.
- Corpus has matched fixtures (`clean.ts`, `dirty.ts`).
- Unit tests assert both directions.
- Corpus benchmark stays at or above threshold.
- Performance benchmark is within budget.
- Project documentation references the new detector.
