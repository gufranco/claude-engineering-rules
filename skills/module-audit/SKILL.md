---
name: module-audit
description: Survey a codebase for shallow modules and produce a ranked report of consolidation opportunities. Reads the project glossary if one exists, walks the code looking for interfaces nearly as large as their implementations, applies the deletion test, and recommends consolidations with before-and-after Mermaid diagrams. Use when the user says "audit modules", "find shallow modules", "where is the architecture friction", "consolidate this", or after `/assessment` flagged broad architecture debt. Do NOT use for line-level review (use `/review`), debugging (use `/investigate`), or completeness audits (use `/assessment`).
argument-hint: "/module-audit [path] [--html]"
allowed-tools: "Read, Grep, Glob, Bash"
user-invocable: true
---

Find the parts of the codebase where the interface is doing too little work for the implementation it presents, and recommend consolidations that hide complexity behind smaller interfaces. Output is a Markdown report by default; `--html` produces an HTML variant for browser viewing.

## Vocabulary

Use these terms consistently in every finding. Full definitions in [`VOCABULARY.md`](VOCABULARY.md).

- **Module.** Anything with an interface and an implementation. A function, a class, a package, a layer of slice. Scale-agnostic.
- **Interface.** Everything a caller has to know to use the module correctly. Types, invariants, error modes, ordering constraints, configuration, performance characteristics. Not only the type signature.
- **Implementation.** What lives inside.
- **Depth.** How much behavior a caller can drive per unit of interface they have to learn. A module is **deep** when the interface is small and the implementation is large. A module is **shallow** when the interface is nearly as large as the implementation.
- **Seam.** The place an interface lives. A spot where behavior can change without editing the call site.
- **Adapter.** A concrete thing that satisfies an interface at a seam.

Two principles drive every finding:

- **Deletion test.** Mentally delete the module. If complexity vanishes, the module was a pass-through. If complexity reappears across N callers, the module was earning its keep.
- **One adapter is hypothetical, two are real.** A seam is worth its cost only when at least two concrete implementations live behind it. A single-adapter seam is just indirection.

## Process

### 1. Read the project glossary

If a `GLOSSARY.md` exists at the project root, or a `GLOSSARY-INDEX.md` points at per-context glossaries, load it. Use its domain terms in every finding instead of generic words like "service" or "component". See [`rules/project-glossary.md`](../../rules/project-glossary.md).

If no glossary exists, proceed and use the names the code itself uses.

### 2. Walk the code

Use the `Explore` agent with `subagent_type=Explore` for breadth. Note where the model experiences friction:

- Understanding one concept requires bouncing between many tiny modules.
- A module's interface is almost as large as its implementation.
- A module exists only to forward arguments to one downstream call.
- Two adjacent layers expose the same vocabulary.
- A test for the module mocks every collaborator (the test is testing the mocks, not the module).
- A code path that the user describes as "always changes together" lives in N separate files.

For each candidate, apply the deletion test silently. If deletion concentrates complexity, keep the candidate. If deletion just shifts it, discard the candidate.

### 3. Classify dependencies

For every candidate, classify the dependencies the consolidated module would need to talk to. See [`REFACTOR-STRATEGY.md`](REFACTOR-STRATEGY.md):

- **In-process.** Pure computation, in-memory state, no I/O. Always consolidatable.
- **Local-substitutable.** A local stand-in exists, like an in-memory database or a filesystem fake. Test through the stand-in.
- **Remote but owned.** Your own service across a network. Define a port, write two adapters (in-memory for tests, real transport for production).
- **External and not owned.** A third-party API. Inject a port, mock the adapter in tests.

The classification chooses the testing strategy and the seam shape.

### 4. Produce the report

Default output: a Markdown file written to `$TMPDIR/module-audit-<timestamp>.md`. With `--html`, write an HTML file at the same path with `.html` instead of `.md` and open it.

For each candidate, one section:

- **Files.** The modules involved.
- **Friction.** Why the current shape causes pain. Use glossary vocabulary.
- **Recommendation.** What to consolidate, what stays, what new shape the interface takes.
- **Before and after.** Two Mermaid diagrams side by side.
- **Test strategy.** Where the new interface is tested and which dependency category it falls into.
- **Strength.** One of `strong`, `worth exploring`, `speculative`.
- **Tension with existing ADRs.** Only when the recommendation conflicts with an accepted ADR, and only when the conflict is worth reopening.

End the report with a `Top recommendation` section: which candidate to tackle first and why.

### 5. Explore alternatives

After the user picks a candidate, switch to [`INTERFACE-OPTIONS.md`](INTERFACE-OPTIONS.md) to generate at least three radically different interface designs in parallel and pick one.

## Verification

- Every finding uses VOCABULARY.md terms.
- Every finding passes the deletion test.
- Every port introduced has two adapters justified.
- The report uses Mermaid for diagrams (no ASCII art).
- Output path is announced to the user.

## Related skills

- `/assessment` find broad architecture debt before this skill drills in.
- `/refactor` execute the recommended consolidation incrementally.
- `/plan adr new` record any non-obvious decision the consolidation rests on.
