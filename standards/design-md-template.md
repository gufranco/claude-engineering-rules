# DESIGN.md Template

Canonical structure for a project's design system document. Adapted from the TypeUI DESIGN.md format used by design-md-chrome. Use this when scaffolding a new product or extracting a design system from an existing site.

## When to consult

- Starting a new product and codifying visual language.
- Extracting a design system from an existing site for AI-assisted UI work.
- The `/design` skill produces output in this shape.

## File placement

Place at the repository root as `DESIGN.md`. Reference from `README.md` and from any prompt that asks the assistant to generate UI.

## Required sections

```markdown
# DESIGN.md

## Mission
One paragraph. What is this product trying to do for the user. The visual language must serve this mission.

## Brand
- **Product:** Name and one-line value proposition.
- **URL:** Production URL.
- **Audience:** Primary persona, secondary persona.
- **Surfaces:** Web, mobile, desktop, email, all that apply.

## Style Foundations

### Typography
| Token | Value | Usage |
|-------|-------|-------|
| font.heading | <family>, <weight> | Page titles, section headers |
| font.body | <family>, <weight> | Body copy, labels |
| font.mono | <family>, <weight> | Code, numeric data |

Type scale, line-height ratios, letter-spacing rules.

### Color
| Token | Hex / OKLch | Usage |
|-------|-------------|-------|
| color.bg | ... | Default background |
| color.fg | ... | Default foreground |
| color.accent | ... | Primary action |
| color.danger | ... | Destructive action |
| color.muted | ... | Secondary text, disabled |

Light and dark variants when applicable. Contrast ratios verified per pair.

### Spacing
Base unit and the multiplier scale. Never use values outside the scale.

### Radius
Token list with px or rem values. Map each radius to a component class.

### Shadow
Elevation tokens. Map each level to a component class.

### Motion
Duration and easing tokens. Reduced-motion fallbacks.

## Accessibility
- WCAG 2.2 AA minimum.
- Color contrast verified for every text-on-background pair.
- Focus indicator visible on every interactive element.
- Keyboard navigation: tab order matches reading order, no traps.
- Screen reader: every icon has a label, every form control has a programmatic name.
- Reduced motion: every animation has a no-motion fallback.

## Writing Tone
- Voice descriptors. Three to five adjectives.
- Sentence length guidance.
- Words to use, words to avoid.
- Localization notes if multilingual.

## Rules

### Do
- Specific, verifiable instructions.
- One per line.

### Don't
- Specific anti-patterns.
- One per line.

## Component Expectations
For each shared component: states, interactions, loading and error behavior, keyboard handling, screen reader semantics.

| Component | States | Notes |
|-----------|--------|-------|
| Button | default, hover, active, focus, disabled, loading | Full keyboard support |
| Input | default, focus, error, disabled | Inline error message, programmatic label |
| Dialog | open, closing | Focus trap, restore focus on close, Escape to dismiss |

## Quality Gates
Testable consistency checks that any UI change must pass before merge.

- All text uses tokens from the type scale.
- All colors come from the palette.
- All spacing is on the scale.
- Every interactive element has a visible focus indicator.
- Every form control has an accessible name.
- Lighthouse accessibility score 95 or higher on changed pages.
```

## Rules

- DESIGN.md is the source of truth. When a component contradicts the document, the component is wrong.
- Update DESIGN.md in the same PR that introduces a new token, not after.
- Tokens must be defined once and consumed everywhere. No inline literals in components.
- Quality gates are verifiable. "Looks consistent" is not a gate. "All colors come from the palette" is.
