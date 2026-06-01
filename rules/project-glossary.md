# Project Glossary

## Why this rule exists

Every long-running codebase grows a private vocabulary. Names for entities, names for workflows, names for the boundaries between subsystems. When the names are written down, the agent reads code in the project's own terms, generates code in those terms, and stops inventing synonyms that drift apart.

When the names are not written down, every session asks "is `customer` the same as `account`?" and every code change names the same concept three different ways.

This rule encodes a small, opinionated convention: per-project glossaries that live next to the code, are loaded on demand, and never grow beyond a one-or-two-sentence definition per term.

## Scope

Loaded on demand. Triggers:

- A `GLOSSARY.md` file exists at the project root.
- A `GLOSSARY-INDEX.md` file exists at the project root (multi-context repos).
- The user says "domain glossary", "ubiquitous language", "domain vocabulary", "project glossary".

Skip when the task is plainly outside the domain layer: build config tweaks, dependency bumps, formatting passes.

## File layout

### Single-context project

```
/
  GLOSSARY.md
  src/
  ...
```

The `GLOSSARY.md` at the root is the only glossary. Every domain term in the project lives in this one file.

### Multi-context project (monorepo or domain split)

```
/
  GLOSSARY-INDEX.md
  apps/
    ordering/
      GLOSSARY.md
    billing/
      GLOSSARY.md
    fulfillment/
      GLOSSARY.md
```

The root file is `GLOSSARY-INDEX.md`. It names every context, points at the per-context glossary, and lists how the contexts relate (which events flow between them, which IDs are shared, which terms have different meanings in different contexts).

## Format

### Per-context glossary

```markdown
# <Context name>

<One or two sentences explaining what this context owns and why it exists.>

## Terms

### Order

<One or two sentences. Define what it IS, not what it does.>

Avoid: purchase, transaction.

### Invoice

<One or two sentences.>

Avoid: bill, payment request.

### Customer

<One or two sentences.>

Avoid: client, buyer, account.
```

Rules:

- One or two sentences per definition. No more.
- Every entry includes an `Avoid` line listing the synonyms the team has rejected. This is half the value of the file. Without `Avoid`, the same concept slips back in under a different name in a future change.
- Group terms under subheadings only when natural clusters emerge. A flat list is fine when the terms cohere.
- Domain terms only. General programming concepts (timeout, error, retry) do not belong even when the project uses them constantly. Before adding a term, ask: is this concept specific to this context, or would a programmer in any project recognize it?
- The glossary is a glossary, never a spec, a scratch pad, an ADR archive, or an implementation log. When a decision needs recording, use the project's ADR mechanism. When a plan needs recording, use `/plan`.

### Index file

```markdown
# Glossary index

## Contexts

- [Ordering](apps/ordering/GLOSSARY.md). Receives and tracks customer orders.
- [Billing](apps/billing/GLOSSARY.md). Generates invoices and processes payments.
- [Fulfillment](apps/fulfillment/GLOSSARY.md). Manages warehouse picking and shipping.

## Cross-context relationships

- Ordering emits `OrderPlaced`. Fulfillment consumes it to start picking.
- Fulfillment emits `ShipmentDispatched`. Billing consumes it to generate invoices.
- Ordering and Billing share `CustomerId` and `Money` value types.

## Terms that mean different things across contexts

- "Account" in Ordering means the customer record. In Billing it means the ledger.
- "Status" in Ordering means workflow position. In Fulfillment it means physical location.
```

## Lazy creation

Do not create empty glossaries to satisfy a convention. Create on first use:

- A glossary file does not exist, and a discussion or change names a domain term that needs disambiguation. Create the file with that one term. Add more as they come up.
- A multi-context project gains its second context. The index file is created at that moment, not before.

## How sessions use the glossary

- `/interview-me` loads it before the first question. Challenges user terms that conflict with `Avoid` entries.
- `/tdd` pulls test names and variable names from the glossary canon.
- `/module-audit` names every finding using the glossary instead of generic words like "component" or "service".
- `/zoom-out` walks the module map using the glossary terms.
- `/onboard` reads the glossary first to anchor the rest of the exploration.

## What the glossary does not do

- Does not replace ADRs. Decisions go in `docs/adr/` per `/plan adr`.
- Does not replace types. The glossary defines meaning; types enforce shape.
- Does not replace inline documentation. The glossary is short; docs are long.
- Does not gate code review on every term being defined. New terms can be added when needed.

## Cross-references

- `~/.claude/skills/interview-me/SKILL.md` "When the project has a glossary" section.
- `~/.claude/skills/tdd/SKILL.md` anti-pattern section, naming notes.
- `~/.claude/skills/module-audit/SKILL.md` step 1.
- `~/.claude/rules/design-philosophy.md` Vocabulary subsection.
