# Pull Request Comment Discipline

## Core Rule

The only comment this configuration publishes on a pull request is a reply inside a thread a person opened.

Four consequences, each absolute:

| Surface | Rule |
|---|---|
| Reply in a human's thread | The one permitted comment. Four sentences at most |
| Review summary body | Never written. Submit reviews with an empty body |
| Pull-request conversation comment | Never written, on any platform |
| Commit-comment reply | Never written. Fix the code and say it in the commit |
| Any reply to a bot thread | Never written. Read it, fix a real finding, resolve, close |
| New inline thread | Only on a pull request authored by someone else, and only to name a defect at the line it lives on |

A tracker item is never the answer to a problem that can be fixed in the open change.

## Why This Rule Exists

Two prose layers already govern comment voice. [`../standards/code-review.md`](../standards/code-review.md) forbids labels, templates and checklist shape; [`anti-slop.md`](anti-slop.md) catalogues the rhetorical shapes and records a corpus calibration that returned no findings across 209 of this repository's own Markdown files. Where a person chooses whether to write at all, the voice holds.

The slop was concentrated in the artifacts with a mandatory slot and nothing to fill it:

- A review summary body that the skill required to be non-empty, because the GitHub API cannot edit an empty body afterwards. An API constraint became a paragraph of prose on every review.
- A reply to a bot, whose own register rule conceded that the audience has no stake, cannot be persuaded, will not answer, and does not remember the thread. An audience with none of those properties needs no message at all.
- A reply into a channel with no reply endpoint, answered by opening a fresh conversation comment that nobody threads to the point it answers.

Writing better prose into those three slots was the wrong fix. The slots are gone.

## Reading Is Still Mandatory

[`../standards/pr-comment-channels.md`](../standards/pr-comment-channels.md) exists because an inline-only sweep missed a blocking report. Every channel is still fetched, still classified, and still acted on. Only the shape of the answer changed.

| Channel | How it gets answered now |
|---|---|
| Inline thread, human | A reply in the thread, then resolve |
| Review summary body | The code changes; the commit message names the point |
| Conversation comment | Same |
| Commit comment | Same |
| Any channel, bot | The code changes if the finding is real; the thread is resolved or minimized |

A question that reaches no reply still reaches a fix. When the fix alone would leave the reviewer guessing, the pull-request description carries the sentence, since that is where a reader looks for why.

## Never Reply To A Bot

A bot thread is read, verified against the code, acted on, and closed. No verdict line, no acknowledgment, no dismissal note.

The failure-scenario gate in [`ai-review-convergence.md`](ai-review-convergence.md) still decides whether a finding is real: write the concrete inputs and the wrong output first, check them against the code, and fix only what survives. What changes is the closure. A surviving finding is closed by the commit that fixes it. A finding that does not survive is closed by resolving the thread.

| Thread state | Action |
|---|---|
| Resolvable, such as an inline review thread | Resolve it |
| Not resolvable, such as a bot conversation comment | Minimize it with the reason the platform offers |

No mechanical check can enforce this, because a publishing command carries a comment id rather than an author. The rule holds on judgment and is audited at [`../skills/retro/SKILL.md`](../skills/retro/SKILL.md).

## How A Reply Reads

Polite and direct, never warm and long. A reviewer is a person with other work.

- **Answer the point, then stop.** Four sentences is the ceiling. Reasoning past that belongs in the code or the pull-request description.
- **Lead with what changed.** The fix and its commit, or the answer, in the first sentence.
- **Courtesy fits in a clause.** Never a paragraph, never an apology, never repeated thanks.
- **No restatement.** The reviewer wrote the comment and can see it above your reply.
- **No closing offer.** A reply that ends by asking whether anything else is needed has added a sentence and no information.
- **Vary the opening.** Every reply beginning with the same word reads as a template.

When pushing back, name the constraint rather than the preference: what the code does, what the reviewer's path would break, and what you want from them next. That fits inside the ceiling.

Good, in full:

