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

## Audit Emission (MANDATORY for blocking hooks)

Every hook that can block (exit 2) or accept a bypass env var must emit a structured event to `~/.claude/logs/hooks.log` via `scripts/audit_log.py`. This feeds the `/retro --hooks` workflow that proposes upstream fixes (rules, skills, CLAUDE.md) so the model self-corrects before the hook fires next time. Hooks are the last line of defense, not the only one.

### What to emit

Required fields (auto-filled by the helper when omitted): `ts`, `session_id`, `cwd`, `hook`, `decision`, `tool`, `reason`, `command_excerpt`. Optional: `bypass_env`, `level`.

| Decision | When |
|---------|------|
| `block` | Before every `exit 2` / `sys.exit(2)` |
| `bypass` | When a bypass env var is honored and the hook returns 0 |
| `allow` | Optional; do not emit on the happy path. Reserved for hooks that want to record a non-blocking observation |

### Python hooks

```python
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit
except Exception:
    def _audit(**_fields): return None

# before sys.exit(2)
_audit(hook="my-hook", decision="block", tool=tool,
       reason="short stable label", command_excerpt=command[:240])
sys.exit(2)
```

The import block must be defensive: if the module fails to load, the hook keeps blocking. Audit emission is best-effort and never the reason a hook fails.

### Shell hooks

Call the Python CLI form. Wrap in `|| true` so logging failures never alter the exit code.

```bash
python3 "$HOME/.claude/scripts/audit_log.py" --hook my-hook \
    --decision block --tool Bash --reason "short stable label" \
    --command "${COMMAND:-}" 2>/dev/null || true
exit 2
```

Define a `_audit_block` helper at the top of the file when the hook has multiple `exit 2` sites.

### Reason field discipline

`reason` is the cluster key in `/retro --hooks`. Keep it stable, short, and machine-friendly: lowercase, hyphen or space separated, under 80 chars. Do not interpolate user input into the reason; that goes in `command_excerpt`. A reason that varies per call defeats clustering.

| Good | Bad |
|------|-----|
| `subject not conventional format` | `commit message "fix stuff" rejected` |
| `aws configure set without --profile` | `aws configure set region=us-east-1 had no profile flag` |
| `private key write blocked` | `cannot write /Users/x/.ssh/id_rsa` |

Secrets in `command_excerpt` are redacted on write by `audit_log.py`. Treat that as defense in depth, not an excuse to log raw credentials.

## Rules

- Never use `set -e` in hooks. A failed grep match returns exit code 1, which would terminate the hook and produce an unexpected exit code.
- Always write to stderr for block messages, never stdout.
- Keep pattern lists in arrays or external files for maintainability.
- Log blocked actions with enough context to debug false positives: the matched pattern and the original command.
- Test every new pattern against both positive matches and negative matches before deploying.
- Hooks must work without external dependencies beyond standard Unix tools: bash, grep, jq, sed, awk.
- When matching commands, account for path prefixes, extra whitespace, and quoted arguments.
- Every blocking hook must emit a structured audit event before `exit 2`. See "Audit Emission" above.
