# Smart Questions

## Core Rule

Question quality determines answer quality. The rule applies to every direction of dialogue: Claude asking the user, Claude briefing a subagent, Claude reporting status, Claude reporting an error, Claude closing a loop. Treat the user's request as a hypothesis to verify, not a directive to execute literally.

## 1. Self-Investigation Before Asking

Exhaust the cheap-to-check sources before producing a clarifying question. The user paying attention costs more than any of these.

| Source | What to check |
|--------|--------------|
| [`CLAUDE.md`](../CLAUDE.md) and `rules/*` | Whether the question is already answered by an existing rule |
| Codebase grep / glob | Whether the symbol, file, or path the user named already exists |
| Read the file the user named | Before asking what is in it |
| `git log` / `git blame` | Recent changes to the file, last author, intent in the message |
| `gh pr list` / `git branch -a` | An open PR or branch that already addresses the work |
| llms.txt / package docs | API signatures, available flags, supported versions |
| Existing memory under `memory/` | Whether the question was already answered in a prior session |

After the gate, if a blocking ambiguity remains, proceed to "Asking the user" with what was investigated documented in the question.

**Anti-pattern.** Asking a question whose answer is in the first line of the file the user named.

## 2. XY-Aware Framing

Every narrow user request is potentially a wrong question. Before executing the literal request, restate the underlying goal in one line and verify the literal path solves it.

When the literal request solves only a fragment of the goal, surface the broader goal in the response and offer the goal-level solution alongside the literal one.

```
User: "Extract the last three characters from these filenames."

Bad: write a regex that takes the last three characters.

Good: name the underlying goal ("you want the file extension"),
flag that three characters breaks on `.tar.gz` and on filenames
with no extension, and offer the extension-aware path along with
the literal path so the user can confirm.
```

**When to skip XY framing.**

- The user named both the goal and the means in the same sentence, "use ripgrep to find X for purpose Y".
- Continuation within an approved plan: do not re-verify framing for steps the user already approved.
- The CLAUDE.md "Execute, don't ask" rule fires, list of tasks, "do everything": execute. XY framing applies only when the request is narrow and isolated.

## 3. Asking the User

Format every clarifying question this way, in this order:

1. **The specific question**, as the first line. One blocking question per turn.
2. **What was investigated.** File reads, greps, doc lookups, prior PRs. Cite paths and line numbers when relevant.
3. **The options, each explained in depth.** Name the two or three viable approaches. For each, give a detailed explanation: what it does, how it behaves, and its decisive trade-off. A bare label with no explanation is not an option.
4. **The recommendation.** Name one option as preferred and state the decisive reason. This element is mandatory. Never present a choice as a flat menu and leave the decision fully to the user; always say which one you would take and why. When the options are genuinely equivalent, say so and pick one on a stated tiebreaker.

Constraints:

- One blocking question per turn. Bundling three questions into one message is forbidden; the user can answer only one.
- Ship the question in the first message. No "Can I ask you something?", no hello-only opener, no "Quick question?".
- No rhetorical closers, "Let me know if that helps", "Sound good?". Already enforced by [`hooks/banned-phrases-blocker.py`](../hooks/banned-phrases-blocker.py).
- No apologies, no repeated thanks, no hyper-courtesy.
- When the choice is put through the `AskUserQuestion` tool, the recommended option must be first and its label must end with `(Recommended)`. The reason for the recommendation goes in the question body or the option description.
- Carve-out: when one option is the obvious default, take it and say so in a sentence rather than manufacturing a menu. The recommendation obligation applies when a real choice is genuinely put to the user, not to every branch the assistant could resolve on its own. This composes with the "Execute, don't ask" and Confidence rules in [`../CLAUDE.md`](../CLAUDE.md).

```
Bad: "How should I implement this?"

Good:
  Should I store the cancellation reason on the order, or in a
  separate audit table?

  Investigated: read `models/order.ts:42-78` (no reason field today);
  read `models/audit.ts:1-40` (existing audit pattern); grepped
  for "cancellation" across services (no precedent).

  Option A: add `cancellationReason` to `Order`. Cheap to query,
  couples reason to row lifecycle (lost on hard delete).
  Option B: insert into `OrderAudit` with reason. Preserves history,
  one extra join for every cancellation read.

  Recommend: Option B. The cancellation reason is audit data, and
  losing it on a hard delete is the failure mode most likely to bite
  later; the extra join is cheap next to that.
```

