# Trust Patterns Fixtures

Synthetic fixtures used to verify the `/audit trust` scan behaves as documented in [`../../skills/audit/trust-patterns.md`](../../skills/audit/trust-patterns.md).

## Directory layout

- [`verdicts/`](verdicts): full mini-project fixtures, one per verdict tier, used to verify end-to-end behavior.

Each fixture directory documents its expected behavior in its own `FIXTURE.md`; the source files carry no comments.

## How to run

The trust scan is markdown-driven and interpreted by the assistant. The verifier is manual: run `/audit trust <fixture-path>` and compare the resulting verdict and finding count against the expectation table below.

## Expected verdicts

| Path | Expected verdict | Expected severity of worst finding |
|------|-----------------|------------------------------------|
| [`verdicts/safe/`](verdicts/safe) | SAFE | None or LOW |
| [`verdicts/suspicious/`](verdicts/suspicious) | SUSPICIOUS | MEDIUM |
| [`verdicts/high-risk/`](verdicts/high-risk) | HIGH-RISK | HIGH |
| [`verdicts/malicious/`](verdicts/malicious) | MALICIOUS | CRITICAL |

## Adding new fixtures

Each fixture lives in its own subdirectory under [`verdicts/`](verdicts). Add a `FIXTURE.md` inside each directory documenting:

1. Which pattern from [`../../skills/audit/trust-patterns.md`](../../skills/audit/trust-patterns.md) the fixture exercises.
2. The expected per-file severity and the expected verdict.
3. A one-line rationale for why this fixture exists.
