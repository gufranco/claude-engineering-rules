# Engineering Discipline

A deep reference of daily-engineering principles drawn from Hunt and Thomas, "The Pragmatic Programmer" (1st edition, Addison-Wesley, 2000, ISBN 0-201-61622-X). Citations point at chapter and section in the original. Every principle is paraphrased; canonical short phrases that have entered industry vocabulary are kept verbatim where useful.

This file is the deep reference. The everyday checklist lives at [`../rules/everyday-engineering.md`](../rules/everyday-engineering.md).

Loaded on demand. Triggers in [`../rules/index.yml`](../rules/index.yml).

## What this file deliberately does not repeat

The following principles are already encoded elsewhere and are not re-stated here:

- Single-source-of-knowledge representation. See [`../rules/code-style.md`](../rules/code-style.md) DRY references and "Single source of truth".
- Assertions and defensive invariants. See [`../rules/code-style.md`](../rules/code-style.md) "Defensive Invariants" and "Total Functions".
- Error classification (transient, permanent, ambiguous). See [`../rules/code-style.md`](../rules/code-style.md) "Error Classification".
- Idempotency and deduplication. See [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md).
- Domain modeling via DDD tactical patterns. See [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md) "Architecture Gate" and [`ddd-tactical-patterns.md`](ddd-tactical-patterns.md).
- Source-code control hygiene. See [`../rules/git-workflow.md`](../rules/git-workflow.md).
- Validation at system boundaries. See [`../rules/code-style.md`](../rules/code-style.md) "Validation".

## Principles

### 1. End-to-end thin slice before depth

Build a thin, working path through every layer of the system before deepening any single layer. Keep the thin slice in production. It is not a throwaway. It is the skeleton the rest of the work hangs from.

When the goal is "does this design hold up at all?" the answer comes from running the path with real wiring, not from reasoning about a slide. The slice exposes integration mismatches and missing seams early, when fixing them is cheap.

When this applies: any new feature touching three layers or more. Backend with API and persistence and a job queue. Frontend with route, data fetch, render, and write-back. The slice is the first slice, not the last.

How we encode it: `/spike` is for throwaway answers to specific questions; thin slicing is the production starting shape. Combine with `/plan` Phase 1 (tracer-style scaffolding when the task is sufficiently new).

Source: Ch 2, Sec 10.

### 2. Throwaway prototype to answer one question

A prototype is code that exists to learn one specific thing. Its life ends the moment the question is answered. Confusing a prototype with a thin slice is the classic mistake. The slice ships; the prototype is deleted.

How we encode it: `/spike` skill. See [`../skills/spike/SKILL.md`](../skills/spike/SKILL.md).

Source: Ch 2, Sec 11.

### 3. Orthogonality

Design so a change in one place does not ripple to another. The test is mechanical: change module A. Did anything in module B break? If yes, the modules were not orthogonal even if the architecture diagram said they were.

How we encode it: applies to every code-change task. The vocabulary in [`../rules/design-philosophy.md`](../rules/design-philosophy.md) (module, interface, seam) is the language to discuss orthogonality. The `/module-audit` skill is the tool to find places where it has been lost.

Source: Ch 2, Sec 8.

### 4. Reversibility

No technology choice is permanent. Every "we are standardizing on X" gets revisited. Build to absorb the revisit by hiding vendor specifics behind interfaces and refusing one-way doors.

How we encode it: ports-and-adapters from [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md) "Architecture Gate". The "one adapter is hypothetical, two are real" rule from [`../rules/design-philosophy.md`](../rules/design-philosophy.md) prevents premature port creation; reversibility prevents single-vendor coupling at the moment a swap becomes desirable.

Source: Ch 2, Sec 9.

### 5. Critical reading of authorities

Vendor claims, fashion-driven recommendations, popular-online answers, and AI outputs are all inputs. None of them is authoritative until verified. Ask who benefits from the position. Reproduce the benchmark. Trace the citation.

How we encode it: the Anti-Hallucination rule in [`../CLAUDE.md`](../CLAUDE.md). Apply also to documentation the user shares, to library docs, to package READMEs, and to LLM outputs that flow into code.

Source: Ch 1, Sec 5.

### 6. Communicate by matching medium to message

Even correct content fails when the delivery is wrong. Pick the medium that fits. A walkthrough belongs in a real-time channel. A decision record belongs in a durable document. A status update belongs in a structured artifact, not a long Slack message.

How we encode it: [`../rules/smart-questions.md`](../rules/smart-questions.md) and [`../rules/writing-precision.md`](../rules/writing-precision.md). The principle here is the framing: think about the audience before drafting.

Source: Ch 1, Sec 6.

### 7. Estimate to learn, not to commit

Estimates exist to surface what is unknown. The number is less important than the act of breaking work down until each piece is estimable. When the breakdown stalls, the unknown has been found. Track actuals against estimates so future estimates calibrate.