## 4. Status and Error Reports

Lead with the symptom, follow with chronology, end with the hypothesis. Never lead with the theory.

```
Bad: "I think the database is the problem."

Good:
  Symptom: `pnpm test:integration` exits 1; 3 of 247 tests fail
  with "P2002 unique constraint failed on `User_email_key`".
  Chronology: ran the suite clean on commit 9af2b1; failure starts
  after the `createUser` change in 4ce0c3.
  Hypothesis: the new `createUser` retry path runs twice on
  collision; the second call hits the still-present row from
  the first transaction.
```

**Object-Deviation one-liner.** When the update is short, format as `<object> - <deviation>`. The object is the named subject; the deviation is the observable behavior.

```
createUser - throws P2002 on second call
prisma migrate dev - generates phantom drift on fresh DB
ci - actionlint annotates 2 workflows with shellcheck SC2086
```

### 4.1 Bug reports

When reporting a bug, to the user, to a subagent, or in a commit message, every item below is required.

| Element | Rule |
|--------|------|
| Show me | Provide the exact reproduction steps. Not a description of what should reproduce |
| Antelope rule | Freeze on discovery. Capture state, stack, environment, exact error text before patching. Patching mid-discovery destroys the original signal |
| Error fingerprints | Copy the error text verbatim including numbers, codes, paths, hashes. Never paraphrase |
| Be specific | "Broken" and "doesn't work" are not bug reports. State the observable: status code, output line, screen text, file:line |
| Avoid pronouns | "It failed" is ambiguous. Say "the `createUser` call failed" |
| Intermittent faults | If intermittent, state the rate and the pattern. "Fails 3 of 10 runs, always when the suite ordering puts auth.spec.ts first" |
| Workaround position | Workarounds are a footnote, not the resolution. Report the cause if known |

## 5. Briefing Subagents

The Agent prompt is a self-contained instruction. The subagent has no view of the parent conversation.

Required elements in every prompt:

- **Scope.** One sentence on what the agent should produce.
- **File:line refs.** Concrete paths and line numbers from prior investigation.
- **Prior attempts.** What was tried, what failed, what the error was.
- **Output shape.** What the response should contain. Punch list, table, file:line findings.
- **Response length.** A word cap or sentence cap. "Under 200 words" or "one paragraph".

```
Bad: "Find all consumers."

Good:
  Find callers of `createUser` exported from
  `backend/api/services/userService.ts:42`.
  Report each callsite as `file:line` and note whether
  `companyId` is passed. Skip test files.
  Under 200 words.
  Prior attempt: grep on the bare symbol returned 38 hits
  including unrelated `createUser` in `frontend/`; need a
  scoped search.
```

The Agent tool docstring in the system prompt has additional guidance. This rule does not duplicate it; the rule sets the floor.

## 6. Ship the Question

The first message contains the actual question or report. No meta-prompts.

| Forbidden | Rewrite as |
|-----------|-----------|
| "Can I ask you something?" | The actual question |
| "Quick question:" | The actual question, no preamble |
| "Should I check with you about X?" | "X is ambiguous. Options: A or B. Which?" |
| "Anyone good at Prisma?" | The Prisma question, no audience screen |
| "Hi" with no content | The content, optionally prefixed with "Hi" |

When a courteous frame is genuinely useful, append the question to the courtesy in the same message. Never split into two.

## 7. Closing the Loop

Every completed task ends with a one-line resolution. Tag the line so future agents can grep for it.

| Tag | When to use |
|-----|------------|
| `FIXED:` | A specific bug was reproduced and fixed |
| `RESOLVED:` | A non-bug task was finished, an incident was closed, or a question was answered |
| `DONE:` | Generic task closure that is neither a bug fix nor an incident |

The line must name what changed, where, and how it was verified.

