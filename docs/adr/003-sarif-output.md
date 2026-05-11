# ADR-003: SARIF Output Format

**Status:** accepted
**Date:** 2026-05-09

## Context

GitHub Code Scanning, Semgrep, CodeQL, and most modern static-analysis tooling consume SARIF (Static Analysis Results Interchange Format) 2.1.0. The format is an OASIS standard with a published JSON schema. CI pipelines that aggregate findings across multiple tools expect SARIF as the lingua franca.

The mutation-method-blocker emits human-readable stderr by default. CI workflows that want to surface findings in the GitHub Security tab cannot consume that format directly. Without SARIF, every project that runs the hook in CI has to write a parser.

The SARIF schema URI is fixed: `https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json`. The format is verbose but stable. Validation tools exist (`sarif-tools validate`) that check conformance against the schema.

## Decision

Add SARIF 2.1.0 emission as an opt-in output mode. A new env var `MUTATION_METHOD_OUTPUT=sarif` switches the hook from human stderr to SARIF JSON on stdout. The default remains human stderr to preserve the developer experience for interactive use.

SARIF emission lives in `hooks/sarif_emitter.py`. The emitter accepts a list of `Finding` records and produces a SARIF document with:

| Field | Source |
|-------|--------|
| `version` | `2.1.0` (constant) |
| `$schema` | `https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json` |
| `runs[0].tool.driver.name` | `mutation-method-blocker` |
| `runs[0].tool.driver.version` | `__version__` from `hooks/mutation-method-blocker.py` |
| `runs[0].results[].ruleId` | Detector name (`array.push`, `object.assign`, etc.) |
| `runs[0].results[].level` | `error` for confidence 7-10, `warning` for 5-6, `note` for below 5 |
| `runs[0].results[].locations[]` | File path and line:column from the regex or AST match |
| `runs[0].results[].message.text` | The fix-hint produced by the detector |

CI workflows opt in by setting the env var. The findings appear in the GitHub Security tab via `actions/upload-sarif`.

## Alternatives Considered

### Stderr only

Pros: simple. One output format. Matches the existing developer experience.
Cons: cannot integrate with Code Scanning. Every CI consumer would need to write a parser. No path to aggregate mutation-blocker findings with other tool findings.

### SARIF only

Pros: tool-friendly. Single output format.
Cons: loses human-readable output. Interactive use becomes painful. Existing fixtures and tests assume stderr.

### Both via env var

Pros: flexible. Default stays human-friendly. CI workflows opt into SARIF without affecting interactive use.
Cons: two code paths to maintain. Tests must cover both.

## Consequences

### Positive

- Findings flow into GitHub Security tab without custom parsers.
- Aggregating across tools (mutation-blocker, eslint, semgrep) is a one-line CI step: collect every SARIF, upload once.
- The schema is stable. Format changes are versioned.
- Confidence scoring maps cleanly to SARIF `level` values.

### Negative

- Two output paths to test. Every detector must produce valid output in both modes.
- SARIF documents are verbose. A single finding can be 200+ bytes of JSON.
- The schema validation step adds a dependency on `jsonschema` (or equivalent) in the test suite. Already present.

### Risks

- SARIF schema may evolve to v2.2.0 or higher. The hook pins to v2.1.0; a future schema upgrade requires a coordinated change.
- GitHub Code Scanning may impose new constraints on SARIF documents (max size, max findings per run). The hook does not currently page findings.
- `actions/upload-sarif` rejects malformed documents. The test suite must catch schema violations before they reach CI.
