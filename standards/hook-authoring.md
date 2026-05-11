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
| 1 | Ask | Hook stderr is forwarded to the model so it can revise the call |
| 2 | Block | Tool call is rejected with the hook's stderr as the reason |

Any other exit code is treated as a hook error and logged but does not block the tool call.

## Contract Versions

Two hook contracts coexist. Pick the one that matches the hook's job. See `decisions.md` D2 for the migration policy.

| Contract | Output | Capabilities | Use when |
|----------|--------|-------------|---------|
| v1 (legacy) | stderr + exit code | Block (`exit 2`), allow (`exit 0`) | Pure block-only hooks. The tool call either runs as-is or is rejected. No rewriting, no in-band feedback |
| v2 (modern) | JSON envelope on stdout, exit code 0 | Modify input, ask, defer, post-tool context | The hook needs to rewrite the input (auto-fix), suggest a fix the model should incorporate (`PostToolUse` `additionalContext`), or ask the model to revise the call without hard-blocking |

v2 is additive. Claude Code accepts both. Migrate hooks where v2 unlocks new behavior; leave the rest on v1.

### v2 Envelope Shapes

```jsonc
// PreToolUse: rewrite the input the tool will receive
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "modifiedInput": { "command": "git commit -m 'feat: ...'" }
  }
}

// PostToolUse: feed extra context back to the model
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Suggested by-copy replacement: [...arr, item]"
  }
}
```

### Migration Targets (per D2)

| Hook | Why migrate | New capability |
|------|------------|----------------|
| `conventional-commits.sh` | Rewrite a malformed commit subject in place | `modifiedInput` |
| `secret-scanner.py` | Redact detected secrets instead of just blocking | `modifiedInput` |
| `banned-prose-chars.py` | Auto-strip em-dashes from non-source payloads | `modifiedInput` |
| `prisma-schema-sync.py` | Suggest the schema patch via `additionalContext` | `additionalContext` |
| `mutation-method-blocker.py` | Suggest the by-copy replacement via `additionalContext` | `additionalContext` |

All other hooks stay on v1. Block-only behavior does not benefit from v2.

### Shared Helper: `scripts/hook_io.py`

Every Python hook can import the shim and stop owning the contract details:

```python
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
from hook_io import allow, ask, block, defer, modify_input, read_input

payload = read_input()
if not payload.tool_input.get("command"):
    sys.exit(allow())

if "rm -rf /" in payload.tool_input["command"]:
    sys.exit(block(
        "Refusing to run rm -rf /",
        audit_payload={"hook": "demo", "decision": "block", "reason": "rm-rf-root"},
    ))

sys.exit(allow())
```

The helper functions return integers, never raise on serialization errors, and fall back to `allow()` when v2 emission fails. Adopting them is incremental: replace one `sys.exit(2)` call site at a time.

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

## SARIF Output Mode

Static-analysis-style hooks (`mutation-method-blocker`, `as-any-blocker`, `console-log-blocker`) can opt into a second emission channel that publishes findings in OASIS SARIF 2.1.0. CI consumers ingest the SARIF document instead of grepping stderr.

### Contract

