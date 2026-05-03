---
name: design
description: Design consultation, variant exploration, and design system scaffolding. Subcommands: consult (default), variants, system. Researches design patterns, proposes component hierarchies, generates design decisions document, and creates multiple visual approaches for comparison. Use when user says "design this", "design consultation", "design system", "component design", "design variants", "UI approach", "visual direction", or needs structured design thinking before implementation. Do NOT use for design review or audit of existing code (use /review design), color palette generation (use /palette), or implementation planning (use /plan).
---

Structured design skill that front-loads design decisions before implementation. Produces a DESIGN.md document and, optionally, multiple visual approaches for comparison.

## Subcommand Routing

| Invocation | Action |
|-----------|--------|
| `/design` or `/design consult <description>` | Design consultation (default) |
| `/design variants` | Generate multiple visual approaches |
| `/design system` | Scaffold a design system or component library |

If no subcommand is given, default to `consult`.

---

## consult

Research design patterns in the ecosystem, propose a component hierarchy, and produce a DESIGN.md with decisions and rationale.

### When to use

- Before building a new UI feature or component.
- When evaluating multiple visual or UX approaches.
- When establishing a design direction for a new project.

### Arguments

- No arguments: interactive mode. Ask what needs to be designed.
- `<description>`: start consultation with the given feature or component.
- `--research`: include competitive research (search for how other products solve the same problem).

### Steps

1. **Clarify requirements.** Ask one question at a time:
   - What is the user trying to accomplish?
   - What are the inputs and outputs?
   - What states exist (empty, loading, error, success, partial)?
   - What are the accessibility requirements?
   - Is there an existing design system or component library to follow?

2. **Research (if `--research` or the problem is non-trivial).** Run **in parallel**:
   - Search for similar UI patterns in the project's existing components.
   - Search for established patterns in the component library (shadcn/ui, MUI, Ant Design, etc.) if one is in use.
   - If `--research`: search the web for how other products handle this pattern.

3. **Detect the project's design foundation.** Read **in parallel**:
   - `tailwind.config.*` or CSS custom properties for design tokens.
   - `package.json` for UI library dependencies.
   - Existing components for naming and structure patterns.

4. **Propose the design.** Cover each dimension:

   | Dimension | What to specify |
   |-----------|----------------|
   | Component hierarchy | Parent, children, composition points |
   | Layout | Grid/flex strategy, responsive breakpoints |
   | Typography | Font sizes, weights, line heights for each element |
   | Color | Semantic colors from the existing palette, not hardcoded values |
   | Spacing | Margin/padding following the project's scale (4px/8px grid) |
   | States | Empty, loading, error, success, disabled, hover, focus, active |
   | Accessibility | ARIA roles, keyboard navigation, screen reader announcements |
   | Animation | Transitions, duration, easing. Respect `prefers-reduced-motion` |
   | Responsiveness | Mobile-first breakpoints and layout changes |

5. **Write DESIGN.md using the canonical 8-section schema.** Save to the project root or spec folder. Sections must appear in this order. Missing a section is a defect.

   ```markdown
   # Design: <feature name>

   ## 1. Context
   <What is the surrounding situation? What triggered this design? What does the reader need to know to understand the rest?>

   ## 2. Goals
   <What this design must achieve. Measurable when possible.>

   ## 3. Non-Goals
   <What this design explicitly does not address. Bounds the scope.>

   ## 4. Constraints
   <Technical, product, regulatory, time, or resource limits that shaped the design.>

   ## 5. Options Considered
   <At least two alternatives, each with trade-offs. Includes the option that was rejected.>

   | Option | Pros | Cons | Rejected because |
   |--------|------|------|-----------------|
   | A | ... | ... | (chosen) |
   | B | ... | ... | ... |

   ## 6. Decision
   <The chosen approach. Component hierarchy, layout, tokens, states, accessibility, animation, responsiveness.>

   ### Component Hierarchy
   ### Layout
   ### Design Tokens Used
   ### States
   | State | Visual treatment | Content |
   |-------|-----------------|---------|
   | Empty | ... | ... |
   | Loading | ... | ... |
   | Error | ... | ... |
   | Success | ... | ... |

   ### Accessibility
   <ARIA, keyboard, screen reader behavior>

   ## 7. Consequences
   <What follows from the decision. Both positive outcomes and downsides accepted.>

   ## 8. Open Questions
   <Anything unresolved that needs validation, user input, or follow-up. Empty if none.>
   ```

