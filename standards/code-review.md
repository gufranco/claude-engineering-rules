# Code Review

## As Author

- Self-review the entire diff line by line
- Run all tests locally
- Keep PRs small (< 400 lines ideally, max 1000)
- One logical change per PR
- Include before/after screenshots for UI changes
- Verify visual identity consistency: new pages must match existing pages in layout structure, spacing tokens, component usage, badge patterns, loading states, and pagination. Reference the project's visual identity guide (CLAUDE.md) when one exists

## As Reviewee

When others review your PR, the goal is to close every open thread with either an implemented fix or a justified reply. Replies are permanent, public, and shape how reviewers respond to future PRs from you.

### Posture

- Assume the reviewer is closer to the code than you are. They often see things you have stopped seeing because you wrote it.
- Never reply in anger. Walk away if needed. The thread lives forever.
- Treat code review as a learning exchange, not a defense. The point is to ship better code, not to be right.

### Mechanics

- Acknowledge a new comment within 4 hours of becoming aware. A 5-word "starting on this" is enough.
- Respond substantively to a batch within 1 business day. Slower than that, the reviewer disengages.
- Batch your response. One push covers all approved replies and fixes for the round. Multiple drips burn CI minutes and reviewer attention.
- Re-request review explicitly after a batch of fixes. Pair it with a top-level comment summarizing the changes since the last round.
- Use the project's standard shortcuts: `PTAL` for re-review requests; `nit:`, `suggestion:`, `issue:`, `question:` per Conventional Comments when posting your own clarifications.

### Reply Form

- Fix the code before explaining it. If a reviewer did not understand, the code is the first thing to change. A clearer variable name beats a thread reply that future readers will never see.
- Link the fix by SHA in every reply. "Fixed in `c8e2f1a`" gives the reviewer a one-click trail.
- Lead with reasoning when you push back. State what the code does, what would change if you took the reviewer's path, and what you want from the reviewer next. Bare "I disagree" is a known failure mode.
- Ask for clarification when you do not understand. Do not guess at intent. "Curious: is the concern about correctness or performance? If correctness, I'll rework now. If performance, I'd rather measure first."
- When you cannot reproduce, name the steps you tried. "Couldn't reproduce. Steps: A, B, C. Did I miss something?"
- Credit reviewers in commit trailers when they materially improved the code. `Co-authored-by` for code-level contributions. `Suggested-by` for direction the author then implemented independently.

### Thread State

- Resolve threads after addressing them, but only the threads you have fully addressed and that are unambiguous. Leave open anything with an open reply, an open question, a suggestion the author chose not to take, or a request for verification.
- Never bulk-resolve. Each thread gets its own resolve after its own action.
- Outdated is not resolved. GitHub auto-marks comments as outdated when the cited line changes. That is not the same as the discussion being settled. Resolve explicitly.
- Re-open a thread when the reviewer disagrees with your resolution. Re-opening is normal, not a failure.

### Scope

- Defer scope creep to follow-up issues. "Filed as #4521. Out of scope for this PR." Never let one inline comment expand into a multi-file refactor in the same PR.
- Every deferral includes a ticket reference. "I will fix in a follow-up" without a ticket is permanent debt.

### Triage

- Triage AI bot comments by failure mode. Style suggestions that contradict the project's lint config, imagined APIs, and refactors that do not compile are common false positives. Dismiss with one line of reasoning so the bot learns.
- Treat AI bot blocking reviews as P3 until a human reviewer also flags the issue.

### When Two Reviewers Disagree

- Name the conflict. Quote both reviewers verbatim. State your slight preference with reasoning. Ask them to align before you push.
- Escalate to a tiebreaker after one round of mutual non-response. Tech lead, module owner, or architect. Agree to abide by their call.
- Never silently pick one side and revert the other's change.

### Reviewee Anti-Patterns

