---
name: profile
description: Performance profiling and bottleneck identification. Instruments code to find the slowest operations, ranks by impact, and suggests specific optimizations. Use when user says "profile", "why is this slow", "find bottleneck", "performance issue", "slow query", "slow endpoint", "optimize", or needs to find what is causing poor performance. Do NOT use for benchmark comparisons (use /benchmark), load testing (use /test perf), or general code review (use /review).
---

Performance profiling that scans the codebase for common bottleneck patterns, ranks findings by estimated impact, and provides concrete fixes with code examples. Covers database queries, API latency, frontend loading, and algorithmic complexity.

## When to use

- When a specific endpoint, page, or operation is slow.
- When you need to find the highest-impact optimization targets before a release.
- When database query performance is degrading.
- When startup time or build time is unexpectedly long.

## When NOT to use

- For benchmark comparisons between implementations. Use `/benchmark` instead.
- For HTTP load testing with concurrent users. Use `/test perf` instead.
- For general code quality review. Use `/review` instead.
- For security scanning. Use `/audit` instead.

## Arguments

This skill accepts optional arguments after `/profile`:

- No arguments: scan the project for common bottleneck patterns across all categories.
- `<path>`: profile a specific file, directory, or module. Example: `/profile src/services/order.service.ts`.
- `--db`: focus exclusively on database query bottlenecks.
- `--api`: focus exclusively on API endpoint latency.
- `--frontend`: focus exclusively on frontend performance.
- `--startup`: focus on application startup time.

Flags can be combined with a path: `/profile src/api --db`.

## Steps

1. **Identify the performance concern.** If a specific path was provided, scope the analysis to that area. If a focus flag was passed, limit categories accordingly. Otherwise, scan all categories.

2. **Detect the tech stack.** Read package.json, go.mod, Cargo.toml, or equivalent to identify: the framework, the ORM, the database, the frontend framework, the bundler, and the test runner. This determines which patterns to search for.

3. **Scan for database bottlenecks.** Search the codebase for these patterns:
   - **N+1 queries:** ORM calls inside loops or `.map()` callbacks. Grep for query methods like `.findOne`, `.findUnique`, `.find`, `.get` inside `for`, `forEach`, `.map`, `.flatMap`. Each match is a potential N+1.
   - **Missing indexes:** read the schema or migration files. For each query that filters, sorts, or joins on a column, check if that column has an index. Cross-reference queries in service files with index definitions.
   - **Full table scans:** queries without a WHERE clause on large tables, or queries using `LIKE '%term%'` which cannot use indexes.
   - **Unnecessary eager loading:** ORM includes or joins that load relations not used by the calling code. Trace from the query to where its result is consumed.
   - **Missing connection pooling:** check database configuration for pool settings. If the ORM connects without a pool, flag it.
   - **Unbounded queries:** queries without LIMIT that could return thousands of rows. Check for missing pagination.

4. **Scan for API bottlenecks.** Search for these patterns:
   - **Sequential external calls:** multiple `await fetch()` or HTTP client calls that are independent but executed sequentially instead of with `Promise.all`.
   - **Missing caching:** repeated identical queries or computations per request without a cache layer. Look for pure functions called with the same arguments across requests.
   - **Unbounded response sizes:** API endpoints that return entire collections without pagination.
   - **Unnecessary serialization:** objects serialized and deserialized multiple times in the same request path.
   - **Synchronous I/O on request paths:** file reads, DNS lookups, or crypto operations blocking the event loop.
   - **Missing compression:** check if response compression middleware is configured.

5. **Scan for frontend bottlenecks.** Search for these patterns:
   - **Large bundle size:** check build output size. Look for large dependencies imported entirely when only a small part is used.
   - **Unoptimized images:** images served without width/height, missing lazy loading, or served in non-modern formats.
   - **Blocking resources:** synchronous scripts in `<head>`, render-blocking CSS, missing `async` or `defer` on scripts.
   - **Excessive re-renders:** components that re-render on every parent render due to missing `memo`, `useMemo`, or `useCallback`. Look for object or array literals created inline as props.
   - **Missing code splitting:** large route components imported statically instead of with `React.lazy` or dynamic `import()`.

6. **Scan for general algorithmic bottlenecks.** Search for these patterns:
   - **O(n^2) algorithms:** nested loops over the same or related collections. `.find()` inside `.map()` or `.filter()`. Array includes checks inside loops where a Set would be O(1).
   - **Unnecessary allocations in loops:** creating new arrays, objects, or strings inside tight loops that could be pre-allocated or computed once.
   - **Missing pagination:** iterating over unbounded collections from the database or API.
   - **Redundant computations:** the same expensive computation performed multiple times when the result could be cached or memoized.

7. **For each bottleneck found, produce a finding.**

   Each finding includes:
   - **File and line:** exact location.
   - **Category:** database, API, frontend, or algorithmic.
   - **Issue:** what the problem is in one sentence.
   - **Impact estimate:** rough time cost or resource waste. Use qualitative levels: critical, high, medium, low. Critical means seconds of latency or orders of magnitude waste. Low means milliseconds in uncommon paths.
   - **Fix:** concrete code change with a before/after example.

8. **Rank findings by estimated impact.** Critical first, then high, medium, low. Within the same level, order by frequency of execution.

9. **Present the report.** Use this format:

   ```
   ## Bottleneck Report

   **Scope:** <path or "full project">
   **Stack:** <detected stack summary>
   **Findings:** N total (X critical, Y high, Z medium, W low)

   ---

   ### Critical

   #### 1. N+1 query in order listing
   **File:** src/services/order.service.ts:45
   **Issue:** `findUnique` called inside a loop for each order's customer.
   **Impact:** For 100 orders, this executes 101 queries instead of 2.
   **Fix:**
   ```ts
   // Before
   for (const order of orders) {
     order.customer = await prisma.customer.findUnique({ where: { id: order.customerId } });
   }

   // After
   const orders = await prisma.order.findMany({
     include: { customer: true },
   });
   ```

   ### High

   ...

   ### Medium

   ...

   ### Low

   ...

   ---

   ### Summary

   Top 3 actions by impact:
   1. Fix the N+1 query in order listing (critical)
   2. Add pagination to the products endpoint (high)
   3. Replace sequential API calls with Promise.all in checkout (high)
   ```

## Rules

- Focus on measurable impact, not code style. A function that violates naming conventions but runs in O(1) is not a performance finding.
- Quantify wherever possible. "This is slow" is not a finding. "This executes 101 queries instead of 2" is.
- Suggest only fixes that preserve existing behavior. A performance fix that changes semantics is a bug.
- Read the actual code before flagging. A loop that runs over 3 items is not a performance problem even if the pattern looks like O(n^2).
- When the scope is a specific path, still check its callers and callees one level deep. A bottleneck might be in the calling code.
- Do not suggest premature optimization. Only flag patterns that matter at the project's actual or expected scale.
- When unsure about impact, classify as low rather than inflating severity.

## Related skills

- `/benchmark` - Compare performance between implementations with statistical rigor.
- `/test perf` - HTTP load testing with concurrent users and latency percentiles.
- `/review` - General code review covering correctness, security, and quality.
- `/health` - Code quality dashboard with weighted scoring.
