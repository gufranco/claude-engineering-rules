## Vocabulary

Use these terms in every finding the skill produces. Do not substitute "component", "service", "API", or "boundary". Consistency is the point.

### Terms

**Module.** Anything with an interface and an implementation. Scale-agnostic. A function, a class, a package, or a tier-spanning slice of code are all modules. Avoid: "unit", "component", "service".

**Interface.** Everything a caller has to know to use the module correctly. Includes the type signature, but also: invariants the module guarantees, error modes, ordering constraints, required configuration, performance characteristics, and side effects. Avoid: "API", "signature". Both are narrower than what is meant here.

**Implementation.** What lives inside the module. Distinct from "adapter". A module can have a small adapter and a large implementation (a real Postgres repository), or a small implementation and a large adapter (an in-memory fake). Use "adapter" when the seam is what is being discussed; use "implementation" otherwise.

**Depth.** How much behavior a caller drives per unit of interface they have to learn. A deep module hides a lot behind a small surface. A shallow module exposes nearly as much surface as it implements. Depth is a property of the relationship between interface and implementation, not of either side alone.

**Seam.** The place an interface lives. A spot in the code where behavior can change without editing the call site. Choosing where to put the seam is a design decision distinct from what goes behind it. Avoid: "boundary". It is overloaded with the DDD bounded-context meaning.

**Adapter.** A concrete thing that satisfies an interface at a seam. Describes the role the thing plays (what slot it fills), not its substance.

### Two driving principles

- **Deletion test.** Imagine deleting the module. If complexity vanishes, the module was a pass-through and was not earning its keep. If complexity reappears across the callers, the module was concentrating something useful and was deep enough to justify itself.
- **One adapter is hypothetical, two are real.** A seam is worth its cost only when at least two concrete adapters live behind it. A single-adapter seam is indirection without payoff.

### Relationships

- A module has exactly one interface (the surface it presents to callers and tests).
- Depth is a property of a module measured against its interface.
- A seam is where a module's interface lives.
- An adapter sits at a seam and satisfies the interface.

### Anti-patterns this vocabulary catches

- **Depth measured as a line-count ratio.** Padding the implementation gets you "deeper" by that metric. We measure depth as behavior-per-interface-element, not lines.
- **Interface taken to mean the TypeScript `interface` keyword or a class's public method list.** Interface here is the full contract a caller must internalize, including invariants and error modes.
- **Boundary used in place of seam.** Say seam when the topic is where the interface lives. Say bounded context when the topic is DDD scope.
