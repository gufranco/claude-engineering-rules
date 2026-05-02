# Shared Agent Principles

This file is a reference fragment. Every agent in this directory follows these principles.

## Directory Conventions

The `agents/` directory contains both agent definitions and support files. Counts in documentation refer to **agents only**, excluding files prefixed with `_` (shared fragments) and `TEMPLATE.md` (boilerplate). To count agents: `ls agents/*.md | grep -vE "^_|TEMPLATE"`.

## Execution

- Do not spawn subagents. Complete this task using direct tool calls only.
- Verify every file path exists before including it in results.

## Scope Resolution

- When no scope is provided, default to files changed in the current git diff: `git diff --name-only HEAD`.
- If no diff exists, ask the orchestrator to specify files or directories.

## Output Rules

- Format findings as `file:line: description`. No raw file contents or full function bodies.
- Every finding must include a severity level: critical, high, medium, or low.
- Respect the per-agent maximum output entry count.
- When findings exceed the output limit, prioritize by severity, truncate at the limit, and state the number of omitted findings.

## Final Checklist

Before returning results:

- Every file path referenced was verified to exist.
- Output follows the exact format specified by the agent.
- No raw file contents or function bodies in the output.
- Findings are sorted by severity, highest first.
- The summary metric is accurate.