State estimates in the units that match accuracy: "a few days" or "two to three weeks", not "63 hours". False precision invites false belief.

How we encode it: applies during `/plan` Phase 2 task breakdown. Calibrate against the spec folder's prior estimates and actuals.

Source: Ch 2, Sec 13.

### 8. Iterate the schedule with the code

The schedule is revised as the code is built, not set once at the start. Slippage is communicated early. Padding is not a substitute for re-estimation.

How we encode it: every `/plan` update revisits the task breakdown timing. Spec folders retain the original estimate next to the revised one.

Source: Ch 2, Sec 13.

### 9. Fix the problem, not the blame

The bug is whoever is reading the code right now. Whose code is at fault is a question for the post-mortem, never for the fix window.

How we encode it: `/investigate` enforces the hypothesis-driven loop. `/incident` writes the blameless post-mortem.

Source: Ch 3, Sec 18.

### 10. Do not panic

A clear head is the most efficient debugging tool. Reread the actual error before theorizing. State the symptom before the hypothesis.

How we encode it: [`../rules/smart-questions.md`](../rules/smart-questions.md) "Status and Error Reports" insists on symptom-then-chronology-then-hypothesis. `/investigate` Phase 1 step 1 ("understand the symptom") makes the order mechanical.

Source: Ch 3, Sec 18.

### 11. The platform is not broken

Bugs in the language runtime, the operating system, the compiler, the database engine, or a popular library are real but rare. Assume your code is at fault until evidence forces the other conclusion.

How we encode it: investigate phase 3 hypothesis ranking puts "my code" first by default. Promoting "library bug" to a candidate requires a reproducer outside the project.

Source: Ch 3, Sec 18.

### 12. Prove every assumption

Verify each assumption against real evidence. Read the actual config. Read the actual output. Memory of "how it works" is not evidence.

How we encode it: [`../CLAUDE.md`](../CLAUDE.md) Confidence rule. [`../rules/verification.md`](../rules/verification.md) gates.

Source: Ch 3, Sec 18.

### 13. Use the Law of Demeter

A method should call only methods of itself, its parameters, the objects it creates, and its direct components. Long chains like `a.b().c().d().e()` are warning signs: every intermediate is a coupling point that a change can break.

How we encode it: [`../rules/code-style.md`](../rules/code-style.md) "Law of Demeter" already states the rule. This file's contribution is the chain-shape signal: count the dots, ask whether the caller had to learn each intermediate.

Source: Ch 5, Sec 26.

### 14. Configure, do not integrate

Hard-coded choices become hard-removed choices. Push variability into configuration, into runtime registries, into declarative metadata. Code holds policy; metadata holds the values that swing.

How we encode it: [`../rules/code-style.md`](../rules/code-style.md) "No environment conditionals" and "No magic numbers" sections cover one face. This file's contribution: when in doubt, the value lives in config.

Source: Ch 5, Sec 27.

### 15. Design with services and explicit concurrency

Independent, well-defined services compose better than monolithic objects. Even single-threaded code lives in a concurrent world (signals, timeouts, retries, queues). Never assume single access; design data structures for safe concurrent use from the start.

How we encode it: [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md) "Hexagonal Architecture" covers the boundary shape. The concurrency framing here applies to in-process state: assume two callers, not one.

Source: Ch 5, Sec 28.

### 16. Separate views from models

Underlying data is distinct from how it is presented. The same model powers many views. The principle applies outside GUIs: an event source has many consumers; a domain entity has many serializations.

How we encode it: applies during frontend planning (component vs. store) and backend planning (entity vs. response DTO). [`../rules/code-style.md`](../rules/code-style.md) "API Boundary Types" already enforces the entity-vs-DTO split.

Source: Ch 5, Sec 29.

### 17. Refactor as gardening

Refactor when duplication, outdated knowledge, or design that no longer fits is seen. Refactoring is continuous gardening, not periodic surgery. Never refactor alongside feature work. Have tests in place first.

How we encode it: `/refactor` skill. [`../rules/git-workflow.md`](../rules/git-workflow.md) bisect-friendly commits rule ("Never mix formatting changes with logic changes").

Source: Ch 6, Sec 33.

### 18. Design for test

Testability is a property of the design. Code that is hard to test through its interface is hard to maintain. Treat untestable code as a design defect, not a testing gap.

How we encode it: [`../rules/testing.md`](../rules/testing.md) integration-first philosophy. [`../rules/code-style.md`](../rules/code-style.md) "Pit of Success" and "Functional core, imperative shell" enforce the design shape that makes tests natural.

Source: Ch 6, Sec 34.

### 19. Do not ship wizard code you do not understand

Generated scaffolding from an IDE wizard or an LLM is your code the moment you keep it. Read what was produced. Understand each line before extending it. If you cannot maintain it, do not ship it.

How we encode it: [`../rules/ai-guardrails.md`](../rules/ai-guardrails.md) "Never Commit Code You Cannot Explain".