- Activated by `MUTATION_METHOD_OUTPUT=sarif` (or the hook's own `*_OUTPUT` env var).
- SARIF JSON goes to `stdout`. Legacy block message stays on `stderr`.
- Empty input still emits a valid envelope with `runs[0].results == []` so downstream uploaders never see a malformed file.

### Required fields

| Field | Purpose |
|-------|---------|
| `$schema`, `version` | Pin to `https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json` and `2.1.0` |
| `runs[].tool.driver.name` and `version` | Stable tool identity; used by GitHub code scanning to deduplicate runs |
| `runs[].tool.driver.rules[].id` | Stable rule code (`MMB001`, `MMB006`, etc.). Lookup table lives in `hooks/mutation_fix_suggestions.json` |
| `runs[].tool.driver.rules[].helpUri` | Link to the rule documentation |
| `runs[].tool.driver.rules[].defaultConfiguration.level` | `error` / `warning` / `note` derived from match confidence |
| `runs[].tool.driver.rules[].properties.tags` | Always include `mutation`, `immutability`, plus the detector category |
| `runs[].results[].partialFingerprints.primaryLocationLineHash` | SHA-256 of `file:line:detector:line_text`. Lets GitHub code scanning deduplicate the same finding across runs even when surrounding lines change |
| `runs[].columnKind` | `utf16CodeUnits` for editor-friendly column rendering |

### Batch mode

`MUTATION_METHOD_BATCH_MODE=1` switches the hook from a Claude Code `tool_input` payload to a list of file paths. Paths come from positional argv (pre-commit) or stdin (CI shell). Each file is scanned as if it were a Write payload (`is_full_file=True`), so full-file detectors like `let`-could-be-`const` still fire.

`MUTATION_METHOD_FAIL_THRESHOLD` controls the exit code in batch mode:

| Value | Exits non-zero when... |
|-------|------------------------|
| `error` (default) | At least one match has confidence ≥ 5 |
| `warning` | At least one match has confidence ≥ 3 |
| `note` | Any match exists |
| `none` | Never. Always exits 0 (advisory mode) |

### Implementation reference

The reference implementation is `hooks/sarif_emitter.py`. Reuse it for any hook that wants SARIF output: pass a list of `Finding(file_path, match)` records to `emit_sarif()` and write the result to stdout.

## Security Stance

Blocking hooks run with the same trust as the local user, on local input, with no network exposure. They are advisory: a determined attacker who controls the agent or the local shell can bypass them. The defenses below raise the bar against accidental damage from agent hallucination and trivial supply-chain attacks, not against a motivated adversary.

### Tampering detection

Every blocking hook in the catalog has a SHA-256 hash recorded in `hooks/.integrity.json`. The companion `scripts/hook_integrity.py` exposes:

- `--update`: regenerate the manifest from the current files. Run after any intentional change to a hook.
- `--verify`: compare every entry against its current hash; non-zero exit on drift.
- `assert_self(__file__)`: importable helper that hooks can call at startup. On drift, writes a stderr warning and returns False but never raises. Detection, not enforcement: a tampered hook still runs.

### Path traversal

Hooks accept file paths from the caller (Claude payload in JSON mode, argv or stdin in batch mode). Paths are opened verbatim. No defense-in-depth normalization beyond `encoding="utf-8"`, which causes binary or sensitive files to raise `UnicodeDecodeError` and be skipped silently. Output is limited to JS/TS mutation findings, so reading an unrelated file yields no useful signal. Threat model: a malicious commit cannot exfiltrate `/etc/passwd` because the hook only emits structured findings for code patterns it recognizes.

### ReDoS

Every detector regex has been audited for nested quantifiers and overlapping alternations. The two patterns that contain `(?:\.X)*` constructs require a literal dot at each iteration, so each iteration consumes at least two characters. Linear time. New detectors must avoid:

- `(a+)+` style nested unbounded repetition.
- `(a|a)*` overlapping alternations under repetition.
- `[\s\S]*` anchored on both ends with no fixed delimiter.

Run new patterns through `python3 -m re_redos_detector` (when installed) before merge.

### Secret redaction in telemetry

Three sinks ship telemetry beyond the local file:

| Sink | Redaction |
|------|-----------|
| `scripts/audit_log.py` | `redact()` strips AKIA, sk-ant, gh tokens, JWTs, and 40+ other patterns from `command_excerpt` and similar fields before writing the JSON line |
| `hooks/sarif_emitter.py` | Emits only the matched line text (≤ 240 chars), the line number, and a SHA-256 fingerprint. Never emits surrounding file context |
| `scripts/otel_exporter.py` | Span attributes are limited to hook name, detector tag, decision, file path, line number, latency, and confidence. No code snippets, no payloads, no environment variables |

Adding a new field to any of these sinks requires reviewing it against the redaction list. Any field that can carry user code or environment values must pass through `redact()` first.

### Subprocess discipline

The only subprocess invocation is `subprocess.run([binary, ...], shell=False, timeout=2.0)` in `scripts/mutation_detectors_core.py` for ast-grep. Args are a fixed list, never a string. Stdin is piped from in-memory file content. No format string interpolation. Safe.

## Versioning Policy

Every blocking hook records `__version__ = "<MAJOR>.<MINOR>.<PATCH>"` at module scope. Bumps follow semver:

| Bump | When |
|------|------|
| Patch (`2.0.0` -> `2.0.1`) | Bug fix, false-positive correction, fixture addition. No detector behavior change visible from outside. |
| Minor (`2.0.0` -> `2.1.0`) | Backward-compatible addition: new detector, new env var, new auto-allowed scope, new fix-suggestion mapping. Existing payloads still produce the same outcome. |
| Major (`2.0.0` -> `3.0.0`) | Breaking change: rename of an env var, removal of a detector, change in exit-code semantics, change in audit-log field names that downstream tooling reads. |

Every minor or major bump:

1. Updates the `__version__` constant.
2. Adds a row to the migration note section in the hook docstring.
3. Adds a corresponding section in `~/.claude/docs/migrations/` when the bump is major.
4. Bumps the corpus `VERSION` file's `hook_version_min` field if the bump is major.

Patch bumps do not require a migration note.

## Rules

- Never use `set -e` in hooks. A failed grep match returns exit code 1, which would terminate the hook and produce an unexpected exit code.
- Always write to stderr for block messages, never stdout.
- Keep pattern lists in arrays or external files for maintainability.
- Log blocked actions with enough context to debug false positives: the matched pattern and the original command.
- Test every new pattern against both positive matches and negative matches before deploying.
- Hooks must work without external dependencies beyond standard Unix tools: bash, grep, jq, sed, awk.
- When matching commands, account for path prefixes, extra whitespace, and quoted arguments.
- Every blocking hook must emit a structured audit event before `exit 2`. See "Audit Emission" above.
