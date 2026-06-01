# State route

For questions about a state machine, data shape, business workflow, or business rule.

## Goal

Push the model through cases that are hard to reason about on paper. The spike is correct when the user can see, in plain printed output, what happens at every transition.

## Shape

A single entry file under `spike-<short-slug>/` next to the real module:

- `index.<ext>` is the entry point. Runs a REPL or a sequence of prompts.
- An in-memory store holds the model state.
- Each interactive command applies one transition and prints the full state.

Example skeleton (TypeScript):

```ts
// SPIKE: should refunds split the order into two records or mutate one?
// Delete after verdict captured.
type Order = { id: string; lines: Line[]; status: 'open' | 'shipped' | 'refunded' };

let order: Order = { id: 'o1', lines: [...], status: 'open' };

const commands = {
  ship: () => { order = { ...order, status: 'shipped' }; },
  refund: (lineId: string) => { /* the branch under question */ },
};

function printState() { console.log(JSON.stringify(order, null, 2)); }

repl(commands, printState);
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

When the user has seen enough, write a `NOTES.md` next to the spike:

```
Question: should refunds split the order into two records or mutate one?
Verdict: split into two. The mutate path lost the original total once partial refunds layered.
Owner of follow-up: <name>
```

Then run `/plan adr new` if the verdict is hard to reverse, and delete the spike directory.
