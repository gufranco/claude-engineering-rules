# Normative Keywords

Every normative statement uses one BCP 14 keyword. Lowercase is the default; uppercase only for security, correctness, data integrity, irreversibility, or verbatim citation.

| Keyword | Meaning |
|---|---|
| must, required, shall, always | Absolute requirement |
| must not, shall not, never | Absolute prohibition |
| should, recommended | Default with valid deviations |
| should not | Acceptable only in specific cases |
| may, optional | Truly optional |

One keyword per statement, so never `must always`.

Full rule: [`standards/normative-keywords.md`](../standards/normative-keywords.md). Read it before writing a rule.

## Enforcement

Enforced by: [`hooks/normative-keyword-discipline.py`](../hooks/normative-keyword-discipline.py).
