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
