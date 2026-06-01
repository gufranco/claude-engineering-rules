# Everyday Engineering

A short daily checklist of engineering principles distilled from [`../standards/engineering-discipline.md`](../standards/engineering-discipline.md). The standards file is the deep reference; this rule is the everyday version.

Loaded on demand for code-change tasks. Triggers in [`index.yml`](index.yml).

## The checklist

When you start a non-trivial code change, apply these. When you finish one, verify them.

### Before writing code

- Did you build an end-to-end thin slice through every layer before going deep on one of them? If the change is the first of a feature, the slice is the first deliverable, not the last.
- Did you ask whether a spike would answer the open question more cheaply than committing to the design? If so, run `/spike` and delete the answer-code after capturing the verdict.
- Did you check whether the user's stated requirement is the real one? Surface workflows. Surface "what happens when this fails?" cases. Surface the constraint they did not say out loud.
- When the surrounding constraint feels impossible, did you list the constraints and ask which are actually binding? The hardest problems usually have an unstated constraint that, once stated, falls away.

### While writing code

- Are you keeping changes orthogonal? Change one module. Did anything in another break? If yes, the design is not orthogonal yet.
- Are you preserving reversibility? Vendor-specific code hides behind an interface. New ports get justified by two real adapters, not one hypothetical one.
- Are you following the Law of Demeter? Long chains like `a.b().c().d()` mean every intermediate is now a coupling point.
- Did you push variability into configuration instead of hard-coding? Code holds policy; metadata holds values that swing.
- Did you separate model from view? The entity is not the response DTO. The event source is not the event consumer.
- Are you designing for test? If the only way to test the new code is to mock half the project, the design is wrong.

### While debugging

- Did you build a deterministic, fast feedback loop before you started hypothesizing? Phase 0 of `/investigate` exists for this reason. Without a loop, every hypothesis is a guess.
- Are you proving every assumption against real evidence? Read the actual error. Read the actual config. "I remember it works like..." is not evidence.
- Are you assuming your code is at fault before you blame the runtime, the OS, the compiler, the library? The platform is rarely broken.
- When the bug is intermittent, are you raising the reproduction rate instead of waiting for a clean repro? 50% flake is debuggable, 1% is not.
- Did you stay in problem-solving mode? Whose code introduced the bug is a post-mortem question, never a fix-window question.

### Before declaring done

- Did you add a regression test for the bug you just fixed? A bug found in production should never recur.
- Did you ship a thin slice that the user can actually feel, or only an internal refactor? Communicate expectations through what they can touch.
- Did you remove the broken windows you spotted along the way, or board them up with a tracking link? Decay accelerates once it starts.
- Did you sign your work? Commit identity is yours, not borrowed.

### Communication discipline

- Status reports lead with the symptom, then the chronology, then the hypothesis. Never the theory first.
- Questions to the user lead with the specific question, then what was investigated, then the options with their trade-offs.
- When blocked, present a path forward. Never hand off a problem framed as "impossible".
- Pick the medium that fits the message. A decision belongs in a durable document. A walkthrough belongs in a real-time channel.
- Estimate in units that match accuracy: "a few days", not "63 hours".

## When this checklist gives way

- The change is a single-line fix or a trivial config tweak. Skip the checklist.
- The user has explicitly asked for an exploration, a sketch, or a "just see what happens" pass. The checklist resumes when the exploration produces code intended to ship.
- A rule in `~/.claude/rules/` is more specific and conflicts with an item here. The more specific rule wins.

## Cross-references

- [`../standards/engineering-discipline.md`](../standards/engineering-discipline.md). The deep reference this file checklists.
- [`design-philosophy.md`](design-philosophy.md). The vocabulary (module, interface, seam, adapter) that the checklist uses.
- [`code-style.md`](code-style.md). The mechanical rules that encode several items directly.
- [`smart-questions.md`](smart-questions.md). The communication discipline used in the last section.
- [`verification.md`](verification.md). The evidence-based completion gates.
