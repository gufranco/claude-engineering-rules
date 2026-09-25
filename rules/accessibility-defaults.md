# Accessibility Defaults

Every frontend task targets WCAG 2.2 AA, plus AAA where it does not conflict with AA.

- Every interactive element is keyboard operable and exposes name, role, and state; every input has a label.
- Targets 44x44 CSS px, 48x48 on Android; contrast floor 4.5:1 for text, 3:1 for large text, UI, and focus rings.
- Honor `prefers-reduced-motion`; `lang` on `<html>`; no image CAPTCHA; never `tabindex` above 0.

Full rule, examples, and rationale: [`standards/accessibility-defaults.md`](../standards/accessibility-defaults.md). Read it before writing or reviewing any UI markup.
