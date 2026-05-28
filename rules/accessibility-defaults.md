# Accessibility Defaults

## Scope

Every frontend task. The rule is loaded by default per [`compliance-defaults.md`](compliance-defaults.md). Full conformance target: WCAG 2.2 Level AA mandatory + Level AAA where it does not conflict with AA.

## Mandatory Targets

| Target | Rule |
|--------|------|
| WCAG version | 2.2 AA at minimum; 2.2 AAA where feasible |
| Older criteria removed in 2.2 (e.g., 4.1.1 Parsing) | Keep meeting them; valid HTML costs nothing |
| Keyboard operability | Every interactive element reachable and operable via Tab, Enter, Space, Escape, and arrow keys |
| Name, role, state | Every interactive element exposes name, role, and state to assistive tech |
| Programmatic label | Every form input has a `<label>`, `aria-label`, or `aria-labelledby` |
| Heading order | One `<h1>` per page; no skipped heading levels |
| Page language | `<html lang="...">` on every page; `lang` attribute on any inline content in a different language |
| Focus indicator | Visible focus ring with 3:1 contrast against adjacent colors |
| Target size | 44x44 CSS pixels minimum (locked above the WCAG 2.5.8 AA floor of 24x24); 48x48 on Android |
| Color contrast | 4.5:1 floor for body text, 3:1 for large text and UI components, 7:1 target |
| Reduced motion | `prefers-reduced-motion: reduce` honored on every animation and transition |
| Authentication | Passkey, OAuth, or magic link; no image-recognition CAPTCHA, no math puzzle |
| Time limits | User-adjustable; 20-second warning + one-click extension within security envelope |
| Sign language for video | Provided where a signing community exists for the locale (Libras, LSF, DGS, BSL, ASL, LSE) |
| Locale equivalence | Every accessibility feature implemented for every supported language |
| Accessibility statement | Required on every project; template in [`../standards/accessibility-testing.md`](../standards/accessibility-testing.md) |
| Mobile | Same WCAG 2.2 AA + EN 301 549 mobile clauses applied to native apps |

## Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| `<img>` without `alt` attribute | WCAG 1.1.1 fails immediately |
| Decorative image without `alt=""` | Screen reader announces the file path |
| Icon-only button without `aria-label` | Button has no accessible name |
| `<input>` without label, `aria-label`, or `aria-labelledby` | WCAG 3.3.2 fails |
| `role="button"` on `<div>` or `<span>` without keyboard handler | WCAG 2.1.1 fails |
| `tabindex` > 0 | Breaks logical tab order |
| Missing `lang` on `<html>` | WCAG 3.1.1 fails |
| `<a>` without `href` (other than placeholder during prototyping) | Not focusable, not announced as link |
| Click handler on `<div>` or `<span>` without `role`, `tabIndex`, and key handlers | WCAG 2.1.1 fails |
| `aria-hidden="true"` on a focusable element | Focus lands on invisible content |
| Color-only meaning (e.g., red border without text) | WCAG 1.4.1 fails |
| Auto-playing audio without control | WCAG 1.4.2 fails |
| Image CAPTCHA without non-cognitive alternative | WCAG 3.3.8 fails |

## Mechanical Enforcement

The hook [`../hooks/accessibility-mechanical-checks.py`](../hooks/accessibility-mechanical-checks.py) catches the highest-signal forbidden patterns at write time. Bypass env: `ACCESSIBILITY_CHECKS_DISABLE=1` (parent shell only).

## Audit Workflow

For every frontend change:

1. The accessibility-auditor agent runs unconditionally (see [`../agents/accessibility-auditor.md`](../agents/accessibility-auditor.md)).
2. Automated tests via axe-core (jest-axe, playwright-axe, or cypress-axe) at the component layer.
3. Lighthouse CI threshold ≥ 0.9 accessibility score.
4. Pa11y CI on multi-page audits with zero errors.
5. Manual pass: keyboard navigation, screen reader on one desktop + one mobile, zoom 400%, reduced-motion enabled.

## Law Coverage

The rule covers the union of WCAG 2.2 AA + AAA-aspirational obligations from every accessibility law in Europe, North America, and South America. Per-law citations and effective dates in the spec folder's `references.md`. Authority for conflict resolution: spec folder's `conflicts.md`.

## Cross-References

- [`compliance-defaults.md`](compliance-defaults.md): umbrella rule, locked targets
- [`../standards/accessibility-testing.md`](../standards/accessibility-testing.md): full implementation guide
- [`../standards/frontend.md`](../standards/frontend.md): frontend patterns with cross-links
- [`../agents/accessibility-auditor.md`](../agents/accessibility-auditor.md): per-change auditor agent
- [`../checklists/checklist.md`](../checklists/checklist.md): verification gates
