---
name: benchmark
description: Performance regression detection. Measures API latency, bundle size, and database query time, then compares against saved baselines. Use when user says "benchmark", "performance check", "check for regressions", "bundle size", "latency", "is this slower", or wants to detect performance changes. Do NOT use for code quality scoring (use /health), load testing setup, or profiling.
---

Establishes performance baselines and detects regressions by comparing current measurements against stored reference values.

## Arguments

| Invocation | Action |
|-----------|--------|
| `/benchmark` | Run all available measurement categories |
| `/benchmark api` | Measure API endpoint latency only |
| `/benchmark bundle` | Measure JS bundle size only |
| `/benchmark db` | Measure database query time only |
| `/benchmark --save` | Run all and save results as the new baseline |
| `/benchmark api --save` | Run API latency and save as baseline |

## Measurement Categories

### API Latency

1. **Detect available tools.** Check for load testing tools in order of preference:
   - `which k6`
   - `which wrk`
   - `which hey`
   - `which ab`
   - Fall back to `curl` with timing if none are installed.

2. **Identify endpoints.** Read route files or API documentation to find endpoints. Ask the user which endpoints to benchmark if the project has more than 10.

3. **Run measurements.** For each endpoint, measure:
   - p50 latency in milliseconds.
   - p95 latency in milliseconds.
   - p99 latency in milliseconds.
   - Requests per second.

4. **Report per endpoint:**

   | Endpoint | p50 | p95 | p99 | RPS |
   |----------|-----|-----|-----|-----|

### Bundle Size

1. **Build the project.** Run the build command from the project's scripts.

2. **Measure output.** For each output file in the build directory:
   - Raw size in bytes.
   - Gzipped size in bytes.

3. **Report:**

   | File | Raw | Gzipped |
   |------|-----|---------|

### Database Query Time

1. **Identify slow queries.** Look for query logging configuration in the ORM or database config.

2. **Run the test suite with query timing.** If the ORM supports query logging, enable it and capture execution times.

3. **Report queries exceeding 100ms:**

   | Query | Duration | Location |
   |-------|----------|----------|

## Baselines

Baselines are stored in `.claude/benchmarks/<project>.json` relative to the project root.

```json
{
  "timestamp": "2026-04-04T12:00:00Z",
  "api": {
    "GET /api/users": {"p50": 12, "p95": 45, "p99": 120, "rps": 850},
    "POST /api/orders": {"p50": 25, "p95": 80, "p99": 200, "rps": 420}
  },
  "bundle": {
    "main.js": {"raw": 245000, "gzipped": 78000},
    "vendor.js": {"raw": 890000, "gzipped": 210000}
  },
  "db": {
    "findUserById": {"p50": 2, "p95": 8}
  }
}
```

## Comparison

When a baseline exists, compare every measurement against it:

1. **Compute deltas.** For each metric, calculate the percentage change from baseline.

2. **Flag regressions.** A regression is any metric that worsened beyond the threshold:

   | Metric | Regression threshold |
   |--------|---------------------|
   | API p50 | > 20% slower |
   | API p95 | > 30% slower |
   | API p99 | > 50% slower |
   | Bundle raw size | > 10% larger |
   | Bundle gzipped size | > 10% larger |
   | DB query time | > 25% slower |

3. **Report with deltas:**

   | Metric | Baseline | Current | Delta | Status |
   |--------|----------|---------|-------|--------|
   | GET /api/users p50 | 12ms | 15ms | +25% | REGRESSION |
   | main.js gzipped | 78KB | 76KB | -2.6% | OK |

4. **Summary.** State total regressions found, total improvements, and unchanged metrics.

## Saving Baselines

When `--save` is passed:

1. Run all requested measurements.
2. Write results to `.claude/benchmarks/<project>.json`.
3. Create the `.claude/benchmarks/` directory if it does not exist.
4. If a baseline already exists, show the diff before overwriting.
5. Confirm the save to the user.

## Rules

- Benchmarks must run against a local or staging environment, never production.
- Report median, not mean. See `../../rules/testing.md` benchmark methodology section.
- When no load testing tool is installed, state which tools are supported and ask whether to install one. Do not silently fall back to inaccurate methods.
- Bundle size measurements require a fresh build. Do not measure stale build artifacts.
- All timestamps in GMT.
- Never modify source code during benchmarking. This is a measurement-only skill.
- Include the runtime version, tool version, and measurement date in every report.

## Related Skills

- `/health` -- Quality scoring covers different dimensions than performance.
- `/test` -- Run the test suite, which may include performance tests.
- `/ship checks` -- Check CI pipeline, which may include performance gates.