| Anti-pattern | Why it is wrong |
|--------------|-----------------|
| Bare "Done." with no SHA or context | Forces the reviewer to re-read the whole PR to verify |
| The drive-by accept, implementing the suggestion without checking what it would change | Ships nitpicks and AI noise into production |
| The defensive wall, "works as intended" with no engagement | Disengages, escalates the thread |
| Silent force-push during review | Drops the reviewer's comment context, marks threads outdated without resolving them |
| The TODO smuggle, "I'll fix it later" with no ticket | Cleanup never happens |
| The Ransom Note, holding the patch hostage until the developer does unrelated work | Conflates review with separate scope |
| The Double Team, two reviewers contradict and the author ping-pongs without naming the conflict | Wastes everyone's time |
| The Guessing Game, vague criticism with no acceptance path | The author cannot tell when the comment is satisfied |
| The Priority Inversion, trivia first and then a rewrite that invalidates the trivia | Sunk cost on work that no longer matters |
| The Late-Breaking Design Review, challenging fundamentals on a minor follow-up | Right concern, wrong moment |
| The Catch-22, alternating demands to split and consolidate | Author cannot satisfy both |
| The Flip Flop, objecting to a pattern previously accepted without comment | Inconsistent standard |
| The Death of a Thousand Round Trips, stops at the first nit each cycle | Stretches a 2-day review into 2 weeks |
| Praise Spam, "Thanks!" on every comment, including praise | Adds work without value |
| AI-attribution slip, crediting an AI tool as commit co-author | Obscures actual authorship, violates personal rules |
| Auto-Resolve, author resolves their own threads instantly | Reviewer cannot verify what was actually addressed |
| Scope Creep Accept, inline refactor expands the diff beyond the original ticket | Inverse of the Ransom Note. Diff becomes too big to split |
| Top-Post or Quote Avalanche, replying above the quoted text or including the full reviewer comment | Mailing-list anti-pattern carried into PR replies |

## Review Comments

Write review comments the way a human colleague would. No prefix labels, no structured templates. Just say what you mean directly.

If something needs to be fixed, say it. If you have a question, ask it. If something looks good, say so briefly. Each comment must be its own thought, written naturally, not items from a checklist.

### No Internal Config Leakage (MANDATORY)

Every review comment, PR description, PR comment, Slack message, and any other externally-visible text must read as if a human engineer wrote it from experience. The reader has no access to our internal configuration and must never learn it exists.

**Never reference, cite, or mention:**

- `~/.claude/`, [`rules/`](rules), [`checklists/`](checklists), [`standards/`](standards), [`skills/`](skills)
- File names like `checklist.md`, `code-style.md`, `testing.md`, [`database.md`](standards/database.md)
- Phrases like "per our rules", "per our standards", "category 17", "checklist item 3"
- Rule-sourced phrasing that implies a codified checklist: "this violates rule X", "standard Y requires"
- Internal severity tiers in posted text: `P0`, `P1`, `P2`, or section headings like `## P0 Blocking`, `## P1 Should Fix`, `## P2 Nits`. Severity is something you compute internally to triage; it maps to GitHub's `APPROVE` / `REQUEST_CHANGES` / `COMMENT` verdict, full stop. It does not appear as a label in the body.
- The skill's own invocation arguments: `--backend`, `--frontend`, `--local`, `--post`, `--focus`, `--severity`, or any flag that names how you ran the tool. Never write "Backend-only review" or "Skipped frontend per the `--backend` flag". The first-person voice is plain English about what you actually looked at.
- Conventional Comments label prefixes when posting: `issue (blocking):`, `issue (non-blocking):`, `nitpick:`, `suggestion:`, `question:`, `thought:`, `praise:`, `chore:`, `todo:`. The vocabulary exists for human reviewers to use when they choose. When generated output uses it on every single comment, the uniformity is itself the template tell. Strip the label entirely; the tone of the prose carries the severity.
- Structural section headings carried over from internal taxonomy: `Behavioral Flow Analysis`, `Blast Radius Summary`, `Standards Applied`. These sections inform what you write; their findings reach the reader as plain prose, not under those headings.

**Instead, state the engineering reason directly:**

```
# Bad: leaks internal config
This violates `rules/testing.md` mock policy. Per `checklists/checklist.md`
category 8, mocking internal services is a blocking issue.

# Good: same knowledge, human voice
These tests mock internal services instead of using a real database.
A test that verifies mock wiring proves the mock works, not the code.
If someone reverts the fix, all five tests still pass. That is zero
regression protection for a security fix.
```

This applies to the initial generation, not as a post-hoc rewrite. Comments must be clean from the first draft. Requiring a second pass to "humanize" is a process failure.

The internal config informs what to check. The review comment explains why using engineering reasoning. The reader sees the reasoning, never the source.

A second worked example, with the kind of leak that motivated this rule:

