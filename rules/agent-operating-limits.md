# Agent Operating Limits

## Core Rule

Every limit placed on an agent run, a turn ceiling, a per-run change cap, a tool allowlist, a context injection, is a decision with a cost. State the measurement that set it, or state that none was taken. A number chosen because it sounded safe is a guess wearing the shape of a budget.

Two limits behave in opposite ways, and confusing them is the common failure:

| Kind | Behavior when hit | How to set it |
|---|---|---|
| Backstop | Aborts the run and returns nothing | Above the observed ceiling, with headroom |
| Budget | Degrades gracefully, returns partial work | At the point where marginal value stops |

A backstop set at a budget's value converts a slow run into a total loss. A budget set at a backstop's value never binds.

## Setting a Backstop

A turn ceiling, a timeout, and a hard iteration cap are backstops. Tripping one costs the entire run: the work is discarded, nothing is reported, and the cost already spent buys nothing.

The number therefore goes **above** the observed ceiling, never at the expected value.

```
Measurement: 68 turns observed as the maximum across 60 sampled runs.
Wasted turns from denied tool calls account for roughly 8 of those.
Ceiling set to 60, which clears the corrected maximum with headroom.
Tightening below 60 pays off only if the denial reduction holds.
Re-measure before changing it.
```

Three obligations:

- **Sample before setting.** A ceiling with no observed distribution behind it is arbitrary in both directions.
- **Subtract known waste.** A ceiling measured against runs that burned turns on denied calls is measuring the waste, not the work. Fix the waste, then re-measure.
- **Record the measurement beside the number.** The next person to tighten it needs the distribution, not the conclusion.

## Setting a Cap

A per-run change cap is a budget. It bounds blast radius and keeps a run reviewable. Hitting it is a normal outcome, not a failure.

The rule that makes a cap work: **overflow is reported, never dropped.** Findings past the cap go into the run's output as a list for the next pass. A cap that silently truncates reads as "covered everything" when it did not, which is the failure named in [`verification.md`](verification.md) under no-silent-caps.

Caps worth setting on any long autonomous run:

| Cap | Why |
|---|---|
| Files changed per run | Bounds review surface, per [`surgical-edits.md`](surgical-edits.md) |
| Findings acted on per pass | Keeps a review round convergent, per [`ai-review-convergence.md`](ai-review-convergence.md) |
| Items serviced per run, oldest first | Makes progress deterministic and fair across runs |
| Iterations before declaring no progress | Prevents a loop that finds nothing from running forever |

## The Cost of a Denied Call

A tool call that is refused still costs a full turn. It consumes context, produces no result, and on a run with a turn ceiling it consumes budget that the actual work needed.

This makes some habits expensive in a way that is invisible without measuring:

- **Compound shell commands** where the harness allows one command per call. Each blocked attempt is a wasted turn, and retrying the same shape wastes another.
- **Reaching for a tool or skill that is not available in this context.** Repeated attempts cost a turn each and never succeed.
- **Unprojected API and query results.** A response returned whole is re-read on every subsequent turn for the rest of the run. Project to the fields actually needed at the point of the call, never after.
- **Reading a large reference set to find one fact.** See the anti-read discipline in [`../standards/agent-instruction-files.md`](../standards/agent-instruction-files.md).

When a call is denied, the correct response is to change the shape of the request, not to retry it. A denial repeated three times is a signal that the capability is absent, per the escalation rule in [`../CLAUDE.md`](../CLAUDE.md).

## The Unconditional Injection Tax

Context injected on every turn, through an always-firing prompt hook or an always-loaded instruction, is paid on every turn for the whole session. That is acceptable when it fires correctly. It is a compounding loss when it fires in a context its author did not anticipate.

The specific hazard: an unconditional injection that instructs the agent to reach for a capability that is unavailable in some contexts costs a denied turn in each of those contexts, forever, with no signal that it is happening.

Obligations for anything that injects unconditionally:

