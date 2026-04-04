---
name: office-hours
description: Pre-code brainstorming with forcing questions. No code produced, only a structured design document. Asks six questions one at a time, then produces a design document with Problem Statement, User Persona, Success Criteria, Scope, Risk Mitigation, and Competitive Analysis. Use when user says "office hours", "brainstorm", "think through this", "design session", "let's talk about", "before we code", or wants structured thinking before implementation. Do NOT use for code review (use /review), implementation planning (use /plan), or design system work (use /design).
---

Pre-code brainstorming skill. Asks six forcing questions one at a time to clarify requirements before any code is written. Produces a structured design document, never code.

## Invocation

| Invocation | Action |
|-----------|--------|
| `/office-hours` | Start a brainstorming session with six questions |
| `/office-hours <topic>` | Start with a specific topic pre-loaded |

---

## Steps

1. **Set the topic.** If a topic argument is provided, use it. Otherwise, ask: "What feature or problem do you want to think through?"

2. **Ask six forcing questions.** Ask each question one at a time. Wait for the answer before asking the next question. Do not batch questions.

   | # | Question | Purpose |
   |---|----------|---------|
   | 1 | Who has this problem today? Describe the specific person or role. | Identify the user persona and validate that the problem is real |
   | 2 | What do they do to work around it right now? | Understand the current state and the pain level |
   | 3 | What does the ideal solution look like from their perspective? | Define the north star without implementation constraints |
   | 4 | What is the minimum viable version that delivers value? | Scope the first iteration |
   | 5 | What are the top 3 risks? Technical, business, or adoption risks. | Surface concerns early |
   | 6 | What existing solutions did you consider, and why are they insufficient? | Prevent reinventing what already works |

3. **Synthesize the answers.** After all six questions are answered, produce the design document. Do not ask additional questions unless the answers contain contradictions that need resolution.

4. **Present the design document.** Output the structured document as shown below.

### Output

```
## Design Document: <topic>

**Date:** <timestamp GMT>
**Status:** Draft

### Problem Statement
<One paragraph distilling the problem from the answers to questions 1-2.
Who is affected, what they do today, and why it is insufficient.>

### User Persona
**Role:** <from question 1>
**Current workflow:** <from question 2>
**Pain points:** <extracted from questions 1-2>

### Success Criteria
<Measurable outcomes that define "done". Derived from question 3.
Each criterion must be verifiable: a test, a metric, or an observable behavior.>

1. <Criterion>
2. <Criterion>
3. <Criterion>

### Scope

**MVP (first iteration):**
<From question 4. What ships first.>
- <Feature or behavior>
- <Feature or behavior>

**Future iterations:**
<What the ideal solution includes beyond MVP. From question 3 minus question 4.>
- <Feature or behavior>
- <Feature or behavior>

### Risk Mitigation
<From question 5. Each risk with a concrete mitigation strategy.>

| Risk | Category | Mitigation |
|------|----------|-----------|
| <risk> | Technical / Business / Adoption | <action to reduce or eliminate> |

### Competitive Analysis
<From question 6. What was considered and why it was rejected.>

| Solution | Why considered | Why insufficient |
|----------|---------------|-----------------|
| <name> | <reason> | <gap> |

### Next Steps
- [ ] Validate with <stakeholder> by <date or milestone>
- [ ] Create implementation plan with `/plan`
- [ ] <Any other preparatory step>
```

## Rules

- No code in the output. This skill produces a design document only.
- Ask questions one at a time. Never present all six at once.
- Do not skip questions. If the user says "I don't know" for a question, note it in the document as an open item that needs resolution.
- Do not add questions beyond the six listed. If a clarification is needed, ask it inline before moving to the next question.
- Success criteria must be verifiable. "Users are happy" is not a criterion. "User completes the workflow in under 3 clicks" is.
- The design document is the deliverable. Do not offer to implement anything.
- All timestamps in GMT.

## Related skills

- `/plan` -- Turn the design document into an implementation plan.
- `/design` -- Visual design consultation after requirements are clear.
- `/explain` -- Understand existing code before brainstorming changes.
- `/assessment` -- Audit an implementation against the design document's success criteria.
