## Refactor strategy

How to deepen a cluster of shallow modules safely. Assumes the vocabulary in [`VOCABULARY.md`](VOCABULARY.md).

### Classify the dependencies first

The deepened module needs to talk to something. The category chooses the seam shape and the testing strategy.

#### Category 1: in-process

Pure computation. In-memory state. No I/O. No network.

- Always consolidatable.
- No seam at the external interface. Internal seams may exist for the module's own tests.
- Test the deepened module by calling the new interface directly.

#### Category 2: local-substitutable

A local stand-in exists for the dependency. Examples: an in-memory database such as PGLite for Postgres, a memfs filesystem, a fake clock.

- Consolidatable when the stand-in is available in the test suite.
- The seam is internal to the module. No port appears in the external interface.
- Test through the stand-in running in the same process as the test.

#### Category 3: remote but owned

Your own service across a network boundary. Microservice, internal HTTP API, internal queue.

- Define a port (an interface) at the seam. The deep module owns the logic.
- Implement two adapters: one in-memory for the test suite, one real transport for production.
- The recommendation: "Define a port at the seam. Implement an HTTP adapter for production and an in-memory adapter for testing. The logic lives in one deep module even though it is deployed across a network."

#### Category 4: external and not owned

A third-party API. Stripe, Twilio, Salesforce.

- Inject a port for the third party at the deepened module's edge.
- Tests provide a mock adapter for the port.
- Production hits the real third-party API through a thin adapter that translates between our port and theirs.

### Seam discipline

- One adapter is hypothetical. Two are real. Never introduce a port unless at least two adapters are justified. A single-adapter port is indirection without payoff.
- Internal seams are private to the module's implementation and usable by the module's own tests. Do not expose them through the external interface just because the tests use them.

### Testing strategy: replace, do not layer

- Old tests on the shallow modules become waste once the deepened module is tested at its interface. Delete the old tests.
- New tests assert on observable outcomes through the deepened interface. They survive internal refactors.
- A test that has to change when the implementation changes is testing past the interface. The interface is the wrong shape, or the test is.

### Heuristic order

1. Is every dependency in Category 1? Consolidate. No port.
2. Is some dependency in Category 2? Consolidate. Use the stand-in for tests.
3. Is some dependency in Category 3 or 4? Decide whether two adapters are real. If yes, introduce a port. If no, postpone the port and consolidate without it.