- **Prefer a condition.** A matcher, a path scope, or a keyword trigger turns a fixed tax into a targeted one.
- **State what happens where the injection is wrong.** If the answer is "a wasted turn", the injection needs a condition.
- **Never instruct toward a capability without confirming it exists in that context.** Naming a tool, skill, or command that may be absent converts the injection into a denial generator.
- **Audit periodically.** An injection added for a workflow that no longer exists is pure cost.

## Fail Closed

A verification tool that fails to run is a failed check, never a skipped one.

| Situation | Correct interpretation |
|---|---|
| A classifier exits non-zero | Treat every item as the most restrictive class |
| A capability or state file is missing | Treat every capability as not granted |
| A gate's output cannot be parsed | The gate did not pass |
| A check errored rather than reporting | The check failed |
| A permission state cannot be read | Assume the narrower permission |

The reason is asymmetry. Failing closed costs a false stop, which is visible and cheap to clear. Failing open costs an unverified change that looks verified, which is invisible and expensive.

Two mechanics that make fail-closed real rather than nominal:

- **Gate on the exit code, never on grepping output.** A `grep` for a success string matches inside an error message, inside a warning, and inside the tool's own help text. Substring matching makes a gate report false success, which is not gating.
- **Read the stream the tool actually writes to.** Diagnostics commonly go to `stderr`, so a pipeline that discards `stderr` reads an empty stream and the loop over it runs zero times while appearing to succeed. Confirm which stream carries the payload before depending on it.

## Identity Is An Operating Parameter

An agent acting through an account changes what its actions mean, not only who is credited.

- **Know which identity you post as** before commenting, reviewing, or resolving anything. Prior output from that identity is your own, and recognizing it is what lets you skip, supersede, or resolve correctly rather than duplicating.
- **An action can change a record's class.** Replying in a thread as a human-typed identity can convert an automated thread into a human one, changing which automation will touch it afterward. Check what class the target is in before acting on it.
- **Dismiss or supersede your own prior output** rather than stacking a new result beside a stale one. Two live verdicts from the same identity is an ambiguous state.
- **Generate a summary fresh each run.** Carrying findings forward from a previous run's summary accumulates issues that no longer exist.

Identity at the account level is governed by [`../standards/multi-account-cli.md`](../standards/multi-account-cli.md) and the git-author rule in [`git-workflow.md`](git-workflow.md). This section covers the layer above: what the identity makes an action mean.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| A turn ceiling, timeout, or iteration cap with no recorded measurement | Arbitrary in both directions, and un-tightenable later |
| Setting a backstop at the expected value | Converts a slow run into a total loss |
| A cap that silently truncates its overflow | Reads as full coverage when it is partial |
| Retrying a denied call in the same shape | Each attempt costs a turn and none will succeed |
| Returning whole API or query responses when a projection exists | Re-read on every subsequent turn for the rest of the run |
| An unconditional injection naming a capability that may be absent | Generates a denied turn per run, silently, forever |
| Treating a check that errored as a check that was skipped | Fails open on the exact case most likely to hide a defect |
| Gating on a grep of output rather than on the exit code | Matches inside errors and help text, so the gate reports false success |
| Acting on a thread or record without knowing which identity you act as | The action can silently change what the record is |

## Interaction With Other Rules

[`verification.md`](verification.md) defines what evidence is. This rule defines the cost of gathering it and what to do when the gathering mechanism itself fails.

[`writing-precision.md`](writing-precision.md) section 7b requires every decision to carry its evidence. An operating limit is a decision, so it carries its measurement.

[`ai-review-convergence.md`](ai-review-convergence.md) bounds the review loop specifically; the per-pass cap here is the general form.

[`../standards/agent-instruction-files.md`](../standards/agent-instruction-files.md) covers anti-read directives and context routing, which are the largest lever on run cost.

## Provenance

Promoted 2026-08-26, `single-incident`, under the fails-without-an-error-signal condition for the unconditional-injection and fail-open cases. Origin: an audit of an external agent review pipeline whose turn ceiling carried its sampled distribution inline, whose plugin-supplied prompt hook had to be disabled because it instructed toward a capability absent in that context and cost a denied turn on every run, and whose classifier failures were specified to fail closed rather than to skip.
