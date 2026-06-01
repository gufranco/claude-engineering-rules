# Software Complexity

A deep reference of design principles drawn from John Ousterhout, "A Philosophy of Software Design" (2nd edition). Citations point at chapter. Every principle is paraphrased; chapter titles may be quoted as short canonical phrases.

This file is the deep reference. The everyday baseline lives at [`../rules/design-philosophy.md`](../rules/design-philosophy.md).

Loaded on demand. Triggers in [`../rules/index.yml`](../rules/index.yml).

## What this file deliberately does not repeat

The following principles are already encoded in [`../rules/design-philosophy.md`](../rules/design-philosophy.md):

- Complexity manifestations: change amplification, cognitive load, unknown unknowns.
- Two root causes: dependencies and obscurity.
- Strategic vs tactical programming, the 10-to-20-percent budget.
- Deep modules baseline.
- General-purpose modules are deeper.
- Pull complexity downward.
- Different layer, different abstraction.
- Design it twice.
- Define errors out of existence (with masking and aggregation).
- Red flags catalog (pass-through methods, pass-through variables, configuration parameters, classitis, decorator overuse, getters and setters, adjacent layers same abstraction, temporal decomposition, repeated try-catch).
- Design taste.

The chapters that frame comment-writing as a design discipline (Ch 12 to 15 of the source) are intentionally not adopted. We default to no comments. See [`../rules/design-philosophy.md`](../rules/design-philosophy.md) "Boundary Conditions".

## Principles

### 1. Complexity is judged by the reader, not the author

A piece of code is complex when many readers must work hard to understand it. The author's belief that the code is clear does not change its complexity. Always assume a reader who is not the author and who is not in the author's current mental state.

How we encode it: review comments and architecture discussions assume the reader is a future engineer with no benefit of the present conversation. Code-review skill applies this lens by default.

Source: Ch 2.

### 2. Software design is incremental

A large system's design cannot be visualized at the start. The design that survives surfaces from implementation feedback. The waterfall expectation, complete design before code, fails because design problems only become visible when code forces concrete choices.

How we encode it: `/plan` produces a plan, not a fixed blueprint; the plan is revised as Phase 2 unfolds. Spec folders treat the plan as a living document.

Source: Ch 1.

### 3. Strategic investments pay back within months

The 10-to-20-percent design tax is not a long-term bet. The payback shows up inside the same quarter that the investment was made because reduced friction compounds across every subsequent change in the same area.

How we encode it: when budgeting for design improvements during a task, frame the payback window in weeks. The "I will fix the architecture later" pattern is wrong because later never comes.

Source: Ch 3.

### 4. Interface includes the informal parts

The formal interface is types, names, parameter lists, return values, declared exceptions. The informal interface is the side effects, the ordering constraints, the threading assumptions, the resource lifetimes, the performance characteristics, and every other thing the caller has to know but the compiler will not enforce. Both count toward interface size.

When the formal interface is small but the informal interface is large, the module is not as deep as the type signature suggests.

How we encode it: when measuring depth during `/module-audit`, count both formal and informal interface elements. A function with one parameter that has six undocumented preconditions is shallow.

Source: Ch 4.

### 5. False abstractions

An abstraction is a simplified view that omits unimportant details. A false abstraction omits details the caller actually needs, or includes details the caller does not. Both shapes leak.

How we encode it: when reviewing a new interface, ask "what does the caller still have to know that the interface does not reveal?" and "what does the interface make the caller learn that no caller cares about?". Either question with a non-trivial answer means the abstraction is false.

Source: Ch 4.

### 6. Default-private, public on demand

Hide variables and methods as aggressively as the language allows. Private by default. Public only when at least one outside caller has a real need. The justification is information hiding: every public symbol is a future-change cost.

How we encode it: apply at every code change. Existing public symbols with no external callers are dead surface and should be made private during the touching change, per the cleanup-as-you-go rule.

Source: Ch 5.

### 7. Hierarchy-internal hiding

Information hiding applies inside class hierarchies. A subclass that reads or writes the parent's internal state has the same leakage problem as an external caller reaching into private state. Protected access is not a green light; it is a slightly narrower red flag.

