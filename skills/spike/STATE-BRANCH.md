# State route

For questions about a state machine, data shape, business workflow, or business rule.

## Goal

Push the model through cases that are hard to reason about on paper. The spike is correct when the user can see, in plain printed output, what happens at every transition.

## Shape

Two files under `spike-<short-slug>/` next to the real module:

- `model.<ext>` holds the logic that answers the question, as a pure module: no I/O, no prompts, no printing. The shell calls into it; nothing flows the other way. This file outlives the spike.
- `index.<ext>` is the throwaway shell. It runs a REPL or a sequence of prompts, holds the current state in memory, applies one transition per command, and prints the full state.

Pick the module shape the question needs, not the one easiest to wire to the shell:

- A reducer, `(state, action) => state`, when actions are discrete events over a single value.
- A state machine with explicit states and transitions, when which actions are legal right now is part of the question.
- A few pure functions over a plain data type, when there is no current state, only transformations.
- A class with a small method surface, when the logic genuinely owns ongoing internal state.

Example skeleton in TypeScript, for the question "should refunds split the order into two records or mutate one?", kept on `spike/refund-split` after the verdict. In `model.ts`:

```ts
export type Order = Readonly<{ id: string; lines: readonly Line[]; status: 'open' | 'shipped' | 'refunded' }>;
export type Action = { type: 'ship' } | { type: 'refund'; lineId: string };

export const apply = (order: Order, action: Action): Order => {
  switch (action.type) {
    case 'ship':
      return { ...order, status: 'shipped' };
    case 'refund':
      return refundLine(order, action.lineId);
  }
};
```

In `index.ts`, the throwaway shell:

```ts
repl({ initial, apply, print: (order) => console.log(JSON.stringify(order, null, 2)) });
```

## What to include

- Every transition the question touches, even the boring ones. The interesting case rarely fails in isolation.
- Invalid transitions as guarded commands that print a refusal. Seeing a refusal is part of the answer.
- A reset command so the user can restart without relaunching.

## What to skip

- Persistence, authentication, retries, telemetry, logging.
- Edge cases outside the question being asked.
- Tests. The spike is the test.

## Verdict capture

When the user has seen enough, record the verdict where the work continues:

```
Question: should refunds split the order into two records or mutate one?
Verdict: split into two. The mutate path lost the original total once partial refunds layered.
Evidence: branch spike/refund-split
Owner of follow-up: <name>
```

Then lift the validated `model.<ext>` into the real module, adding the tests and error paths the spike skipped. Commit the whole spike, shell included, to `spike/<slug>` as [`SKILL.md`](SKILL.md) describes, and remove it from the working branch. If the verdict is hard to reverse, call the Skill tool with `plan` and the arguments `adr new <title>`.
