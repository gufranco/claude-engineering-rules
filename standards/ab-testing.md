# A/B Testing

## When to A/B Test

A/B test when: the change has measurable business impact, the correct choice is not obvious from first principles, and you have enough traffic to reach statistical significance within a reasonable timeframe.

Do not A/B test when: the change is a bug fix, a compliance requirement, a performance improvement with no UX trade-off, or traffic is too low for significance within 2 weeks.

## Experiment Design

Before writing code, define:

| Element | What to specify |
|---------|----------------|
| Hypothesis | "Changing X will improve metric Y by Z%" |
| Primary metric | One metric that determines success. Not two, not three. One. |
| Guardrail metrics | Metrics that must not degrade (revenue, error rate, latency) |
| Sample size | Calculate using power analysis before starting |
| Duration | Minimum runtime to account for weekly cycles (at least 1 full week) |
| Targeting | Which users see the experiment (all, segment, percentage) |
| Assignment unit | User, session, or device. Must be consistent for the experiment duration |

## Statistical Rigor

- **Power analysis**: calculate the required sample size before starting. Running until you see a result is p-hacking
- **Significance threshold**: p < 0.05 is conventional. For high-stakes decisions, use p < 0.01
- **Minimum detectable effect (MDE)**: the smallest change worth detecting. If your MDE is 1% but your traffic only supports detecting 5%, the experiment is underpowered
- **One primary metric**: testing multiple primary metrics inflates false positive rate. Use Bonferroni correction if you must test multiple
- **No peeking**: do not stop the experiment early because the result "looks significant". Use sequential testing methods (always-valid p-values) if early stopping is a business requirement
- **Run for full weeks**: user behavior varies by day of week. A Monday-to-Thursday test misses weekend patterns

## Assignment and Randomization

- Hash the assignment unit (user ID) with the experiment ID to produce a deterministic, reproducible assignment
- The same user must see the same variant for the entire experiment duration. Re-randomization biases results
- Verify balance: control and treatment groups must have similar distributions on key covariates (new vs returning users, geography, device)
- Use holdout groups for long-term impact measurement. A small percentage of users never see any experiment

## Implementation

- Feature flags control variant assignment. See `standards/feature-flags.md` for flag lifecycle
- Log every exposure event: user ID, experiment ID, variant, timestamp. Without exposure logging, you cannot analyze results
- Separate experiment configuration from code. Adding or removing an experiment must not require a deploy
- Support mutual exclusion: some experiments cannot run simultaneously (two checkout flow changes). Use experiment layers or namespaces

## Analysis

- **Intent-to-treat**: analyze all assigned users, not just those who "completed" the flow. Excluding non-completers biases results
- **Novelty and primacy effects**: new features get more attention initially. Wait for the novelty to wear off (7-14 days minimum)
- **Segmentation**: break results by key segments (mobile vs desktop, new vs returning). An overall flat result may hide a strong positive in one segment and a strong negative in another
- **Confidence intervals**: report the range, not just the point estimate. "Conversion increased by 2.1% (95% CI: 0.8% to 3.4%)" is more useful than "p = 0.03"

## Multivariate Testing

When testing multiple variables simultaneously (headline + image + CTA):

- Full factorial design (all combinations) requires exponentially more traffic. Use only with high-traffic pages
- Fractional factorial or Taguchi designs test a subset of combinations to identify main effects with less traffic
- Interaction effects (headline A works better with image B) require full factorial to detect

## Post-Experiment

- Document the result: hypothesis, sample size, duration, primary metric result, guardrail metrics, decision
- Ship the winning variant. Remove the losing variant code and the experiment flag. Dead experiment code is technical debt
- If the result is inconclusive, decide: extend the experiment, accept the null result, or redesign
- Feed learnings back into the next experiment. A/B testing is iterative

## Related Standards

- `standards/feature-flags.md`: Feature Flags
- `standards/observability.md`: Observability
