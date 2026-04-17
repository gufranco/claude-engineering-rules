# Performance

## Core Web Vitals Budgets

Measure on a mid-tier mobile device with a 4G connection, not on a developer MacBook.

| Metric | Budget | What it measures |
|--------|--------|-----------------|
| LCP | Under 2.0s | Largest Contentful Paint: time until the main content is visible |
| INP | Under 150ms | Interaction to Next Paint: responsiveness to user input |
| CLS | Under 0.05 | Cumulative Layout Shift: visual stability during load |

## API Latency Targets

Measure at the application boundary. Network, serialization, and middleware overhead count.

| Percentile | Target | When to investigate |
|-----------|--------|-------------------|
| p50 | Under 100ms | Baseline user experience |
| p95 | Under 500ms | Tail latency affecting 1 in 20 users |
| p99 | Under 1000ms | Worst-case experience, often reveals resource contention |

## Database Query Limits

Every query above 50ms must have an `EXPLAIN ANALYZE` reviewed before shipping. Add indexes or restructure the query.

| Query type | Time limit |
|-----------|-----------|
| Simple lookup by indexed key | Under 5ms |
| Filtered list with pagination | Under 50ms |
| Aggregation or report query | Under 500ms |
| Migration or batch operation | No limit, must not block request-serving queries |

## JavaScript Bundle Budget

| Asset | Compressed size limit |
|-------|---------------------|
| Main JS bundle | Under 300KB |
| Per-route JS chunk | Under 100KB |
| Total CSS | Under 80KB |
| Individual images | Under 200KB, use WebP or AVIF |

## Image Optimization

- Always set `width` and `height` on `<img>` elements. Missing dimensions cause layout shift.
- Set `fetchpriority="high"` on the LCP image. Only one element per page gets this.
- Use `loading="lazy"` for images below the fold.
- Serve responsive images with `srcset` and `sizes`.
- Never serve images larger than the display size.

## DOM and Rendering

- Never perform synchronous DOM reads followed by writes in event handlers. This triggers forced reflow.
- Batch DOM mutations. Use `requestAnimationFrame` or framework batching mechanisms.
- Avoid layout thrashing: reading `offsetHeight` or `getBoundingClientRect` between writes forces browser layout recalculation.
- Debounce scroll and resize handlers. A handler taking 50ms drops frames at 60fps.

## General Rules

- Measure before optimizing. Profile first, fix the bottleneck, measure again.
- Never ignore obvious waste: unnecessary re-renders, N+1 queries, unbounded list rendering, synchronous file reads on the request path.
- Set performance budgets in CI. A budget not enforced is a suggestion.
- Log slow operations: database queries over 100ms, API calls over 500ms, renders over 16ms.