How we encode it: when composing types via inheritance (rare under our existing rules; we prefer composition), treat parent fields as encapsulated. Use accessors that enforce invariants.

Source: Ch 5.

### 8. Six tests for general-purpose interfaces

When designing an interface, ask:

1. What is the simplest interface that covers all current needs?
2. How many situations will use it? (Two or more concrete situations justify generality.)
3. Is the interface easy to use for the current needs?
4. Is the interface too general? An interface that can do anything tends to do nothing well.
5. Does the interface decouple the caller's specific case from the implementation?
6. Does the implementation work for multiple callers without conditionals on caller identity?

How we encode it: apply during `/plan` Phase 2 alternative-evaluation step on every non-trivial interface.

Source: Ch 6.

### 9. Layer-rename test

When two adjacent layers seem to express the same abstraction, try renaming one. If the rename forces real semantic changes in the other layer, the layers were already different. If the rename is purely cosmetic, one layer is empty.

How we encode it: use during architectural review when two adjacent modules feel suspiciously parallel.

Source: Ch 7.

### 10. Do-the-right-thing over ask-the-caller

When the module's author can compute the correct value or behavior internally, do so. Only expose a configuration knob when there is no defensible default and the caller plausibly knows better.

A configuration parameter pushed up to callers becomes a configuration parameter that every caller has to think about, and most callers will get wrong.

How we encode it: when adding a new parameter, run the "could this be computed from existing inputs?" check first. If yes, compute it. Only escalate to a parameter when the caller has knowledge the module cannot derive.

Source: Ch 8.

### 11. Indexes and caches as complexity sinks

Indexes and caches are good examples of pulling complexity down. The data structure absorbs the optimization burden. The caller sees a clean interface that says "give me X" and gets X. The complexity of maintaining the index or invalidating the cache lives inside the data structure.

How we encode it: when faced with a performance problem the caller is currently solving, ask whether the optimization can move into the data layer or the service layer instead.

Source: Ch 8.

### 12. Five tests for combining vs splitting

Combine two pieces of functionality into one module when:

1. They share information that would have to be duplicated if separated.
2. They are always used together.
3. They overlap conceptually.
4. Combining simplifies the interface seen by callers.
5. Combining removes duplication of logic or state.

Split when none of those holds, or when one part is general and the other is special-purpose.

How we encode it: apply during refactoring planning under `/refactor` or `/module-audit`.

Source: Ch 9.

### 13. Extract subtask vs divide into two

When a long method needs splitting, two patterns apply:

- Extract subtask. A chunk of code is moved into a helper method. The original method's interface stays the same. The helper is named for what it does. This works when the subtask is meaningful on its own.
- Divide into two. One method becomes two peers, each with its own interface. The caller now calls both. This works when the subtask is reusable across multiple callers.

The choice is whether the subtask has an audience beyond the caller that originally needed it.

How we encode it: refactor planning chooses one pattern explicitly rather than splitting "to make the method shorter".

Source: Ch 9.

### 14. Long methods are not automatically bad

A long method that performs a single coherent operation is fine. The question is not how many lines the method has but whether the lines belong together. Splitting a coherent method into pieces that have to be called in a specific order is worse, not better, because the order becomes part of the interface.

How we encode it: our existing 30-line guideline in [`../rules/code-style.md`](../rules/code-style.md) is a default, not a ceiling. Coherence wins over arbitrary length.

Source: Ch 9.

### 15. Defensive programming as complexity

Every defensive check is code to read, test, and maintain. Only add a check when the code can act on the result. A check that throws an exception the caller cannot recover from is rarely useful; the same condition would have produced the same crash without the check.

How we encode it: when adding a runtime check, name what the caller would do with a failure. If the answer is "nothing meaningful", drop the check.

Source: Ch 10.

### 16. Fewer exception types

Each new exception type doubles the matrix of possible behaviors the caller must handle. Prefer designs with a small number of exception types and a clear policy for each. Exception-path code is rarely tested; reducing the count reduces the untested surface.

How we encode it: when introducing a new exception in domain code, justify why an existing one cannot serve. The default is to reuse an existing exception type.