Source: Ch 6, Sec 35.

### 20. Dig for requirements, do not gather them

Stated requirements are surface. Real needs are below. Ask why repeatedly. Observe the actual workflow. Document the policy separately from the implementation. Abstractions live longer than details: capture "tax rules vary by jurisdiction", not "apply 7.5%".

How we encode it: `/interview-me` and `/plan` Discovery Phase questions.

Source: Ch 7, Sec 36.

### 21. Find the box, do not think outside it

Most "impossible" problems have unstated constraints that, once surfaced, dissolve the impossibility. List every constraint. Question which are actually binding. The easiest path may already be in the list.

How we encode it: applies during `/plan` Phase 2 evaluation of alternatives.

Source: Ch 7, Sec 37.

### 22. Provide options, not lame excuses

When something is blocked, present a path forward instead of a reason it cannot be moved. State what is blocked, what alternatives exist, what is recommended.

How we encode it: [`../rules/smart-questions.md`](../rules/smart-questions.md) "Asking the user" demands options with trade-offs on every blocker.

Source: Ch 1, Sec 2.

### 23. Do not live with broken windows

Fix bad designs, wrong decisions, and poor code as soon as they are seen. If you cannot fix immediately, board it up (file an issue, stub a fix, leave a TODO with a tracking link) so the rot does not spread.

How we encode it: [`../rules/found-fix.md`](../rules/found-fix.md) covers verification-surface findings. This principle extends it to general code smells the engineer notices while passing through.

Source: Ch 1, Sec 2.

### 24. Make quality a requirements issue

Quality is a property the user signs off on, not a private engineering aspiration. The trade-off between scope, quality, and timeline is negotiated, not assumed.

How we encode it: `/plan` Discovery Phase question 3 ("what does success look like?"). The user decides when "good enough" has been reached for the current release; the engineer surfaces the trade-off explicitly.

Source: Ch 1, Sec 4.

### 25. Saboteurs and state coverage

A test that never fails is no test at all. Deliberately introduce bugs in a branch and verify tests catch them. Aim for state coverage (every transition explored) not just line coverage (every line executed). Coverage tools indicate what was not tested, not what was tested well.

How we encode it: mutation testing for the highest-risk modules. State-machine modeling from [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md) makes the state set explicit so coverage can be measured against it.

Source: Ch 8, Sec 43.

### 26. Find bugs once

A bug found in production should never recur. Every defect ticket gains a regression test before it is closed. "We already fixed that" should never be said twice.

How we encode it: [`../CLAUDE.md`](../CLAUDE.md) Completion Gates "Bug fixes add" already requires a test that fails without the fix. This principle adds the long-tail discipline: the test stays in the suite forever.

Source: Ch 8, Sec 43.

### 27. No manual procedures

Humans are not as repeatable as computers. Scripts in source control are. Every repeatable build, deploy, test, and provisioning step is a script. Cron and CI run the script the same way every time.

How we encode it: [`../rules/git-workflow.md`](../rules/git-workflow.md) Local Quality Gate. [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md) Verification Gate. CI files in the repo.

Source: Ch 8, Sec 42.

### 28. Build documentation in, do not bolt it on

Documentation generated from the code stays in sync. Documentation added at the end goes stale immediately. Comments describe why, not how. API docs derive from the code (TypeDoc, JSDoc, docstring extraction).

How we encode it: [`../rules/code-style.md`](../rules/code-style.md) "Comments Policy" already restricts comments to non-obvious why. This principle adds the source-derived API doc rule.

Source: Ch 8, Sec 44.

### 29. Gently exceed expectations

Success is measured by user perception, not feature count. Communicate expectations continuously through thin slices and prototypes. Deliver a little more than promised in details that matter to the user. Never surprise with scope.

How we encode it: communication discipline during `/plan`, `/ship pr`, and post-deploy verification. The principle here is mindset: the bar is not "did the feature ship", it is "did the user feel the system understood them".

Source: Ch 8, Sec 45.

### 30. Sign your work

Put your name on what you ship. Treat your signature as a quality guarantee. Respect the signatures of others. Anonymous code invites sloppy code.

How we encode it: commit identity from the home gitconfig (never the OAuth email), author and reviewer fields on PRs, ADR authorship.

Source: Ch 8, Sec 46.

## Cross-references

- [`../rules/everyday-engineering.md`](../rules/everyday-engineering.md). The daily checklist derived from this file.
- [`../rules/design-philosophy.md`](../rules/design-philosophy.md). The complexity-as-cost-axis framing this file composes with.
- [`../rules/code-style.md`](../rules/code-style.md). The mechanical rules that encode many of these principles directly.
- [`../rules/architecture-defaults.md`](../rules/architecture-defaults.md). The architecture gate that decides when DDD or hexagonal applies.
- [`../rules/testing.md`](../rules/testing.md). The testing rules that encode "design for test" and "find bugs once".
