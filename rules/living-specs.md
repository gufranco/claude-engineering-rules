# Living Specs

Every non-trivial change, meaning 3 or more files or changed behavior, updates the behavior spec under the project's `specs/current/` directory.

- Each requirement states one behavior with a normative keyword and at least one Given/When/Then scenario; no implementation detail.
- Changes are deltas: ADDED, MODIFIED with full new text, REMOVED with a reason; merged on completion by `/plan archive`.
- When a decision pivots mid-change, update every invalidated plan, decision record, and delta in the same session.

Full rule, examples, and rationale: [`standards/living-specs.md`](../standards/living-specs.md). Read it before writing a spec delta or archiving a change.
