# ADR-005: Confidence Scoring for Findings

**Status:** accepted
**Date:** 2026-05-09

## Context

The project's verification rule mandates confidence scoring on findings produced by analytical tools. Scores under 5 are suppressed, 5-6 are displayed with a caveat, and 7-10 are surfaced normally. The mutation-method-blocker is an analytical tool: it produces findings against source code that may be a true mutation, a false positive on a string literal, or a context that warrants a softer treatment.

Without confidence scoring, every finding looks identical. A regex match inside a known framework callback (XState `actions`, Pinia `mutations`) carries the same weight as an AST-confirmed mutation in production code. Users learn to suppress aggressively, eroding the rule.

Confidence is a multi-signal computation. The detector identity, AST confirmation, receiver-type knowledge, and file-path context each shift the score. Scoring decisions need to be deterministic, auditable, and aligned with the v1-to-v2 migration so that block messages can carry the score without breaking schema consumers.

## Decision

Every finding carries a 1-10 confidence score computed from a fixed signal set. The score is attached to the v2 envelope (ADR-002) and the SARIF `level` field (ADR-003). Initial scoring lives in `hooks/mutation_confidence.py`.

Signals and weights:

| Signal | Weight |
|--------|--------|
| Detector type matches the canonical pattern exactly | +3 |
| AST-confirmed (not just regex) | +2 |
| Receiver type confirmed (not heuristic) | +2 |
| File path inside auto-allowed directory but pattern still matches | -3 |
| Detected inside a known framework callback (XState `actions`, etc.) | -2 |

Score interpretation:

| Range | Action |
|-------|--------|
| 7-10 | Block. Standard message. SARIF `level: error` |
| 5-6 | Block with a "confidence: medium" annotation. SARIF `level: warning` |
| 1-4 | Warning only, not a block. SARIF `level: note`. Logged in audit telemetry |

Scores are logged to the audit pipeline per finding so trends can be analyzed. A spike in low-confidence findings indicates either a corpus gap (new pattern needs an allowlist) or a detector regression (false positives have crept in).

## Alternatives Considered

### Binary block-or-allow

Pros: simplest. Matches the v1 behavior. No scoring code to maintain.
Cons: every finding looks identical. The rule cannot communicate "this is probably wrong but I am not sure". Users adapt by suppressing aggressively or disabling the hook.

### Three-level (high, medium, low) without numeric scoring

Pros: simpler than 1-10.
Cons: aggregating signals into three buckets loses precision. The scoring rule "7-10 is block, 5-6 is warning" maps cleanly to a score; a bucket model needs an explicit threshold per signal combination, which is harder to audit.

### External scorer (call out to a service or LLM)

Pros: scoring logic centralized across multiple hooks.
Cons: adds a network call to the hot path. Violates the performance budget (ADR-004). Privacy: sending source excerpts to a remote scorer leaks code.

## Consequences

### Positive

- Aligns the hook with the project-wide verification rule.
- High-confidence blocks get more weight; low-confidence findings can be triaged before they become blocks.
- The audit log produces telemetry that can drive corpus and detector improvements.
- SARIF `level` values map directly, no custom encoding needed.

### Negative

- Every detector must contribute confidence inputs (AST confirmation, receiver type, etc.). Detectors that lack the inputs default to a baseline score.
- Score thresholds are arbitrary. A 7-versus-6 boundary means edge cases swing between block and warning. Documented and tested.
- Audit log volume grows by a per-finding score field. Negligible storage cost.

### Risks

- Signals may correlate. AST confirmation and receiver-type knowledge frequently co-occur; the additive weighting may overstate confidence in those cases. Calibration tests on the corpus catch this.
- Auto-allowed directory negative weight may suppress real findings when a project mis-categorizes a file as "hot path" or "state library". Corpus negatives cover this.
- Confidence depends on detector quality. A detector with high false-positive rate will produce low-confidence findings frequently; the right fix is the detector, not the threshold.
