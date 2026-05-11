# ADR-004: Performance Budget for Mutation Method Blocker v2

**Status:** accepted
**Date:** 2026-05-09

## Context

The mutation-method-blocker fires on every Write and Edit invocation against TS or JS files. A slow hook delays the agent's main loop and the user's interactive feedback. The v1 hook had a budget of p95 < 200ms; that budget was loose because v1 ran fewer detectors against a smaller pattern surface.

v2 expands the detector surface from roughly 10 patterns to 50+ across 9 categories. It adds AST escalation when `ast-grep` is on PATH, the `hook_io.py` shim for v2 envelope emission, integrity self-checks, confidence scoring, and per-detector telemetry. Each addition costs latency. Without a tighter budget, the cumulative cost would push the p95 well past 200ms and degrade the agent experience.

A budget that is not enforced is not a budget. The test harness must measure realistic payloads (5KB fixtures), record p50, p95, and p99 across runs, and fail the build when the numbers regress.

## Decision

The v2 budget is:

| Metric | Limit |
|--------|-------|
| p95 latency with AST on | < 180ms |
| p99 latency | < 250ms |
| Mean latency | < 60ms |
| AST off (regex only) | < 100ms p95 |

The budget is enforced by `tests/test_mutation_blocker_perf.py` via the corpus benchmark. The test runs the hook over the fixture corpus 100 times, records timings, and asserts each percentile against the limit.

Profiling is part of the gate: every minor or major version bump runs `cProfile` and records the top 10 time-consuming functions. Findings are appended to the decisions document as a perf addendum so future regressions can be diagnosed against the documented baseline.

## Alternatives Considered

### Keep the v1 budget (p95 < 200ms)

Pros: no test changes. Existing fixtures pass.
Cons: leaves no headroom for future features. The 50-detector surface is more than the 10-detector v1 surface; a budget that fits both is too loose to catch v2-specific regressions.

### Tighten further (p95 < 100ms)

Pros: maximally responsive. Forces detector discipline.
Cons: AST escalation cannot fit. `ast-grep` warm parse is ~20-40ms by itself. A 100ms budget would force AST off, sacrificing the accuracy gain.

### Adaptive budget (loosen on slow systems)

Pros: handles low-end hardware gracefully.
Cons: a soft budget is not a budget. Different machines would see different enforcement. CI would have to bake in machine-specific thresholds.

## Consequences

### Positive

- Performance regressions are caught at PR time, not in production.
- The budget is documented so future detector additions know the cost ceiling.
- Profiling addenda accumulate into a record of what each release optimized.
- Users on slow hardware can fall back to AST off and stay under the regex-only budget.

### Negative

- New detectors must be benchmarked before merging. Detectors that exceed their share of the budget either get rejected or replace existing detectors.
- The 100-iteration benchmark adds a few seconds to the test suite.
- Profiling output is verbose. The decisions addendum grows by a few hundred bytes per release.

### Risks

- Hardware drift: a benchmark that passes on the maintainer's machine may fail on slower CI runners. Budgets are calibrated against the slowest supported runner.
- AST parsers may regress in upstream releases. The hook pins a minimum version of `ast-grep` and includes AST off in the budget so a regression has a fallback.
- Adding native dependencies (e.g. tree-sitter) would shift the cost profile. The current hybrid keeps native code out of the critical path.
