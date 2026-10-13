# Frontend Render Gate

A change to markup, styles, theme tokens, or the component tree is unverified until a real engine has rendered it. A diff read, a jsdom test, or a clean type check is never render evidence.

- Extend the project's browser harness when one exists; assert computed style and the accessibility tree, never class names.
- Name the viewport, including the smallest supported width when layout changes.
- Drive every entry point, read the persisted write back, and require empty page errors and console; the PR body states what was clicked and seen, or `No UI change`.
- Mobile needs a simulator or emulator run; a widget test is not enough. If unverified, say so.

`agent-browser` is installed globally:

```bash
agent-browser open http://localhost:4502/some/route
agent-browser eval "document.getElementById('pay').focus(); getComputedStyle(document.activeElement).boxShadow"
agent-browser snapshot -i
agent-browser set device "iPhone 12"
```

Full rule, examples, and rationale: [`standards/frontend-render-gate.md`](../standards/frontend-render-gate.md). Read it before verifying any UI or mobile change.

## Enforcement

Enforced by: [`hooks/frontend-render-gate.py`](../hooks/frontend-render-gate.py).

## Provenance

Added 2026-08-20, recurrence not recorded. Origin: not recorded at creation.
