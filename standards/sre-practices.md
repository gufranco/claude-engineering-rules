# SRE Practices

## Service Level Indicators

SLIs measure user experience with real data. Synthetic checks confirm the service is reachable but do not represent actual user behavior.

| SLI category | What to measure | Data source |
|-------------|----------------|-------------|
| Availability | Proportion of successful requests out of total | Load balancer logs, application metrics |
| Latency | Request duration at p50, p95, p99 | Application instrumentation, reverse proxy |
| Correctness | Proportion of responses that return the right answer | Application-level validation, checksums |
| Freshness | Age of data served to users | Timestamp comparison between source and serving layer |
| Throughput | Successful operations per second | Application metrics |

- Measure at the point closest to the user. A load balancer SLI is better than an application SLI. A client-side SLI is better than a load balancer SLI.
- Exclude health checks and internal traffic from SLI calculations. They inflate the numbers without reflecting user experience.
- Use request-based SLIs for synchronous services. Use event-based SLIs for async pipelines.

## Service Level Objectives

SLOs are operational targets that define "good enough." They are not aspirational goals. Set them based on what users actually need, not what the system can theoretically achieve.

| SLO property | Guidance |
|-------------|----------|
| Target | Set below 100%. A 99.99% SLO for an internal tool is a waste of engineering effort |
| Window | 28-day rolling window. Aligns with team cadences without calendar quirks |
| Measurement | Automated, continuous, from the SLI data source |
| Ownership | One team owns each SLO. No shared ownership across teams |

```
# Example SLO definition
Service: Checkout API
SLI: Proportion of POST /checkout requests completing in under 2 seconds with 2xx status
Target: 99.5% over 28-day rolling window
Data source: Load balancer access logs
Owner: Payments team
```

Every user-facing service must have at least one SLO covering availability and one covering latency. Internal services shared by multiple teams also need SLOs.

## Error Budgets

The error budget is `1 - SLO target`. A 99.5% SLO gives a 0.5% error budget over the measurement window.

With a 28-day window and 99.5% target:
- Total minutes: 40,320
- Error budget: 201.6 minutes of allowed downtime or degradation

The error budget is the currency that funds velocity. Deploying new features, running experiments, and performing maintenance all spend error budget. When the budget is exhausted, reliability work takes priority over feature work.

## Burn Rate Alerts

Alert on how fast the error budget is being consumed, not on instantaneous error rates. A brief spike that recovers is not the same as a sustained degradation.

| Burn rate | Meaning | Alert urgency | Budget consumed in 1 hour |
|-----------|---------|---------------|--------------------------|
| 1x | Normal consumption, budget lasts the full window | No alert | 0.15% |
| 2x | Budget exhausted in 14 days | Ticket, investigate within 24 hours | 0.30% |
| 6x | Budget exhausted in ~4.5 days | Page, investigate within 2 hours | 0.89% |
| 10x | Budget exhausted in ~2.8 days | Page immediately, active incident | 1.49% |

Use multi-window alerts to reduce false positives. A 6x burn rate sustained for 5 minutes is noise. A 6x burn rate sustained for 30 minutes is a real problem.

```
# Pseudo-alert definition
alert: HighErrorBudgetBurn
expr: |
  error_budget_burn_rate_1h > 6
  AND error_budget_burn_rate_6h > 3
severity: page
```

## Error Budget Policy

Document the error budget policy before it is needed. Negotiating rules during an incident is ineffective.

The policy must answer:

1. What happens when the budget is at 50%? Increase review rigor for changes.
2. What happens when the budget is at 25%? Freeze non-critical deployments.
3. What happens when the budget is exhausted? Full change freeze. Only reliability improvements, rollbacks, and incident fixes.
4. Who has authority to override the freeze? Name the role, not the person.
5. How is the budget replenished? Rolling window naturally replenishes as old errors age out.

Get sign-off from engineering leadership and product stakeholders before the first incident. A policy nobody agreed to will be ignored under pressure.

## Change Freeze Protocol

When the error budget is exhausted:

- No feature deployments until the budget recovers above 10%.
- Config changes require two approvals.
- All engineering effort shifts to reliability improvements.
- Toil reduction work is prioritized.
- The freeze is lifted when the rolling window shows the SLO target is met again.

## Postmortems

Conduct a blameless postmortem within 5 business days of any incident that consumed more than 10% of a service's error budget.

### Required sections

| Section | Content |
|---------|---------|
| Summary | One paragraph: what happened, impact, duration |
| Timeline | Chronological events with GMT timestamps |
| Impact | Users affected, error rate, revenue impact if applicable |
| Root cause | The actual cause, not the trigger |
| Contributing factors | Systemic issues that made the incident worse |
| What went well | Response actions that helped |
| Action items | Specific, assigned, with deadlines |

### Rules

- Blameless. Focus on systems and processes, not individuals.
- Action items must be tracked in the team's issue tracker, not just the postmortem doc.
- Review action item completion in a follow-up meeting within 30 days.
- Share postmortems broadly. Other teams learn from your incidents.
- Never use the postmortem to justify punitive action against individuals.

## SLO Coverage

| Service type | Required SLOs |
|-------------|---------------|
| User-facing API | Availability + latency |
| Background processor | Freshness + correctness |
| Data pipeline | Freshness + throughput |
| Internal platform service | Availability + latency |
| Third-party dependency | Track their SLA, set internal SLO below it |

Services without SLOs are services without accountability. If a service does not have an SLO, nobody knows when it is broken badly enough to act on.

## Toil Tracking

Toil is manual, repetitive, automatable work that scales with service size. Track it explicitly.

- Each team logs toil hours weekly.
- Target: less than 30% of a team's time on toil.
- If toil exceeds 30%, it becomes the top priority ahead of feature work.
- Automate the highest-frequency toil first, not the most annoying.
