# Design Philosophy

Complexity is the primary cost axis of every design decision. Name the symptom and root cause before reaching for a fix.

- Symptoms: change amplification, cognitive load, unknown unknowns. Root causes: dependencies or obscurity. A fix that targets neither is decoration
- Prefer deep modules: small interface, large hidden implementation. Depth is measured by interface size, never file size
- Deletion test: if deleting a module makes complexity vanish, it was a pass-through
- A seam needs two real adapters today; one adapter is hypothetical, so do not invent ports
- Adjacent layers must present different abstractions; pass-through methods and variables signal an empty layer
- Design it twice: draft two radically different approaches for any non-trivial decision
- Define errors out of existence before designing the catch site; aggregate handlers at the top
- Strategic budget: 10 to 20 percent of a non-trivial task improves the surrounding design, within surgical-edit scope. A third touch of the same area in a quarter triggers consolidation
- On conflict: the 30-line function limit, the no-comments policy, surgical edits, and YAGNI win

Full rule, examples, and rationale: [`standards/design-philosophy.md`](../standards/design-philosophy.md). Read it before a design review, a module consolidation, or naming red flags in someone's code.
