---
name: <agent-name>
description: <One line. Used for routing: be specific about WHEN this agent activates and WHAT it returns.>
tools:
  - Read
  - Grep
  - Glob
model: <haiku for fast/simple, sonnet for analysis, opus for complex reasoning>
color: <blue | green | orange | red | yellow | purple | cyan — optional, for visual identification>
memory: <path to JSONL file for cross-session memory — optional, for agents that track false positives or learned patterns>
mcpServers: <list of MCP server names this agent is permitted to use — optional, omit to inherit all>
  - <server-name>
---

<One paragraph: who this agent is and what it does. State the single responsibility clearly.>

Do not spawn subagents. Complete this task using direct tool calls only.

## Constraints

- <What the agent must NOT do. 3-5 items.>
- Do not return raw file contents or full function bodies
- Do not modify any files unless explicitly part of the process

## Process

1. <First step>
2. <Second step>
3. <Continue with numbered steps>

## Output Contract

Return results in this exact format:

```
## <Title>: <summary metric>

### <Section per finding or category>
- `path/to/file.ts:42` - <one-line description>
```

Maximum <N> entries. If no findings, state "<No issues found>" with a brief rationale of what was checked.

## Scenarios

**No scope provided:**
Run against all files changed in the current git diff. If no diff exists, ask the orchestrator to specify files.

**Findings exceed the output limit:**
Prioritize by severity. Truncate at the limit. State how many findings were omitted.

**<Domain-specific ambiguous situation>:**
<What to do.>

## Final Checklist

Before returning results:

- [ ] Every file path referenced was verified to exist
- [ ] Output follows the exact format specified above
- [ ] No raw file contents or function bodies in the output
- [ ] Findings are sorted by priority or severity
- [ ] The summary metric is accurate
