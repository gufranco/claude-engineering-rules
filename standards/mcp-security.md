# MCP Security

## Core Rule

MCP servers are attack surface. Each server has access to tools, data, and credentials. Scope them tightly, validate their output, and limit how many run concurrently.

## Server Scoping

Assign MCP servers to agents via the `mcpServers` frontmatter field. Never expose a database MCP server to a general-purpose agent. Never expose a production MCP server to any agent without explicit user approval.

```yaml
---
name: database-analyst
description: Analyze database schema and query performance
mcpServers:
  - dev-postgres
allowed-tools:
  - Read
  - Grep
  - mcp__dev-postgres__query
---
```

## Scoping Rules

| MCP Server Type | Who gets access | Who must never get access |
|----------------|----------------|--------------------------|
| Database, read-only | Database analysis agents | General-purpose agents, code generation agents |
| Database, read-write | Never expose directly | All agents. Use a service layer instead |
| File system | File exploration agents | Agents that do not need file access |
| API integrations | Domain-specific agents | Unrelated agents |
| Credentials or secrets | Never expose as MCP | All agents. Use env vars |

## Output Validation

MCP tool responses are external input. Validate the shape before using the data.

- Check that the response contains the expected fields.
- Check that field types match expectations: a number is a number, not a string.
- Handle missing fields gracefully. Never assume a field exists because the MCP server documentation says it will.
- Treat MCP output with the same suspicion as any external API response.

## Credential Isolation

MCP server credentials must come from environment variables, never from hardcoded values in configuration files.

```json
{
  "mcpServers": {
    "dev-postgres": {
      "command": "mcp-server-postgres",
      "env": {
        "DATABASE_URL": "${DEV_DATABASE_URL}"
      }
    }
  }
}
```

Never store database passwords, API keys, or tokens in MCP configuration files. Never commit MCP configuration files that contain credentials.

## Performance Limits

Limit active MCP servers to 5-6 concurrently. Each MCP server:

- Consumes a persistent process
- Adds latency to tool discovery
- Increases memory usage
- Adds entries to the tool namespace, which can cause confusion when many tools share similar names

Start only the servers needed for the current task. Stop servers when the task is done.

## Tool Search for On-Demand Discovery

Use the Tool Search mechanism to discover MCP tools instead of loading all servers upfront. This keeps the active tool count low and reduces namespace pollution.

```
# Discover available database tools without starting all MCP servers
ToolSearch: "database query"
```

## Rules

- Every MCP server must have a documented purpose. No "just in case" servers.
- Review MCP server permissions quarterly. Remove servers that are no longer used.
- Never run MCP servers with write access to production databases.
- Log all MCP tool invocations for audit purposes.
- When an MCP server fails, the agent must handle the failure gracefully, not retry indefinitely.
- Test MCP server connectivity before relying on it in a task. A stale connection wastes time.

## OWASP LLM Top 10 (2025 Edition)

The OWASP Top 10 for LLM Applications was revised in 2025 with new categories that map directly to how MCP servers and agentic systems fail in production. Treat these as a checklist when adding a new MCP server, designing a new agent, or wiring an LLM into an external system.

| OWASP ID | Category | MCP and agent expression |
|----------|----------|--------------------------|
| LLM01 | Prompt Injection | Treat every MCP tool response as untrusted user input. Validate and sanitize before the model sees it. Strip executable markup. Do not blindly forward tool output back into prompts |
| LLM02 | Sensitive Information Disclosure | Scope MCP servers per the table above. Never expose secrets, PII, or production data through a general-purpose MCP server |
| LLM03 | Supply Chain | Pin MCP server versions. Verify provenance of every third-party MCP server before installing. Review the source when the server runs in a privileged context |
| LLM04 | Data and Model Poisoning | When MCP servers feed data into vector databases or training pipelines, validate the ingest. A poisoned document in a RAG store affects every later query |
| LLM05 | Improper Output Handling | Validate the shape of every MCP tool response before acting on it. The "Output Validation" section above covers the baseline; add domain-specific schema checks for sensitive operations |
| LLM06 | Excessive Agency | Default to read-only MCP servers. Require explicit user confirmation for any tool that mutates external state. The Scoping Rules table above is the first line of defense |
| LLM07 | System Prompt Leakage (NEW in 2025) | System prompts and agent instructions must not contain secrets, credentials, or operational logic. Anything a leaked prompt would compromise belongs in a separate, gated tool call, not in the prompt |
| LLM08 | Vector and Embedding Weaknesses (NEW in 2025) | When MCP servers write to or read from vector databases, validate the embedding source, scope the search by tenant or user, and rate-limit per-source ingestion. Stored prompt injection lives here |
| LLM09 | Misinformation | Cite sources for MCP tool output that flows into user-visible responses. Track provenance through the agent pipeline so the user can verify |
| LLM10 | Unbounded Consumption | Cap the number of MCP tool calls per agent turn. Cap token usage per tool response. A runaway agent that loops on a slow tool can consume the entire context window |

For agentic workflows that go beyond single MCP tool calls, also reference the separate OWASP Agentic AI Top 10 published in late 2025. Its emphasis is multi-step plans, tool-use chains, and inter-agent communication, which extend beyond what this MCP-focused file covers.

The LLM Output Trust Boundary section in [`code-style.md`](../rules/code-style.md) covers the application-side hardening: validate format and shape, sanitize before vector-DB inserts, allowlist URLs, verify tool-output schemas, never store raw LLM output in user-visible fields.
