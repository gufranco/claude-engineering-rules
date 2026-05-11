# ADR-002: Hook v2 Envelope Migration

**Status:** accepted
**Date:** 2026-05-09

## Context

Claude Code introduced a v2 hook protocol that replaces the v1 stderr + `sys.exit(2)` blocking convention with a JSON envelope on stdout. The envelope carries `permissionDecision`, `permissionDecisionReason`, `updatedInput`, and `additionalContext` fields. v2 unlocks ask-and-defer flows, structured fix suggestions, and input modification, none of which the v1 channel can express.

The mutation-method-blocker is one of the highest-traffic hooks in the suite. Every Write and Edit on a TS or JS file invokes it. A migration here sets the expected pattern for sibling hooks (`as-any-blocker`, `console-log-blocker`, `redis-atomicity`, etc.).

The runtime advertises its protocol version via `CLAUDE_HOOK_API_VERSION`. Older Claude Code releases do not set the variable. Log scrapers in CI parse v1 stderr lines and would break if stderr fell silent.

## Decision

Migrate now via a shared shim at `scripts/hook_io.py`. The shim exposes `block(reason)`, `allow()`, `modify_input(diff)`, `ask(prompt)`, and `defer(reason)`. Each call writes the v2 JSON envelope to stdout AND emits the legacy v1 stderr line. v1 emission is preserved indefinitely per the backward compatibility policy.

Detection logic reads `CLAUDE_HOOK_API_VERSION`:

| Value | Behavior |
|-------|----------|
| Unset or empty | v1 stderr is the primary channel. v2 envelope still written so v2-aware tooling can consume it |
| `1` | Same as unset |
| `2` or higher | v2 envelope is the primary channel. v1 stderr remains as a side channel for log scrapers |
| Anything else | Treat as v1 (degrade gracefully) |

The dual emit is the contract. A regression that suppresses v1 stderr is a breaking change and must bump the major version.

## Alternatives Considered

### Stay on v1

Pros: zero migration work. No risk of breaking the existing channel.
Cons: misses every v2 capability. Future detector evolution (ask-on-medium-confidence, modify-input fix application) would have no path forward.

### Migrate now via shim

Pros: single source of truth for output formatting. v2 capabilities available to every hook through one import. Tests can assert against a typed envelope.
Cons: touches every hook that calls `block()`. The shim adds a new failure mode (shim bug crashes every hook).

### Dual-emit v1 and v2 with no shim

Pros: backward compat without coordinating a shim.
Cons: ambiguous decision channel when v1 stderr and v2 stdout disagree. Each hook reimplements envelope construction, drifting over time.

## Consequences

### Positive

- All hooks share one output formatter.
- v2 envelope is testable: stdout JSON parses against the published schema.
- Migration to ask/modify flows requires only shim updates, not hook-by-hook rewrites.
- Confidence scoring (ADR-005) attaches to v2 envelopes natively.

### Negative

- The shim is a single point of failure. A bug in `hook_io.py` affects every hook.
- v1 stderr is preserved indefinitely. Future cleanup of legacy code paths cannot remove it without a major-version migration.
- Test surface grows: every hook needs a v1-stderr regression test AND a v2-envelope schema test.

### Risks

- The `CLAUDE_HOOK_API_VERSION` env var may not be reliable across Claude Code releases. The hook degrades to v1 on any non-`2` value.
- Downstream tooling that scrapes v1 stderr may break if a future Claude Code release stops passing stderr through. Documented as a contract dependency.
- Schema drift in the v2 envelope across Claude Code minor versions could silently invalidate existing fixtures. Schema validation in tests catches this.