```
# Bad: templated label, internal severity, flag self-reference
issue (blocking): Backend-only review (`--backend`).

P0 Blocking: round-robin path bypasses the under rejection. This
violates the policy documented in our internal review standard.

# Good: same finding, no scaffolding
The round-robin path never runs the under rejection. So a user can
include a one-way under in a round-robin and it lands. Putting the
call in `createRoundRobinBetInternal` after the selections map is
built closes it.
```

**Self-check before posting:**

Scan the draft for the patterns below. If any are present, rewrite before posting:

| Pattern | Why it leaks |
|---------|--------------|
| Line starts with `issue (`, `nitpick:`, `suggestion:`, `thought:`, `question:`, `praise:`, `chore:`, `todo:` | Conventional Comments template tell |
| `P0`, `P1`, `P2`, `P3` as standalone tokens | Internal severity scaffolding |
| `--backend`, `--frontend`, `--local`, `--post`, `--focus`, `--severity` | Skill invocation flag |
| Path tokens that resolve under the personal config tree | Internal paths |
| Bare names of the personal rule files when cited as authority | Internal file names |
| `category 17`, `cat 8`, `checklist item 3` | Internal numbering |
| `Behavioral Flow Analysis`, `Blast Radius Summary`, `Standards Applied` as headings | Internal section labels |
| `per our rules`, `per our standards`, `our internal` | First-person possessive on the configuration |

Enforcement: a Pre-Tool-Use hook on Bash, Write, and Edit blocks commands that publish externally (`gh pr`, `gh api`, `glab mr`, `git commit`, and similar) and Markdown or JSON payload files containing any of the patterns above. If the hook fires, the fix is to rewrite the content, not to bypass the hook.

## Test Evidence (MANDATORY)

Every behavior-changing PR must have passing test evidence. CI pipeline passing is sufficient. Only request manual output when CI doesn't exist, doesn't run tests, or hasn't executed.

## Branch Freshness (MANDATORY)

Before approving any PR, check if the branch is behind the base branch. If it is:

- Request a rebase onto the latest base branch
- Request fresh test evidence after the rebase
- If there are merge conflicts, request resolution and new evidence

A PR with passing tests on stale code proves nothing about the merged result.

## Documentation (README) - MANDATORY

Every task completion MUST include a README check. If the change affects how someone uses or sets up the project, update the README:

- New environment variables
- New API endpoints
- Authentication changes
- New commands or scripts
- Changed setup steps
- New dependencies with setup
- Architecture changes
- New features

## Technical Debt

Not all tech debt is bad. Intentional debt taken with a plan to repay is a valid engineering trade-off. Untracked debt that accumulates silently is the problem.

**When reviewing or completing work:**

- If you introduce a shortcut or known limitation, document it with a `TODO(debt):` comment explaining what the ideal solution is and why it wasn't done now
- If you encounter existing debt while working, note it but do not fix it in the same PR. File it separately
- Classify debt by impact: **blocks future work** (fix soon), **slows development** (schedule), **cosmetic** (backlog)

### Architecture Decision Records (ADR)

For non-trivial architecture decisions, record the decision so future engineers understand WHY, not just WHAT.

Format:

```
# ADR-NNN: <Title>

**Status**: proposed | accepted | deprecated | superseded by ADR-NNN
**Date**: YYYY-MM-DD

## Context
What is the problem or situation that requires a decision?

## Decision
What was decided and why this option over the alternatives?

## Consequences
What are the trade-offs? What becomes easier? What becomes harder?
```

Store ADRs in a `docs/adr/` directory in the repository. Number them sequentially. Never delete a superseded ADR, mark it as superseded and link to the replacement.

## Zero Warnings (MANDATORY)

Apply [`checklists/checklist.md`](checklists/checklist.md) category 17 during every review. Warnings are blocking issues with the same severity as bugs. A PR that "passes CI" but has deprecation warnings or non-fatal annotations is not passing.

## Pre-Completion Checklist

Run through [`checklists/checklist.md`](checklists/checklist.md). All 52 categories apply during implementation as a self-review loop: read the diff, check every applicable category, fix issues, re-read, repeat until clean. Categories 8, 13, 17, and 50 specifically cover reuse verification, test evidence, zero warnings, and clean room verification. Category 51 covers deployment verification and category 52 covers design quality.