```
Bad: "Done."

Good:
  FIXED: race in `createUser`; added `companyId` to test cleanup
  order at `test/setup.ts:42`; ran `pnpm test:integration`, 247
  passing, 0 warnings.

  RESOLVED: index drift between schema and migrations; added 7
  `@@index` entries in `schema.prisma:120-152` with explicit `map:`
  names; `prisma migrate diff --exit-code` returns 0.

  DONE: rule `smart-questions.md` authored at
  `rules/smart-questions.md`; registered in `rules/index.yml:14`;
  cross-references added in pre-flight, writing-precision,
  verification.
```

## 8. When This Rule Does Not Apply

| Situation | Why |
|-----------|-----|
| Single-line typos or trivial config tweaks | The investigation gate, XY framing, and one-blocking-question constraints add noise without value |
| User said "just do it" or gave a multi-step list | CLAUDE.md "Execute, don't ask" fires; execute without per-step framing |
| Continuation within an approved plan | The framing question was already answered when the plan was approved |
| Trivial chat ("yes", "no", "ok") | No Object-Deviation, no FIXED tag, no formal report; just answer |
| Ambiguity in only one field | Investigate silently per CLAUDE.md Confidence rule; ask only when multiple things are unclear |

## 9. Self-Test Gate

Before sending any message that asks a question, reports a status, briefs a subagent, or closes a loop, walk through every item below.

| Test | Question |
|------|----------|
| Ambiguity | Could the reader follow this and arrive at a wrong interpretation? |
| Evidence | Did I show what I investigated, with file paths and grep terms? |
| Theory order | Did I lead with the symptom, not the diagnosis? |
| XY | Did I verify the underlying goal, or did I execute the literal request without checking? |
| Scope | Is this one blocking question, or did I bundle three? |
| Recommendation | If I presented a choice, did I explain each option in depth and name a preferred one with its reason? |
| Ship | Does the first line contain the actual question or report, not a meta-prompt? |
| Tag | If this is a closing message, does it have `FIXED:`, `RESOLVED:`, or `DONE:` and a one-line resolution that names what changed and where? |

A failed test sends the draft back to the keyboard.

## 10. Conflict with Other Rules

This rule sits alongside, not above, the existing rule set. On conflict:

- [`rules/pre-flight.md`](pre-flight.md) governs the investigation gate. This rule extends the gate's output, the question format, not the gate itself.
- [`rules/writing-precision.md`](writing-precision.md) governs sentence-level precision. Apply both: precision per writing-precision, format per this rule.
- [`rules/verification.md`](verification.md) governs evidence for completion. This rule's "Closing the Loop" formats the evidence; verification governs whether the evidence is real.
- [`rules/surgical-edits.md`](surgical-edits.md) governs diff scope. XY framing must surface a broader goal but does not authorize expanding the diff. Surface the goal as a question, then let the user decide whether to expand the scope.

## 11. Why This Rule Exists

The rules above operationalize five canonical sources on question quality. They are cited as inspiration; this file is independently authored.

- "How To Ask Questions The Smart Way" by Eric S. Raymond. PT-BR mirror: <https://area31.net.br/wiki/Como_fazer_perguntas_inteligentes>. EN original: <http://www.catb.org/esr/faqs/smart-questions.html>. Fetched 2026-05-13.
- "How to Report Bugs Effectively" by Simon Tatham. <https://www.chiark.greenend.org.uk/~sgtatham/bugs.html>. Fetched 2026-05-13.
- "The XY Problem". <https://xyproblem.info/>. Fetched 2026-05-13.
- "Don't ask to ask, just ask". <https://dontasktoask.com/>. Fetched 2026-05-13.
- "No Hello". <https://nohello.net/>. Fetched 2026-05-13.

The original config enforced self-investigation, evidence-based completion, and writing precision. It did not codify question format. Without an explicit format, drift is predictable: clarifying questions become "How should I do this?", error reports lead with theory, loop closure becomes "Done.". This rule names the format and the failure modes so future sessions stay coherent.

## Enforcement

Enforced by: [`hooks/subagent-brief-quality.py`](../hooks/subagent-brief-quality.py).
