# AI Review Convergence

## Scope

Loaded when a pull request carries automated review comments: a CI review bot, Bugbot, CodeRabbit, Codex, or any tool that samples findings on every push. Triggers in [`index.yml`](index.yml).

## Core Rule

Zero bot comments is not a reachable state and is not the goal. These tools sample fresh findings on every push, so a loop that pushes until the bots go quiet does not terminate; it just accumulates diff surface until something breaks.

The goal is convergence: a round that produces no verified failure. That is the signal to stop, and it arrives with open comments still on the page.

## The Failure-Scenario Gate

Fix a bot comment only after writing a concrete failure scenario and checking it against the actual code. The scenario names specific inputs or state, and the wrong output, crash, or hole that follows.

When that sentence cannot be written honestly, the correct response is a reply declining the change with the reasoning, not a defensive edit. A healthy decline rate on bot comments is roughly 40 to 60 percent. A rate near zero means the gate is not being applied, and every comment is being treated as a defect.

The gate does not apply to human reviewers. Evaluate their comments on the merits.

## Minimal Diff

A commit that answers a review comment touches the flagged lines and nothing else. No adjacent refactor, no added defensive branch, no reformatting of the surrounding block.

The reason is mechanical rather than stylistic: every extra changed line is fresh surface for the next sampling pass. A commit that fixes one finding and reformats a file invites a new round of findings on the reformat, and the loop widens instead of closing.

## Convergence

When a review round yields no verified-failure fixes, the pull request has converged. Say so and recommend merge. Do not request another pass to confirm the absence of findings, because another pass will sample new ones and the confirmation never arrives.

## Know Which Identity You Are Acting As

On a review surface, the identity behind an action changes what the action means, not only who is credited.

- **Recognize your own prior output.** Comments and reviews left by the identity you are currently acting as are yours. Treating them as someone else's produces duplicate findings and a reply thread arguing with yourself.
- **An action can reclassify the thread.** Replying inside a thread started by an automated reviewer, while acting under a human-typed identity, converts that thread into a human one. Automation that keys on thread authorship then stops touching it, and a pull request held on that thread stays held indefinitely. Check what a thread is before replying in it; when the intent is only to record that a finding was addressed, the fix commit and the pull request body carry that better than an in-thread reply does.
- **Supersede your own prior verdict rather than stacking beside it.** Two live verdicts from one identity is an ambiguous state. Dismiss or update the earlier one.
- **Write each summary fresh.** Carrying findings forward from a previous round accumulates issues that no longer exist and makes the review look unconverged when it has converged.

Account selection on the command line is governed by [`multi-account-cli.md`](../standards/multi-account-cli.md), and commit authorship by [`git-workflow.md`](git-workflow.md). This section covers the layer above both: what the identity makes the action mean. The general form is in [`agent-operating-limits.md`](agent-operating-limits.md).

## Verification Order

A finding that survives the gate still needs its fix verified before the reply claims it. Reply after the check passes, never before, and name the commit in the reply so a reader can see which revision the claim refers to.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Treating every bot comment as a defect to fix | Ignores the tools' documented precision; roughly half of findings do not survive scrutiny |
| Pushing until the bots stop commenting | They sample per push, so the condition is unreachable |
| Bundling a refactor into a review-response commit | Creates new surface and triggers a fresh round on it |
| Replying that something is fixed before the check passes | Publishes a claim the author has not verified |
| Requesting another review pass to confirm a clean state | Guarantees new findings and prevents the loop from closing |
| Applying the failure-scenario gate to a human reviewer | The gate exists for sampled machine output, not considered human judgment |

## Cross-References

- [`../skills/respond/SKILL.md`](../skills/respond/SKILL.md): the per-thread reply and resolve workflow this rule bounds.
- [`verification.md`](verification.md): what counts as evidence for the claim a reply makes.
- [`surgical-edits.md`](surgical-edits.md): the diff-width discipline the minimal-diff rule applies here.
- [`smart-questions.md`](smart-questions.md): how to word a decline so it reads as reasoning rather than refusal.
