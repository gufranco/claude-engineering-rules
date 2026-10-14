from __future__ import annotations

KNOWN_HOOK_EVENTS = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "SubagentStop",
        "PreCompact",
        "PostCompact",
        "UserPromptSubmit",
        "SessionStart",
        "SessionEnd",
        "Notification",
    }
)


def _command_findings(prefix: str, command_hook: object) -> list[str]:
    if not isinstance(command_hook, dict):
        return [f"{prefix} must be an object."]
    htype = command_hook.get("type")
    type_findings = (
        [f"{prefix}.type must be `command`, got `{htype}`."]
        if htype != "command"
        else []
    )
    command_findings = (
        []
        if command_hook.get("command")
        else [f"{prefix}.command must be a non-empty string."]
    )
    return [*type_findings, *command_findings]


def _group_findings(event: str, index: int, group: object) -> list[str]:
    if not isinstance(group, dict):
        return [f"hooks.{event}[{index}] must be an object."]
    inner = group.get("hooks")
    if inner is None:
        return []
    if not isinstance(inner, list):
        return [f"hooks.{event}[{index}].hooks must be a list."]
    return [
        finding
        for j, command_hook in enumerate(inner)
        for finding in _command_findings(
            f"hooks.{event}[{index}].hooks[{j}]", command_hook
        )
    ]


def _event_findings(event: str, entries: object) -> list[str]:
    if event not in KNOWN_HOOK_EVENTS:
        known = ", ".join(sorted(KNOWN_HOOK_EVENTS))
        return [f"unknown hook event `{event}`. Known events: {known}."]
    if not isinstance(entries, list):
        return [f"hooks.{event} must be a list of matcher groups."]
    return [
        finding
        for i, group in enumerate(entries)
        for finding in _group_findings(event, i, group)
    ]


def _hooks_findings(hooks: object) -> list[str]:
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        return ["`hooks` must be an object keyed by event name."]
    return [
        finding
        for event, entries in hooks.items()
        for finding in _event_findings(event, entries)
    ]


def _server_findings(name: str, cfg: object) -> list[str]:
    if not isinstance(cfg, dict):
        return [f"mcpServers.{name} must be an object."]
    has_command = "command" in cfg
    has_url = "url" in cfg
    if has_command and has_url:
        return [f"mcpServers.{name} has both `command` and `url`. Pick one transport."]
    if not has_command and not has_url:
        return [f"mcpServers.{name} needs either `command` (stdio) or `url` (http)."]
    return []


def _mcp_findings(mcp: object) -> list[str]:
    if mcp is None:
        return []
    if not isinstance(mcp, dict):
        return ["`mcpServers` must be an object keyed by server name."]
    return [
        finding for name, cfg in mcp.items() for finding in _server_findings(name, cfg)
    ]


def check_structure(parsed: object) -> list[str]:
    if not isinstance(parsed, dict):
        return []
    return [
        *_hooks_findings(parsed.get("hooks")),
        *_mcp_findings(parsed.get("mcpServers")),
    ]
