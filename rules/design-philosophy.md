# Design Philosophy

Heuristics for reasoning about software complexity. Drawn from John Ousterhout, "A Philosophy of Software Design", and from the user's accumulated practice. This rule extends, never replaces, the existing rules in [`code-style.md`](code-style.md), [`pre-flight.md`](pre-flight.md), [`surgical-edits.md`](surgical-edits.md), and [`ai-guardrails.md`](ai-guardrails.md). Where this rule conflicts with another, the existing rule wins.

## Core Principle

Complexity is the only enemy that scales with project age. Every other defect category, bugs, performance, security, can be fixed in a release. Complexity, once accumulated, resists removal because it is now load-bearing. Treat complexity as the primary cost axis of every design decision.

## Three Manifestations of Complexity

When code is hard to work with, name the symptom precisely before reaching for a fix.

| Symptom | Definition | Signal |
|---------|------------|--------|
| Change amplification | A simple change requires modifications in many places | One feature edit touches 8 files |
| Cognitive load | The amount a developer must know to make a modification safely | New hire cannot ship a fix in week one |
| Unknown unknowns | It is not clear which code must change, or what to know before changing it. The worst form. | Senior engineer says "I think this is right" |

A fix targets the specific symptom. Naming the symptom first prevents random refactoring.

## Two Root Causes

Every form of complexity reduces to one of two causes.

- **Dependencies.** Code that cannot be understood or modified in isolation. A change here forces a change there. Reduce by hiding information, narrowing interfaces, splitting modules along dependency lines.
- **Obscurity.** Important information is not obvious from reading the code. Reduce by precise naming, by surfacing invariants in types, by making the common case the default.

When proposing a fix, state which root cause the fix targets. A fix that addresses neither is decoration.

## Strategic vs Tactical Programming

Tactical programming gets the feature shipped today, accepts complexity as accumulated debt. Strategic programming invests a fraction of every task in better design. The mindset is the design choice; the technique follows.

- **Budget.** Around 10 to 20 percent of any non-trivial task goes to design improvement of the surrounding code: a clearer name, a tightened type, a removed dependency. Not a full refactor, not a separate ticket.
- **Trigger to switch modes.** When the same area is touched a third time in a quarter, pause and pay the strategic cost. Three touches without consolidation is the signal.
- **No tactical apologies.** Code does not need a comment saying "this is temporary". If the design is wrong, fix it now or open a tracked issue. "Temporary" without a tracking link is a synonym for "permanent".

This complements the "Completeness" rule in [`code-style.md`](code-style.md). Completeness governs the depth of the current task; strategic mindset governs the carry-cost of the surrounding code.

## Deep Modules

A deep module presents a small interface and hides a large implementation. A shallow module presents a large interface for a small implementation. Depth is the ratio of power to interface size.

- The metric is interface size, not file size or function size. The existing rule in [`code-style.md`](code-style.md) keeps functions under 30 lines and files under 500 lines. Both rules apply at different layers. A 30-line function can be a leaf of a deep module. A 500-line file is the upper bound of a deep module, not a target.
- Information hiding is the technique. Every field, every helper, every detail that callers do not need is hidden behind the interface.
- **General-purpose modules are deeper.** A general interface tends to be smaller than the union of special-case interfaces it replaces. When in doubt between one general method and three special-case methods, draft both and compare interface size.
- **Pull complexity downwards.** The module author absorbs complexity so callers do not. Opposite of pushing complexity up through configuration knobs.

## Different Layer, Different Abstraction

Adjacent layers must present meaningfully different abstractions. If layer N exposes the same vocabulary as layer N+1, one of them is empty.

- Pass-through methods, pass-through variables, and decorator chains are common signals that adjacent layers share an abstraction.
- A wrapper that adds a type cast, a log line, and forwards the call is not a layer. It is a tax.

## Design It Twice

For any non-trivial design decision, draft at least two approaches before committing.

- The two approaches should be radically different, not minor variations of the same idea.
- Compare on three axes: simplicity of interface, generality of use, implementation cost.
- The first design is rarely the best. The second design often beats the first even when the first was the eventual choice, because the comparison sharpens the requirements.
- This complements [`pre-flight.md`](pre-flight.md) step 5, "Evaluate alternatives". The pre-flight rule mandates 2 to 3 approaches; this rule names the technique.

## Define Errors Out of Existence

The lowest-cost exception is the one that is never thrown. Before designing the catch site, redesign the interface so the error case is not reachable.

| Pattern | Example |
|---------|---------|
| Eliminate the error by widening the contract | `delete(key)` succeeds whether or not the key existed; no `KeyNotFound` |
| Mask the error at a lower layer | TCP retransmits lost packets; the application never sees packet loss |
| Aggregate handlers at one top-level site | One catch in the request dispatcher, not 40 in handler bodies |

