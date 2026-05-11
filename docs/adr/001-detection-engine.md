# ADR-001: Detection Engine for Mutation Method Blocker

**Status:** accepted
**Date:** 2026-05-09

## Context

The mutation-method-blocker hook started as a regex-only scanner. Regex catches the obvious cases but produces false positives when the mutation token appears inside string literals, JSX text, template expressions, or comments. Expanding the surface from a handful of array methods to 50+ patterns across 9 categories would push the regex strategy past its practical limit. The team needed a path that keeps the floor working on every machine while admitting AST-level accuracy where it is available.

The decision is not abstract. Detection accuracy translates to false-positive blocks against legitimate code paths (Immer drafts, Pinia stores, framework navigation). Each false positive trains the user to suppress, which erodes the rule.

## Decision

Hybrid detection. Regex stays the floor: every detector first runs against the source text, and the hook ships with no native dependencies. When `ast-grep` is on PATH, the hook escalates ambiguous matches to AST analysis. The AST step eliminates string-literal false positives, recognizes nested call expressions for state-management allowlists, and feeds receiver-type information into the confidence scorer.

The hook detects `ast-grep` once per process at module load. The decision is cached so subsequent detections reuse the result. AST escalation is opt-out via `MUTATION_METHOD_AST=0` for users who want pure regex.

## Alternatives Considered

### A. Stay regex-only

Pros: zero dependencies, fastest path, current pattern.
Cons: false positives in strings, JSX text, template literals, and comments. The allowlist becomes unwieldy when 50+ patterns each need a string-aware regex.

### B. Switch to tree-sitter via Python bindings

Pros: full AST, ~20ms warm parse, stays in Python.
Cons: native wheels are not always available. `tree_sitter_languages` install fails on niche architectures: musl, Alpine, and older macOS arm64 Pythons.

### C. Switch to Babel or typescript-estree via Node sidecar

Pros: most accurate parser for TypeScript.
Cons: requires Node on PATH. Spawning Node adds 80-150ms per invocation. The user may not have Node installed in every environment where Claude Code runs.

## Consequences

### Positive

- Hook works on any system without dependencies.
- Accuracy approaches AST-grade when `ast-grep` is available.
- Confidence scoring can use AST confirmation as a signal.
- False-positive rate on the corpus drops to zero with AST on, while staying under 200ms p95.

### Negative

- Two code paths to maintain: regex and AST.
- Test matrix doubles in size: every detector has a "regex only" and "AST escalated" variant.
- The cached `ast-grep` decision is per-process; long-lived test runners may not pick up a newly installed `ast-grep` without restart.

### Risks

- `ast-grep` query syntax may diverge from upstream across versions. The hook pins a minimum version and degrades to regex when the schema does not match.
- AST escalation is bypassable by setting `MUTATION_METHOD_AST=0`. Documented as a debugging escape, not a recommended runtime configuration.
- Regex baseline must remain conservative. A regex that flags too aggressively while AST is off becomes the user's experience on systems without `ast-grep`.
