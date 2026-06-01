## Interface options

When the user has picked a consolidation candidate, generate at least three radically different interface designs in parallel and compare them. The first design is rarely the best.

### Step 1: write a brief

Before spawning agents, write a one-page brief for the chosen candidate:

- The constraints any interface must satisfy.
- The dependencies involved and their category from [`REFACTOR-STRATEGY.md`](REFACTOR-STRATEGY.md).
- A code sketch that grounds the constraints. The sketch is not a proposal; it just makes the constraints concrete.

Show the brief to the user. Proceed to step 2 immediately. The user reads while the agents work.

### Step 2: spawn agents in parallel

Use the Agent tool to spawn at least three subagents in parallel. Each produces a radically different interface for the consolidated module. Pin each agent to a different design constraint:

- Agent A: minimize the interface. One to three entry points. Maximize behavior per entry point.
- Agent B: maximize flexibility. Support many use cases and explicit extension points.
- Agent C: optimize for the most common caller. Make the common case trivial; accept that the uncommon case takes more work.
- Agent D (when the dependency category requires it): design around ports and adapters for a remote-or-external dependency.

Each subagent must return:

1. The interface, as types or function signatures, plus the invariants, ordering constraints, and error modes the caller has to internalize.
2. A usage example showing a caller using the interface.
3. A summary of what the implementation hides behind the seam.
4. The dependency strategy: which adapters exist, where the test seam lives.
5. The trade-off: where the design pays off and where it is thin.

Brief each subagent with both VOCABULARY.md terms and the project glossary terms so the candidates name things consistently.

### Step 3: present and compare

Show the designs sequentially so the user can absorb each one. Then write a comparison that contrasts the designs along three axes:

- Depth: how much behavior the interface lets a caller drive per element it exposes.
- Locality: where the next change is likely to concentrate.
- Seam placement: where the test surface lives.

Recommend one design and explain why. If elements from different designs combine well, propose a hybrid. Be opinionated. The user wants a strong read, not a menu.

### Step 4: capture the decision

When the user accepts a design, run `/plan adr new` if the design choice is hard to reverse. Otherwise capture the design in the spec folder's `decisions.md`.
