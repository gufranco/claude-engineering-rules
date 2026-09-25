# AI Review Convergence

## Scope

Loaded when a pull request carries automated review comments: a CI review bot, Bugbot, CodeRabbit, Codex, or any tool that samples findings on every push. Triggers in [`index.yml`](../rules/index.yml).

## Core Rule

Zero bot comments is not a reachable state and is not the goal. These tools sample fresh findings on every push, so a loop that pushes until the bots go quiet does not terminate; it just accumulates diff surface until something breaks.

The goal is convergence: a round that produces no verified failure. That is the signal to stop, and it arrives with open comments still on the page.

## The Failure-Scenario Gate

Fix a bot comment only after writing a concrete failure scenario and checking it against the actual code. The scenario names specific inputs or state, and the wrong output, crash, or hole that follows.

When that sentence cannot be written honestly, the correct response is to resolve the thread and make no change. A bot thread gets no reply either way, per [`pr-comment-discipline.md`](../rules/pr-comment-discipline.md). A healthy decline rate on bot comments is roughly 40 to 60 percent. A rate near zero means the gate is not being applied, and every comment is being treated as a defect.

The gate does not apply to human reviewers. Evaluate their comments on the merits, and decline with the reasoning in the thread when you disagree.

## Minimal Diff

A commit that answers a review comment touches the flagged lines and nothing else. No adjacent refactor, no added defensive branch, no reformatting of the surrounding block.

The reason is mechanical rather than stylistic: every extra changed line is fresh surface for the next sampling pass. A commit that fixes one finding and reformats a file invites a new round of findings on the reformat, and the loop widens instead of closing.

## Convergence

When a review round yields no verified-failure fixes, the pull request has converged. Say so and recommend merge. Do not request another pass to confirm the absence of findings, because another pass will sample new ones and the confirmation never arrives.

## Know Which Identity You Are Acting As

On a review surface, the identity behind an action changes what the action means, not only who is credited.

- **Recognize your own prior output.** Comments and reviews left by the identity you are currently acting as are yours. Treating them as someone else's produces duplicate findings and a reply thread arguing with yourself.
- **An action can reclassify the thread.** Replying inside a thread started by an automated reviewer, while acting under a human-typed identity, converts that thread into a human one. Automation that keys on thread authorship then stops touching it, and a pull request held on that thread stays held indefinitely. This is one reason a bot thread gets no reply: the reply changes what the record is. The fix commit and the pull-request description carry what happened, and they carry it better.
- **Supersede your own prior verdict rather than stacking beside it.** Two live verdicts from one identity is an ambiguous state. Dismiss or update the earlier one.
- **Write each report fresh.** Carrying findings forward from a previous round accumulates issues that no longer exist and makes the review look unconverged when it has converged. The report goes to the terminal, since a review summary is never published.

Account selection on the command line is governed by [`multi-account-cli.md`](multi-account-cli.md), and commit authorship by [`git-workflow.md`](../rules/git-workflow.md). This section covers the layer above both: what the identity makes the action mean. The general form is in [`agent-operating-limits.md`](../rules/agent-operating-limits.md).

## Verification Order

A finding that survives the gate still needs its fix verified before anything claims it is fixed. On a human thread, reply after the check passes, never before, and name the commit so a reader can see which revision the claim refers to. On a bot thread, resolve after the check passes.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Treating every bot comment as a defect to fix | Ignores the tools' documented precision; roughly half of findings do not survive scrutiny |
| Pushing until the bots stop commenting | They sample per push, so the condition is unreachable |
| Bundling a refactor into a review-response commit | Creates new surface and triggers a fresh round on it |
| Replying that something is fixed before the check passes | Publishes a claim the author has not verified |
| Replying to a bot thread at all | Nothing reads it, and the reply changes what the thread is |
| Requesting another review pass to confirm a clean state | Guarantees new findings and prevents the loop from closing |
| Applying the failure-scenario gate to a human reviewer | The gate exists for sampled machine output, not considered human judgment |

## Cross-References

- [`pr-comment-discipline.md`](../rules/pr-comment-discipline.md): what may be published on a pull request, and why a bot thread is closed in silence.
- [`../skills/respond/SKILL.md`](../skills/respond/SKILL.md): the per-thread reply and resolve workflow this rule bounds.
- [`verification.md`](../rules/verification.md): what counts as evidence for the claim a reply makes.
- [`surgical-edits.md`](../rules/surgical-edits.md): the diff-width discipline the minimal-diff rule applies here.
- [`smart-questions.md`](../rules/smart-questions.md): how to word a decline so it reads as reasoning rather than refusal.