Source: Ch 10.

### 17. The second design improves the first

Even when the first design is chosen, the act of producing the second improves the first. Comparing two designs surfaces requirements the author had not stated. The first design has those requirements baked in implicitly; the second design forces them into the open.

How we encode it: applies during `/module-audit` "interface options" pass. The user gets a hybrid recommendation when the second design strengthens the first.

Source: Ch 11.

### 18. The design phase is cheap

Designing twice is small relative to coding both implementations. Most of the time goes into making the chosen design work. Spending an extra hour on design saves the days that go to fixing the wrong design.

How we encode it: when tempted to start coding "to see what shape it takes", check whether one more design pass would surface the shape on paper first.

Source: Ch 11.

### 19. Comment that repeats the code is a signal

When a comment restates what the next line of code already says, one of the two is wrong. Either the code is unclear and the right fix is a better name or a clearer structure. Or the comment is dead weight and should be deleted. Never both.

This is the only comment-craft principle from the source that composes with our no-comments-by-default rule.

How we encode it: during code review, restated comments are flagged. The reviewer asks "rename the symbol or delete the comment?".

Source: Ch 13.

### 20. Naming and scope

Short names (one or two characters) are acceptable in tight scopes: a loop index, a lambda's parameter, a short helper's only argument. Names at module scope or public-API scope must be descriptive. The line is "could a reader land on this name with no surrounding context and guess its meaning?". Tight-scope names are read with surrounding context; module-scope names are not.

How we encode it: extends [`../rules/code-style.md`](../rules/code-style.md) "Meaningful names". A function called `t` is fine inside a three-line callback and wrong as a top-level export.

Source: Ch 14.

### 21. Naming is part of designing

The act of choosing a name forces clarity about what the entity is. Refusal to name (using `tmp`, `helper`, `process`) is refusal to design. When the name is hard to find, the design is muddled.

How we encode it: covered by the `Hard to Pick Name` red flag added to [`../rules/design-philosophy.md`](../rules/design-philosophy.md).

Source: Ch 14.

### 22. Three requirements for a consistent convention

A convention is consistent when:

1. The common name is always used for its purpose.
2. The common name is never used for any other purpose.
3. The purpose is narrow enough that all uses behave the same way.

A convention that has exceptions stops being a convention. The reader has to check every use against the exceptions before trusting the meaning.

How we encode it: when proposing a project-wide pattern, the three checks decide whether the pattern is a convention or a suggestion.

Source: Ch 17.

### 23. Invariants reduce special cases

When the code maintains an invariant (this list is always sorted; this map never contains null values), every reader of the code can assume the invariant. Special-case handling for "what if the list is not sorted?" disappears.

How we encode it: when adding a data structure, ask which invariants the structure will guarantee and which the callers will have to maintain. The fewer the callers maintain, the deeper the structure.

Source: Ch 17.

### 24. Three techniques for obvious code

Code is obvious when the reader makes correct guesses at a glance. Three techniques drive obviousness:

1. Reduce the information the reader needs. Smaller interfaces, fewer variables in scope, fewer responsibilities per function.
2. Reuse information the reader already has. Idioms, conventions, consistent names. Surprise costs cognition.
3. Present important information explicitly. Documented invariants, named constants, structure that mirrors the domain.

How we encode it: every code review checks all three on the touched code.

Source: Ch 18.

### 25. Event-driven code needs explicit invocation context

Event-driven and reactive programming hide the control flow inside the framework. The reader cannot tell when a handler is called or by whom. The handler must document its invocation context: when is this called, by what, with what state.

How we encode it: applies to React effects, queue consumers, signal subscribers, observers. The invocation context belongs in a single sentence at the top of the handler.

Source: Ch 18.

### 26. Generic containers obscure meaning

A `Pair<A, B>` returned from a function tells the reader nothing about what the two values mean. A named struct with named fields says everything. Generic containers are a tax on every reader.

How we encode it: in TypeScript, prefer a discriminated union or a named object type over a tuple, an array of mixed types, or a `Record` with implicit conventions.

Source: Ch 18.

### 27. Declared type should match the allocated type

