"""Shared I/O contract for `~/.claude/hooks/*.py` PreToolUse and PostToolUse hooks.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.1.4.

Hides the contract drift between the v1 (stderr + exit 2) and v2
(`hookSpecificOutput` JSON on stdout) Claude Code hook formats. Every Python
hook in this repo can import the small set of helpers below and stop owning
the contract details.

Public API:

    read_input() -> ToolUse
        Parse JSON from stdin. Never raises. On parse failure, returns an
        empty ToolUse so callers fall through to allow().

    block(reason: str, *, audit_payload=None, suggestion=None) -> int
        Print `reason` (and optional fix `suggestion`) to stderr and return
        exit code 2 so the orchestrator blocks the tool call. Records a
        block decision in the audit log when `audit_payload` is provided.

    allow() -> int
        Return exit code 0 (the orchestrator allows the tool call).

    defer() -> int
        Return exit code 0 with no message. Used by hooks that decide a
        condition is out of scope (e.g., file extension not handled).

    ask(message: str) -> int
        Print `message` to stderr and return exit code 1. The orchestrator
        forwards the message to the model, which can revise its tool call.

    modify_input(updates: dict, *, original: ToolUse) -> int
        Emit the v2 `hookSpecificOutput.permissionDecision = "allow"` shape
        with a `modifiedInput` body. Falls back to allow() when v2 is
        unavailable. Used by smart-formatter and similar rewriters.

    add_post_context(text: str) -> int
        Emit the v2 `additionalContext` body. Used by PostToolUse hooks that
        feed information back to the model (per Claude Code v2 hooks).

The functions follow the tool-protocol used by every existing hook in this
repo, so callers can adopt incrementally: replace `sys.exit(2)` and stderr
prints with `block(...)`, then drop the boilerplate around stdin parsing.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolUse:
    """Parsed PreToolUse / PostToolUse payload.

    `tool_name`, `tool_input`, and `cwd` mirror the schema documented in the
    Claude Code hooks reference. Unknown fields land in `extra` so callers
    can read v2-only fields without forcing every hook to know about them.
    """

    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    cwd: str = ""
    session_id: str = ""
    transcript_path: str = ""
    hook_event_name: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def read_input() -> ToolUse:
    """Parse JSON from stdin into a `ToolUse`. Empty payload on parse failure."""
    raw = sys.stdin.read()
    if not raw:
        return ToolUse()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ToolUse()
    if not isinstance(payload, dict):
        return ToolUse()
    known = {
        "tool_name",
        "tool_input",
        "cwd",
        "session_id",
        "transcript_path",
        "hook_event_name",
    }
    extra = {k: v for k, v in payload.items() if k not in known}
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    return ToolUse(
        tool_name=str(payload.get("tool_name") or ""),
        tool_input=tool_input,
        cwd=str(payload.get("cwd") or ""),
        session_id=str(payload.get("session_id") or ""),
        transcript_path=str(payload.get("transcript_path") or ""),
        hook_event_name=str(payload.get("hook_event_name") or ""),
        extra=extra,
    )


def _emit_audit(payload: dict[str, Any] | None) -> None:
    if not payload:
        return
    try:
        sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
        from audit_log import record as _record
    except ImportError:
        return
    try:
        _record(**payload)
    except (OSError, TypeError, ValueError):
        return


def block(
    reason: str,
    *,
    hook_event_name: str = "PreToolUse",
    audit_payload: dict[str, Any] | None = None,
    suggestion: str | None = None,
) -> int:
    """Dual-emit deny.

    v1: prints `reason` (and optional `suggestion`) to stderr.
    v2: emits a `hookSpecificOutput.permissionDecision = "deny"` envelope on
    stdout so v2-aware orchestrators can read the structured reason without
    parsing free-form stderr text. Both channels carry the same content so
    rolling between v1 and v2 orchestrators is loss-free.

    Returns exit code 2 in both cases.
    """
    if reason:
        print(reason, file=sys.stderr)
    if suggestion:
        print(f"\nFix:\n{suggestion}", file=sys.stderr)
    if reason:
        body = {
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        try:
            sys.stdout.write(json.dumps(body, ensure_ascii=False))
            sys.stdout.flush()
        except (OSError, TypeError, ValueError):
            pass
    _emit_audit(audit_payload)
    return 2


def allow() -> int:
    """Return exit 0. Used when the hook explicitly approves the tool call."""
    return 0


def defer() -> int:
    """Return exit 0 with no output. Used when the hook does not apply."""
    return 0


def ask(message: str) -> int:
    """Print `message` to stderr, return exit 1 so the model can revise."""
    if message:
        print(message, file=sys.stderr)
    return 1


def modify_input(updates: dict[str, Any], *, original: ToolUse) -> int:
    """Emit a v2 modifiedInput response. Falls back to allow() on serialization error."""
    if not isinstance(updates, dict) or not updates:
        return allow()
    merged = {**original.tool_input, **updates}
    body = {
        "hookSpecificOutput": {
            "hookEventName": original.hook_event_name or "PreToolUse",
            "permissionDecision": "allow",
            "modifiedInput": merged,
        }
    }
    try:
        sys.stdout.write(json.dumps(body, ensure_ascii=False))
        sys.stdout.flush()
    except (OSError, TypeError, ValueError):
        return allow()
    return 0


def add_post_context(text: str) -> int:
    """Emit a v2 PostToolUse additionalContext body. Falls back to allow()."""
    if not text:
        return allow()
    body = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": text,
        }
    }
    try:
        sys.stdout.write(json.dumps(body, ensure_ascii=False))
        sys.stdout.flush()
    except (OSError, TypeError, ValueError):
        return allow()
    return 0