```
Fixed in a1b2c3d. The round-robin path built its own selections map and
skipped the guard, so both routes now go through one helper.

Switching to requestAnimationFrame would skip the ping on a backgrounded
tab, which breaks the keep-alive contract. Want me to name that in the
function, or do you see an API that keeps the behavior?

Good catch, thanks. Pushed the null check plus a regression test.
```

What the ceiling forbids:

```
You are right, and the reason it matters is worse than the line suggests.
buildDbUrl hardcodes the limit in both branches, so the fallback was the
one path that ignored the cap this change exists to add, which means the
pool could grow past the ceiling under load, and the same shape probably
appears in the other two builders, so I went through those as well and...
```

## Fix It Now

A problem found while the change is open is fixed in that change. Never recorded, never scheduled, never handed to a tracker.

| Never | Instead |
|---|---|
| Filing an issue for a defect you could fix | Fix it in this change |
| A reply promising a follow-up change | Make the change |
| A reply naming a separate pull request | Make the change here |
| A code marker recording the debt | Fix it. Markers are banned by [`code-style.md`](code-style.md) |
| Closing a thread by pointing at a ticket | Close it by fixing the code |

The one genuine exception is a fix blocked outside the change: a coordinated release across services, a migration another team owns, an upstream release that has not shipped. State the blocker in one sentence in the reply and create nothing. The blocker is the message; a ticket adds nothing the reviewer can act on.

An explicit request to export a plan to a tracker is a different thing, and [`../skills/plan/SKILL.md`](../skills/plan/SKILL.md) still serves it. The ban is on deferral, never on planning the user asked for.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| A pull-request conversation comment | No thread, no reader who asked |
| A review submitted with a summary body | The slot exists for an API reason, not a communicative one |
| A reply to a commit comment | Answer by fixing the code |
| A reply of any length to a bot | The audience cannot read it |
| A verdict line recorded for later readers | The commit is the durable record |
| A new inline thread on your own pull request | A finding in your own code is a commit |
| A reply longer than four sentences | The reasoning belongs in the code or the description |
| A reply restating the comment it answers | The reviewer wrote it |
| A reply ending with an offer of further help | A sentence with no information |
| A ticket, issue, or follow-up standing in for a fix | The problem is still there |

## Cross-References

- [`../standards/pr-comment-channels.md`](../standards/pr-comment-channels.md): what a pull-request comment is on each platform, and the fetch that stays mandatory.
- [`../standards/code-review.md`](../standards/code-review.md): comment voice, and the internal taxonomy that never reaches a reader.
- [`ai-review-convergence.md`](ai-review-convergence.md): the failure-scenario gate and the stop condition for a review loop.
- [`anti-slop.md`](anti-slop.md): the shapes a reply must not take.
- [`found-fix.md`](found-fix.md): a problem surfaced by any verification surface is in scope for the current change.
- [`no-ai-process-leak.md`](no-ai-process-leak.md): what a reply must never disclose about how it was produced.
- [`../skills/respond/SKILL.md`](../skills/respond/SKILL.md): the workflow this rule governs.

## Provenance

Promoted 2026-09-17, `single-incident`, under the fails-without-an-error-signal condition. A content-free artifact passes every gate: it compiles nothing, breaks nothing, and reads as diligence, so the cost lands on the reviewer who scrolls past it rather than on any check.

Origin: an audit of this configuration's own pull-request surfaces found three slots that required text and supplied no subject. A review summary body mandated non-empty because the GitHub API cannot edit an empty one later. A bot reply governed by a register whose stated premises argued for no reply at all. Three channels with no reply endpoint answered by opening unthreaded conversation comments. The reply-only rule, the no-bot-reply rule, the four-sentence ceiling, and the fix-now rule were set by the repository owner in the same session.

## Enforcement

Enforced by: [`../hooks/pr-comment-discipline.py`](../hooks/pr-comment-discipline.py).
Enforced by: [`../hooks/ai-slop-blocker.py`](../hooks/ai-slop-blocker.py).
Enforced by: [`../hooks/found-fix-rationalization-blocker.py`](../hooks/found-fix-rationalization-blocker.py).
