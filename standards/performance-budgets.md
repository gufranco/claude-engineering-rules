# Performance Budgets

## Core Web Vitals Targets

These are the thresholds for "good" scores. Measure on real user data, not just lab tests.

| Metric | Target | What it measures |
|--------|--------|-----------------|
| LCP | Under 2.0s | Largest visible content element fully rendered |
| INP | Under 150ms | Responsiveness to user interactions across the page lifecycle |
| CLS | Under 0.05 | Visual stability, cumulative layout shift |

- Measure with Real User Monitoring, not just Lighthouse. Lab scores hide device and network variance.
- Track p75 values. The 75th percentile reflects the experience of most users, including slower devices and connections.
- Separate metrics by page type. A landing page has different budgets than a data-heavy dashboard.

## Resource Budgets

Hard limits on asset sizes. Exceeding any budget requires explicit justification and team review.

| Resource | Budget | Rationale |
|----------|--------|-----------|
| JavaScript, compressed | Under 300KB | Main thread blocking, parse time on mobile |
| CSS, compressed | Under 80KB | Render-blocking, CSSOM construction |
| Hero image | Under 200KB | LCP element, usually the largest single asset |
| Total page weight | Under 1.5MB | Bandwidth on mobile networks |
| Third-party scripts | Max 5 | Each script adds DNS lookup, connection, and execution cost |
| Web fonts | Max 2 families, 4 files | Font loading blocks text rendering |

## CI Enforcement

Alert when resource sizes reach 80% of the budget. Fail the build when the budget is exceeded.

```yaml
# Example: Lighthouse CI budget configuration
budgets:
  - resourceSizes:
      - resourceType: script
        budget: 300
      - resourceType: stylesheet
        budget: 80
      - resourceType: image
        budget: 200
      - resourceType: total
        budget: 1500
  - timings:
      - metric: largest-contentful-paint
        budget: 2000
      - metric: interactive
        budget: 3500
```

Integrate size checks into the build pipeline:

1. Measure bundle size after build.
2. Compare against the budget.
3. Warn at 80% of the limit.
4. Fail at 100%.
5. Report the delta from the previous build in the PR comment.

## LCP Optimization

The LCP element is usually a hero image, a heading, or a large text block. Optimize the critical path to it.

- Add `fetchpriority="high"` on the LCP image element. This tells the browser to prioritize it over other resources.
- Preload the LCP image: `<link rel="preload" as="image" href="..." fetchpriority="high">`.
- Inline critical CSS for the above-the-fold content. Defer non-critical CSS.
- Avoid lazy-loading the LCP element. Lazy loading delays discovery.
- Server-render the LCP content. Client-side rendering adds a JavaScript-dependent delay.

```html
<!-- LCP image with priority hints -->
<img
  src="/hero.webp"
  alt="Product showcase"
  width="1200"
  height="600"
  fetchpriority="high"
  decoding="async"
/>
```

## INP Optimization

INP measures the latency of all interactions, not just the first. Long tasks block the main thread and degrade responsiveness.

- Break long tasks with `scheduler.yield()`. Yield after each logical unit of work to let the browser process pending interactions.
- Move heavy computation to Web Workers.
- Debounce rapid-fire inputs like search-as-you-type.
- Avoid synchronous layout reads followed by writes. Batch DOM reads, then batch DOM writes.

```typescript
async function processLargeList(items: readonly Item[]): Promise<void> {
  for (const item of items) {
    processItem(item);

    // Yield to the browser between items
    if (navigator.scheduling?.isInputPending?.()) {
      await scheduler.yield();
    }
  }
}
```

## CLS Prevention

Layout shifts happen when elements change size or position after the initial render.

- Always set `width` and `height` attributes on images and videos. This reserves space before the asset loads.
- Use CSS `aspect-ratio` for responsive containers that maintain proportions.
- Never inject content above existing visible content after initial render.
- Use `font-display: swap` with size-adjusted fallback fonts to minimize font swap shifts.
- Reserve space for dynamic content like ads, embeds, and lazy-loaded sections.

```html
<!-- Dimensions prevent layout shift -->
<img
  src="/product.webp"
  alt="Product photo"
  width="400"
  height="300"
  loading="lazy"
  decoding="async"
/>
```

## Code Splitting Strategy

Split code by route and by interaction. The initial load carries only what the first screen needs.

| Split boundary | When to apply |
|---------------|---------------|
| Route-based | Every route is a separate chunk. Loaded on navigation |
| Interaction-based | Modals, dropdowns, and heavy widgets loaded on user action |
| Vendor | Stable third-party code in a separate chunk for long-term caching |
| Feature flag | Code behind disabled flags excluded from the bundle |

```typescript
// Route-level splitting in React
const Dashboard = lazy(() => import("./pages/Dashboard"));

// Interaction-level splitting
async function openExportModal(): Promise<void> {
  const { ExportModal } = await import("./components/ExportModal");
  renderModal(ExportModal);
}
```

- Prefetch next-page chunks on link hover or viewport proximity.
- Set chunk size targets: no single chunk above 100KB compressed.
- Monitor chunk count. More than 50 chunks increases HTTP overhead, even with HTTP/2 multiplexing.

## Third-Party Script Management

Each third-party script is a liability. It runs on your domain with full access.

- Load with `async` or `defer`. Never render-blocking.
- Use `dns-prefetch` and `preconnect` for known third-party origins.
- Set a Content Security Policy that restricts script sources.
- Audit third-party scripts quarterly for size growth, performance regression, and security.
- Tag third-party resources with `crossorigin="anonymous"` to enable error reporting.

| Loading strategy | When to use |
|-----------------|-------------|
| `async` | Analytics, tracking, non-critical features |
| `defer` | Scripts that depend on DOM but are not critical |
| Dynamic import | Features triggered by user interaction |
| Web Worker | Heavy processing that must not block the main thread |

## Performance Monitoring

Track performance metrics continuously, not just during development.

| Metric | Source | Alert threshold |
|--------|--------|----------------|
| LCP p75 | RUM | Above 2.5s for 15 minutes |
| INP p75 | RUM | Above 200ms for 15 minutes |
| CLS p75 | RUM | Above 0.1 for 15 minutes |
| JS bundle size | Build | Above 80% of budget |
| Total page weight | Build | Above 80% of budget |
| Time to First Byte | RUM | Above 800ms p75 |
