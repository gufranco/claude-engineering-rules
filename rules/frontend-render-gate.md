# Frontend Render Gate

A change to markup, styles, theme tokens, the component tree, a desktop layout, or a terminal UI is unverified until a real engine has rendered it, and unreviewable until the reviewer can see it. A diff read, a jsdom test, or a clean type check is never render evidence.

- Extend the project's browser harness when one exists; assert computed style and the accessibility tree, never class names.
- Name the viewport, including the smallest supported width when layout changes.
- Drive every entry point, read the persisted write back, and require empty page errors and console; the PR body states what was clicked and seen, or `No UI change`.
- Mobile needs a simulator or emulator run; a widget test is not enough. If unverified, say so.
- Every pull request, review reply, issue, issue answer, and tracker comment about a visible change must attach screenshots labeled `Before:`, unless the surface is new, and `After:`. Web, mobile, desktop GUI, and TUI alike.
- Screenshots are high resolution: device scale 2 or more, longer side at least 1600 px. Before comes from the base commit with the same data, viewport, theme, and locale.
- Upload with `gh ... --attach '<file>#After: <screen>'`; never commit screenshots or host them elsewhere.

`agent-browser` is installed globally:

```bash
agent-browser open http://localhost:4502/some/route
agent-browser eval "document.getElementById('pay').focus(); getComputedStyle(document.activeElement).boxShadow"
agent-browser snapshot -i
agent-browser set device "iPhone 12"
```

Full rule, examples, and rationale: [`standards/frontend-render-gate.md`](../standards/frontend-render-gate.md). Read it before verifying any UI or mobile change, and before publishing text about one.

## Enforcement

Enforced by: [`hooks/frontend-render-gate.py`](../hooks/frontend-render-gate.py).

## Provenance

Added 2026-08-20, recurrence not recorded. Origin: not recorded at creation. Amended 2026-10-28, by direct user instruction: visible changes publish high-resolution before and after screenshots in every channel and on every platform, because visibility is a reviewer's main criterion for an interface; the hook now enforces it at publish time.