When an exception is genuinely necessary, the existing classification rule in [`code-style.md`](code-style.md) applies: classify transient vs permanent vs ambiguous, log with context, never swallow.

## Red Flags

Patterns that signal a complexity problem. Each is a smell, not a rule. Investigate when seen.

| Red flag | What it looks like | What it usually means |
|----------|-------------------|----------------------|
| Pass-through method | A method whose body is one forwarding call with matching arguments | Two layers expressing the same abstraction |
| Pass-through variable | A parameter threaded through five functions, used by none of the intermediates | Missing context object or wrong scope |
| Configuration parameter | A knob exposed because the module cannot compute the right value | Complexity pushed up to the caller |
| Classitis | Many tiny classes, each doing almost nothing, chained at the call site | Decomposition too fine; cognitive load high |
| Decorator overuse | A wrapper that adds no behavior except forwarding | Inheritance or composition misapplied |
| Getter and setter pairs | One-line accessors for every private field | Information hiding undone by reflex |
| Adjacent layers, same abstraction | Two layers naming the same nouns and verbs | One layer is empty |
| Temporal decomposition | Module boundaries follow the order of operations rather than the knowledge each module needs | Coupling on schedule, not on data |
| Repeated try/catch | The same exception caught and handled in many places | Missing aggregation or masking site |

Mechanical detection of these patterns is unreliable. Review catches them by reading. The hook in [`../hooks/todo-marker-blocker.py`](../hooks/todo-marker-blocker.py) covers the one mechanically-enforceable case, the marker comment that explicitly admits tactical debt.

## Design Taste

Good architectural taste develops only through shipping, receiving feedback, and shipping again. There is no shortcut. AI assistance does not substitute, because taste is calibrated against outcomes, not against training data.

- The author of the code is responsible for the taste of the code. Generated code that compiles and matches the surrounding style is still the author's responsibility.
- Specific, repeated experiences calibrate taste: a refactor that simplified a module, an outage caused by a missing invariant, a change that took 8 hours because a function had 11 parameters.
- Read other people's code. Specifically code that has run in production for years. Bad-looking code that worked is more instructive than clean-looking code that did not.
- Disagree with the consensus when the evidence warrants. The right answer is not the popular answer; it is the answer that survives the next change.

This complements [`ai-guardrails.md`](ai-guardrails.md) "Multi-Agent Validation" and "Never Commit Code You Cannot Explain". Taste is the layer above mechanical review.

## Boundary Conditions

| Conflict with another rule | Resolution |
|---------------------------|------------|
| Deep modules vs 30-line function limit in [`code-style.md`](code-style.md) | The 30-line limit wins at the function level. Deep modules applies at the module and file level. |
| Write comments first vs default no comments in [`code-style.md`](code-style.md) | The no-comments-by-default rule wins. Ousterhout's comments stance is intentionally not adopted. |
| Strategic budget vs surgical edits in [`surgical-edits.md`](surgical-edits.md) | Surgical edits wins. Strategic improvements happen in their own focused task or in the diff the user explicitly asked for. |
| General-purpose modules vs YAGNI in [`code-style.md`](code-style.md) | YAGNI wins for speculative features. Generality is preferred only when two or more concrete callers exist today. |

## Self-Test

Before committing any non-trivial change, ask three questions about the area you touched:

1. **Which symptom of complexity did this address, if any?** Change amplification, cognitive load, unknown unknowns.
2. **Which root cause did this attack?** Dependencies or obscurity.
3. **Did I leave the area more obvious than I found it?** If not, write down what would have made the change easier and feed that into the next task.

If the answer to all three is "neither, nothing, no", the change was strictly tactical. That is acceptable. It must not become a pattern.

## Cross-References

- [`code-style.md`](code-style.md) Fundamentals: DRY, SOLID, KISS, YAGNI, LoD, CQS, Pit of Success.
- [`code-style.md`](code-style.md) Error Classification: what to do once an exception occurs.
- [`pre-flight.md`](pre-flight.md): the gate that runs before implementation.
- [`surgical-edits.md`](surgical-edits.md): scope discipline at the diff level.
- [`ai-guardrails.md`](ai-guardrails.md): mechanical review of AI-generated code.
- [`verification.md`](verification.md): the completion gate.

## Source Material

- John Ousterhout, "A Philosophy of Software Design". Yaknyam Press, 2018 first edition, 2021 second edition.
- Stanford excerpt: https://web.stanford.edu/~ouster/cgi-bin/aposd2ndEdExtract.pdf
- Vasilios Syrakis review: https://cetanu.github.io/blog/a-philosophy-of-software-design/