6. **Run the 5-dimension self-critique.** Before presenting, score the draft on each lens. State the score, the reasoning, and any fix made.

   | Lens | Question |
   |------|----------|
   | Clarity | Could a reader unfamiliar with the project follow this without asking? |
   | Completeness | Are all 8 sections present? Every state covered? Every option weighed? |
   | Feasibility | Can this be built with the project's current stack and team? |
   | Reversibility | If this design proves wrong, how hard is it to undo? Flag one-way doors. |
   | Blast radius | What breaks if this design is wrong? Who is affected, and how widely? |

   If any lens scores below 7 of 10, fix the gap before presenting. Document the score line in DESIGN.md under "Open Questions" only when the gap is acknowledged but deferred.

7. **Present for approval.** Wait for user feedback before implementation begins.

---

## variants

Generate multiple design approaches for the same requirement and present them for comparison.

### When to use

- When the design direction is unclear.
- When stakeholders need to choose between approaches.
- After `/design consult` when the user wants to see options.

### Arguments

- No arguments: use the most recent DESIGN.md for context.
- `<description>`: generate variants for the described feature.
- `--count <N>`: number of variants (default: 3, max: 5).

### Steps

1. **Read context.** Load DESIGN.md if it exists, or ask for the requirement.

2. **Generate N distinct approaches.** Each variant must differ meaningfully in at least one major dimension:
   - Layout strategy (cards vs list vs table vs timeline)
   - Information density (minimal vs detailed)
   - Interaction model (inline editing vs modal vs page navigation)
   - Visual style (compact vs spacious, flat vs layered)

3. **Present comparison:**

   | Dimension | Variant A | Variant B | Variant C |
   |-----------|----------|----------|----------|
   | Layout | ... | ... | ... |
   | Interaction | ... | ... | ... |
   | Complexity | ... | ... | ... |
   | Accessibility | ... | ... | ... |
   | Performance | ... | ... | ... |
   | Mobile behavior | ... | ... | ... |

4. **User picks.** Update DESIGN.md with the chosen direction and rationale for the choice.

---

## system

Scaffold a design system or extend an existing component library with new tokens, components, or patterns.

### When to use

- When starting a new project that needs a design foundation.
- When adding a new category of components to an existing system.
- When standardizing ad-hoc styles into a system.

### Arguments

- No arguments: audit existing design tokens and suggest improvements.
- `<component-type>`: scaffold a new component type (button, card, dialog, table, form, etc.).

### Steps

1. **Audit existing system.** Read **in parallel**:
   - `tailwind.config.*` for existing tokens.
   - CSS/SCSS files for custom properties.
   - Existing components for patterns.
   - Project root `DESIGN.md` if one exists.

2. **Identify gaps.** Compare against the project's needs:
   - Missing semantic color tokens.
   - Inconsistent spacing usage.
   - Components using hardcoded values instead of tokens.
   - Missing dark mode support.

3. **Propose additions.** For each gap:
   - Token name and value.
   - Where it applies.
   - Migration path for existing hardcoded values.

4. **Scaffold project DESIGN.md when missing.** Apply the canonical schema from `standards/design-md-template.md`: mission, brand, style foundations, accessibility, writing tone, do/don't rules, component expectations, quality gates. The per-feature design docs from the `consult` subcommand are separate from this project-level document.

5. **Present for approval.** Propose changes to config files and suggest `/plan scaffold component <name>` for new components.

## Rules

- Design decisions must reference the project's existing design tokens and component library. Never propose arbitrary values.
- Every design must address all states: empty, loading, error, success. Forgetting states is the most common design gap.
- Accessibility is not optional. Every design must specify keyboard navigation, ARIA roles, and screen reader behavior.
- Color choices must pass WCAG AA contrast ratios. Use the project's semantic color tokens, not raw hex values.
- DESIGN.md is permanent. It records WHY decisions were made, not just WHAT was decided.
- Never generate production code during design consultation. This skill produces decisions and specifications, not implementation.
- When the project uses a specific component library (shadcn/ui, MUI, etc.), use its component vocabulary and patterns. Do not invent parallel abstractions.

## Related skills

- `/review design` -- Audit an existing implementation against design quality standards.
- `/palette` -- Generate a full OKLCH color palette with accessibility verification.
- `/plan scaffold component` -- Generate component boilerplate from project patterns.
- `/plan` -- Plan the implementation after design decisions are made.
