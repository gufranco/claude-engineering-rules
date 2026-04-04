# Dashboard Design

## Purpose-Driven Dashboards

Every dashboard must answer a specific question for a specific audience. A dashboard that answers "everything" answers nothing.

| Dashboard type | Audience | Refresh rate | Key question |
|---------------|----------|-------------|--------------|
| Operational | On-call engineers | Real-time (< 30s) | Is the system healthy right now? |
| Analytical | Product/engineering leads | Hourly to daily | How is the system performing over time? |
| Executive | Leadership | Daily to weekly | Are we meeting business goals? |
| Debugging | Engineers during incidents | Real-time | What is broken and where? |

## Layout Principles

- **Most important metric top-left.** Users scan dashboards in an F-pattern: top-left, across the top, then down the left side
- **Maximum 7 panels per row.** More than 7 creates visual noise. Group related metrics in rows
- **Consistent time range.** All panels on a dashboard must share the same time selector. A dashboard where one panel shows 24h and another shows 7d is misleading
- **Progressive disclosure.** Summary at the top, detail below. Link to deeper dashboards, not more panels

## Metric Grouping

Group metrics by the question they answer, not by the source system.

| Group | Metrics | Why together |
|-------|---------|-------------|
| Request flow | Request rate, error rate, latency (p50, p95, p99) | The RED method: Rate, Errors, Duration. Every service dashboard starts here |
| Resource usage | CPU, memory, disk, network | Saturation indicators. Correlate with request flow to find bottlenecks |
| Business metrics | Signups, conversions, revenue | The metrics that justify the system's existence |
| Dependencies | Upstream latency, downstream error rates | External factors affecting your service |

## SLO Visualization

Display SLOs as burn-rate alerts, not raw uptime percentages.

- **Error budget remaining**: show as a gauge or single-stat. "82% of monthly error budget remaining" is actionable. "99.94% uptime" is not
- **Burn rate**: how fast the error budget is being consumed. A 10x burn rate means the monthly budget will be exhausted in 3 days
- **Budget timeline**: a line chart showing error budget consumption over the SLO window. A steep downward slope triggers investigation

## Chart Selection

| Data type | Chart | Avoid |
|-----------|-------|-------|
| Single current value | Stat panel with sparkline | Gauge (hard to read precise values) |
| Value over time | Line chart (time series) | Bar chart (obscures trends) |
| Rate of change | Line chart with derivative transform | Raw counters (always go up, hide rate changes) |
| Distribution | Heatmap or histogram | Averages (hide bimodal distributions) |
| Categorical comparison | Horizontal bar chart | Pie chart (hard to compare similar values) |
| Correlation | Scatter plot | Two separate line charts (correlation not visible) |
| Status/health | Status grid (green/yellow/red) | Single aggregate status (hides partial failures) |

## Alert Integration

- Every panel that can trigger an alert must show the alert threshold as a horizontal line or shaded region
- Alert state (firing, pending, OK) must be visible on the dashboard without navigating elsewhere
- Link from alert notifications directly to the relevant dashboard with the time range pre-set to the alert window

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|-------------|---------|-----|
| Wall of graphs | Too many panels with no hierarchy | Group by question, use rows, add headers |
| Pie charts for time series | Cannot show trends | Use line charts for anything over time |
| Average-only latency | Hides tail latency problems | Always show p50, p95, p99 |
| Raw counter display | Numbers always go up, no useful signal | Use rate() or irate() to show per-second changes |
| No baseline | Cannot tell if current values are normal | Add week-over-week comparison or static baseline annotation |
| Dashboard sprawl | Hundreds of dashboards, nobody knows which to use | Curate a home dashboard per team. Archive unused dashboards |

## Related Standards

- `standards/observability.md`: Observability
- `standards/sre-practices.md`: SRE Practices
