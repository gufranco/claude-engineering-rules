# Performance

## Core Web Vitals Budgets

Every page must meet these thresholds. Measure on a mid-tier mobile device with a 4G connection, not on a developer MacBook.

| Metric | Budget | What it measures |
|--------|--------|-----------------|
| LCP | Under 2.0s | Largest Contentful Paint: time until the main content is visible |
| INP | Under 150ms | Interaction to Next Paint: responsiveness to user input |
| CLS | Under 0.05 | Cumulative Layout Shift: visual stability during load |

## API Latency Targets

| Percentile | Target | When to investigate |
|-----------|--------|-------------------|
| p50 | Under 100ms | Baseline user experience |
| p95 | Under 500ms | Tail latency affecting 1 in 20 users |
| p99 | Under 1000ms | Worst-case experience, often reveals resource contention |

Measure at the application boundary, not at the database layer. Network, serialization, and middleware overhead count.

## Database Query Limits

| Query type | Time limit |
|-----------|-----------|
| Simple lookup by indexed key | Under 5ms |
| Filtered list with pagination | Under 50ms |
| Aggregation or report query | Under 500ms |
| Migration or batch operation | No limit, but must not block request-serving queries |

Every query above 50ms must have an `EXPLAIN ANALYZE` reviewed before shipping. Add indexes or restructure the query.

## JavaScript Bundle Budget

| Asset | Compressed size limit |
|-------|---------------------|
| Main JS bundle | Under 300KB |
| Per-route JS chunk | Under 100KB |
| Total CSS | Under 80KB |
| Individual images | Under 200KB, use WebP or AVIF |

## Image Optimization

- Always set `width` and `height` attributes on `<img>` elements. Missing dimensions cause layout shift.
- Set `fetchpriority="high"` on the LCP image. Only one element per page gets this.
- Use `loading="lazy"` for images below the fold.
- Serve responsive images with `srcset` and `sizes` attributes.
- Never serve images larger than the display size. A 4000px image in a 400px container is 10x the bytes.

## DOM and Rendering

- Never perform synchronous DOM reads followed by writes in event handlers. This triggers forced reflow.
- Batch DOM mutations. Use `requestAnimationFrame` or framework batching mechanisms.
- Avoid layout thrashing: reading `offsetHeight` or `getBoundingClientRect` between writes forces the browser to recalculate layout.
- Debounce scroll and resize handlers. 60fps means 16ms per frame. A handler that takes 50ms drops frames.

## General Rules

- Measure before optimizing. Profile first, fix the bottleneck, measure again.
- Avoid premature optimization, but never ignore obvious waste: unnecessary re-renders, N+1 queries, unbounded list rendering, synchronous file reads on the request path.
- Set performance budgets in CI. Lighthouse CI, bundlesize, or equivalent. A budget that is not enforced is a suggestion.
- Log slow operations. Any database query over 100ms, any API call over 500ms, any render over 16ms deserves a log entry with context.
