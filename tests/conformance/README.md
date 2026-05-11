# Mutation-method-blocker conformance suite

Test262-style behavior verification for the hook. Each `.test.ts` file has
YAML frontmatter declaring the expected detector verdict, and the test
runner under `tests/conformance/test_conformance.py` runs the hook against
each case and asserts the verdict matches.

## Verdict values

| Verdict | Hook exit code | Meaning |
|---------|---------------|---------|
| `allow` | 0 | Code is allowed, no mutation flagged |
| `block` | 2 | Code contains a mutation the hook must block |
| `defer` | 0 | Hook deferred (file outside scope, suppressed, etc.) |
| `ask` | 1 | Hook asked the user for guidance (rare) |

## Frontmatter format

```yaml
---
description: short one-line description of the case
verdict: block
detector: array.push
payload: edit
file: /repo/src/business/example.ts
---
const items = []
items.push(1)
```

| Field | Required | Description |
|-------|----------|-------------|
| `description` | yes | Human-readable summary used in test output |
| `verdict` | yes | Expected outcome: allow, block, defer, ask |
| `detector` | optional | Detector code that must fire when verdict=block |
| `payload` | optional | `write` (default) or `edit` |
| `file` | optional | Defaults to `/repo/src/business/conformance.ts` |

## Adding cases

1. Pick the next free filename under `cases/<category>/<NNN>-description.test.ts`.
2. Write the frontmatter and the test body.
3. Run `python3 -m pytest tests/conformance/`.

The CI gate requires at least 95% of cases pass.
