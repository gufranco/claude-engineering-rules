# Hook Authoring

## Performance Budget

Hooks must complete in under 500ms. Claude Code executes hooks synchronously in the tool pipeline. A slow hook blocks every tool call. Never make network calls, database queries, or any I/O that depends on external services.

## Hook Types

| Type | Trigger | Use case |
|------|---------|----------|
| `PreToolUse` | Before a tool runs | Block dangerous commands, validate inputs |
| `PostToolUse` | After a tool runs | Scan output for secrets, validate results |
| `Notification` | On specific events | Log actions, send alerts |

## Exit Codes

| Code | Meaning | Behavior |
|------|---------|----------|
| 0 | Allow | Tool call proceeds normally |
| 2 | Block | Tool call is rejected with the hook's stderr as the reason |

Any other exit code is treated as a hook error and logged but does not block the tool call.

## Stdin Format

Hooks receive tool input as a JSON object on stdin. The shape depends on the hook type.

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /tmp/build"
  }
}
```

Always parse stdin as JSON. Never assume a specific field exists without checking. A missing or malformed field must not crash the hook.

## Graceful Handling of Malformed Input

```bash
# Read stdin, default to empty object if missing
input=$(cat 2>/dev/null || echo '{}')

# Parse with jq, default to empty string if field is absent
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# If no command found, allow (do not block on missing data)
if [ -z "$command" ]; then
  exit 0
fi
```

## Pattern Matching

Use `grep -qiE` for pattern matching against command strings. Keep patterns simple and anchored.

```bash
# Match destructive git commands
if echo "$command" | grep -qiE '(git\s+push\s+--force|git\s+reset\s+--hard)'; then
  echo "Blocked: destructive git operation" >&2
  exit 2
fi
```

## Testing

Test hooks with JSON fixture files. Create a `tests/` directory alongside the hook with representative inputs.

```bash
# Test a blocking case
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | ./dangerous-command-blocker.sh
# Expected: exit code 2

# Test an allow case
echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | ./dangerous-command-blocker.sh
# Expected: exit code 0

# Test malformed input
echo 'not json' | ./dangerous-command-blocker.sh
# Expected: exit code 0 (graceful fallthrough)
```

## Rules

- Never use `set -e` in hooks. A failed grep match returns exit code 1, which would terminate the hook and produce an unexpected exit code.
- Always write to stderr for block messages, never stdout.
- Keep pattern lists in arrays or external files for maintainability.
- Log blocked actions with enough context to debug false positives: the matched pattern and the original command.
- Test every new pattern against both positive matches and negative matches before deploying.
- Hooks must work without external dependencies beyond standard Unix tools: bash, grep, jq, sed, awk.
- When matching commands, account for path prefixes, extra whitespace, and quoted arguments.