When a variable's declared type is wider than the actual instance assigned to it, the reader has to track which subtype is really in play. Keep declarations tight.

How we encode it: in TypeScript, this composes with our existing strictness rules. The variable's annotation matches the constructor or the parsed shape.

Source: Ch 18.

### 28. Cost-of-operations awareness

Develop intuition for what is expensive:

| Operation | Order of magnitude |
|---|---|
| L1 cache hit | nanoseconds |
| Main memory access | tens of nanoseconds |
| Cache miss to RAM | hundreds of nanoseconds |
| Local disk I/O | tens of microseconds (SSD) to milliseconds (HDD) |
| Same-region network round trip | hundreds of microseconds to milliseconds |
| Cross-region network round trip | tens to hundreds of milliseconds |
| Dynamic allocation, small | tens to hundreds of nanoseconds |
| GC pause, small heap | milliseconds |
| Database query, simple | hundreds of microseconds to milliseconds |
| Database query with joins or scan | tens to hundreds of milliseconds |

Use micro-benchmarks to calibrate against the actual platform. Intuition wrong by 10x is common.

How we encode it: when reasoning about performance, the table is the starting point; profiling is the verification.

Source: Ch 20.

### 29. Design around the critical path

For performance-sensitive code, identify the smallest amount of code that must run on the common case. Remove special cases from that path with a single up-front check that branches to the rare-case handler. The common path stays short, straight, and cache-friendly.

How we encode it: applies to hot endpoints, render paths, and tight loops. The fast-path-slow-path structure is the explicit shape.

Source: Ch 20.

### 30. Deep modules are faster

Fewer layer crossings mean fewer parameter copies, fewer indirect calls, fewer cache misses on jump targets. The same property (small interface, large implementation) that makes deep modules easier to reason about also makes them faster to execute.

How we encode it: when a performance hotspot turns out to be a tower of shallow wrappers, the fix is deepening, not micro-optimization inside the wrappers.

Source: Ch 20.

### 31. Performance default: simple code first, profile, fix hotspots

The default is to write the simplest code that solves the problem, measure, then optimize the 1-to-3 places that matter. Up-front micro-optimization across the codebase produces a slower codebase that nobody wants to change.

How we encode it: composes with our existing "Performance first" principle. Performance-first means choosing the algorithm with better complexity at write time, not hand-tuning every function.

Source: Ch 20.

### 32. Evaluate every trend against complexity

Object-oriented programming, agile development, test-driven development, design patterns, microservices, functional reactive programming. Each comes with a community case. The right test for each is whether it reduces or increases complexity for the specific system. The fashion of the moment is irrelevant.

Specifically:

- Object-oriented programming is useful when used carefully. Inheritance is the dangerous part. Implementation inheritance leaks parent state into the subclass; prefer composition.
- Interface inheritance reduces complexity by letting many implementations share one contract.
- Agile risks tactical drift because it rewards feature throughput. Counter by reserving design time inside each iteration.
- Test-driven development helps the test discipline but does not by itself produce good design. Design happens before the test, not as a side effect of writing one.
- Design patterns are useful when they fit and harmful when forced. A pattern applied because it is in the catalogue is overhead.

How we encode it: when adopting a framework, library, or methodology, the evaluation criterion is "does this reduce or increase the complexity I have to manage?".

Source: Ch 19.

### 33. Good designers spend more time designing

Good designers spend more time in design and less time chasing bugs. The trade is favorable because design hours are cheaper than debugging hours and the work is more pleasant. Spending half a day on a design that prevents a week of debugging is the typical ratio.

How we encode it: the strategic budget framing for daily work. The 10-to-20-percent design tax is the everyday version of this principle.

Source: Ch 21.

## Cross-references

- [`../rules/design-philosophy.md`](../rules/design-philosophy.md). The baseline rule that this file extends.
- [`../rules/everyday-engineering.md`](../rules/everyday-engineering.md). The daily checklist that composes with this file's design lens.
- [`../rules/code-style.md`](../rules/code-style.md). The mechanical rules that encode several principles directly.
- [`../skills/module-audit/SKILL.md`](../skills/module-audit/SKILL.md). The skill that applies many of these principles to a codebase audit.
