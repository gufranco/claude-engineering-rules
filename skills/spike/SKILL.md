---
name: spike
description: Build a small throwaway artifact that answers exactly one open design question, then delete it. Two routes inside the skill, a runnable terminal program for state, logic, or data-shape questions, and a side-by-side view comparison for presentation questions. Use when the user says "spike this", "build a quick throwaway", "let me play with the model", "try a few visual directions", or wants to de-risk a design choice before committing to it. Do NOT use for production features (use `/plan`), for refactoring an existing module (use `/refactor`), or for a single polished design pass (use `/design`).
argument-hint: "/spike [state|view] <question>"
allowed-tools: "Read, Edit, Write, Grep, Glob, Bash"
user-invocable: true
---

A spike is throwaway code whose only purpose is to answer one question. The question chooses the shape.

## Pick a route

Read the user prompt and the surrounding code, then pick.

- **State route.** Use when the open question is about a state machine, a data shape, a workflow, or business rules that are hard to reason about on paper. Load [`STATE-BRANCH.md`](STATE-BRANCH.md). Build a tiny interactive terminal program that drives the state through hard cases and prints the full state after each step.
- **View route.** Use when the open question is about presentation, layout, or visual style. Load [`VIEW-BRANCH.md`](VIEW-BRANCH.md). Generate several radically different variations on a single route, switchable via a query string and a small floating selector.

If the route is genuinely ambiguous and the user is not reachable, pick the route that matches the surrounding code, backend code chooses state, page code chooses view, and write the assumption in the banner comment.

## Rules for every spike

1. **Throwaway from minute one, marked as such.** Place the spike next to the module or page it informs so context is obvious. Prefix the directory or filename with `spike-` per project convention. Add a banner at the top of the entry file: `// SPIKE: <question being answered>. Delete after verdict captured.`
2. **One-command run.** Use the project package manager. The user must launch it without thinking.
3. **State lives in memory.** Skip persistence unless persistence is the question. When persistence is the question, hit a scratch database or local file whose name announces it is disposable.
4. **No polish.** No tests, no abstractions, no error handling beyond what the spike needs to remain runnable. Speed of learning over elegance.
5. **Surface state on every step.** After each user action (state route) or variant switch (view route), print or render the full relevant state.
6. **Capture the verdict, then delete.** Once the question is answered, write the answer to a `NOTES.md` next to the spike or to a commit message or to an ADR, then remove the spike directory. A spike that survives past its verdict has stopped being a spike.

## Verification

- Spike launches with one command.
- Banner names the open question.
- State or chosen variant is visible after every step.
- A verdict is captured before any deletion.
- If the verdict is hard to reverse, run `/plan adr new` and link the ADR from the verdict capture.

## Related skills

- `/plan` plan the real implementation once the answer is known.
- `/plan adr new` record a hard-to-reverse decision.
- `/design` for a single curated design pass that is not throwaway.
