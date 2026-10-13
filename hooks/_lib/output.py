from __future__ import annotations

from typing import Final

DECISION_VERBS: Final[frozenset[str]] = frozenset(
    {"STOP-AND-ASK", "FIX-AND-RETRY", "BYPASS-ONCE", "BYPASS-WITH-REASON"}
)

_SECTION_ORDER: Final[tuple[str, ...]] = (
    "What was detected:",
    "Why this rule exists:",
    "How to fix:",
    "If the rule does not apply here:",
    "Decision guidance for Claude:",
)

_LINE_CAP = 200


def _cap(body: str) -> str:
    out: list[str] = []
    for line in body.splitlines():
        if len(line) > _LINE_CAP:
            out.append(line[:_LINE_CAP] + "...")
        else:
            out.append(line)
    return "\n".join(out)


def _indent(body: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line if line else line for line in body.splitlines())


def block(
    *,
    hook: str,
    rule_anchor: str,
    detected: str,
    why: str,
    fix: str,
    bypass_when: str,
    decision: str,
    env_var: str,
    safety: str | None = None,
) -> str:
    if decision not in DECISION_VERBS:
        raise ValueError(
            f"unknown decision verb {decision!r}; expected one of {sorted(DECISION_VERBS)}"
        )
    detected = _cap(detected)
    why = _cap(why)
    fix = _cap(fix)
    bypass_when = _cap(bypass_when)
    safety_line = safety or "subsequent runs of the same payload will not be checked."
    bypass_block = (
        f"{bypass_when}\n"
        f"env: {env_var}=1 (parent shell)\n"
        f'file: python scripts/bypass.py set {hook} --ttl 600 --reason "<why>"\n'
        f"safety: {safety_line}"
    )
    parts = [
        f"BLOCKED by {hook} ({rule_anchor})",
        "",
        "What was detected:",
        _indent(detected),
        "",
        "Why this rule exists:",
        _indent(why),
        "",
        "How to fix:",
        _indent(fix),
        "",
        "If the rule does not apply here:",
        _indent(bypass_block),
        "",
        "Decision guidance for Claude:",
        _indent(decision),
        "",
    ]
    return "\n".join(parts)


def warn(
    *,
    hook: str,
    purpose: str,
    saved_to: str | None = None,
    next_action: str | None = None,
) -> str:
    parts = [f"INFO from {hook}", "", "Purpose:", _indent(_cap(purpose))]
    if saved_to:
        parts.extend(["", "Saved to:", _indent(_cap(saved_to))])
    if next_action:
        parts.extend(["", "Next:", _indent(_cap(next_action))])
    parts.append("")
    return "\n".join(parts)


def validate_block_message(message: str) -> list[str]:
    issues: list[str] = []
    if not message.lstrip().startswith("BLOCKED by "):
        issues.append("missing 'BLOCKED by <hook>' header on first line")
    last_pos = -1
    for label in _SECTION_ORDER:
        pos = message.find(label)
        if pos == -1:
            issues.append(f"missing required section '{label}'")
        elif pos < last_pos:
            issues.append(f"section '{label}' appears out of order")
        else:
            last_pos = pos
    decision_marker = "Decision guidance for Claude:"
    decision_pos = message.find(decision_marker)
    if decision_pos != -1:
        tail = message[decision_pos + len(decision_marker) :].strip().splitlines()
        first_line = tail[0].strip() if tail else ""
        if first_line not in DECISION_VERBS:
            issues.append(
                f"decision verb {first_line!r} is not one of {sorted(DECISION_VERBS)}"
            )
    bypass_marker = "If the rule does not apply here:"
    bypass_pos = message.find(bypass_marker)
    if bypass_pos != -1:
        block_body = (
            message[bypass_pos:decision_pos]
            if decision_pos > bypass_pos
            else message[bypass_pos:]
        )
        if "env:" not in block_body and "_DISABLE" not in block_body:
            issues.append("bypass section is missing the env-var channel reference")
        if "file:" not in block_body and "scripts/bypass.py" not in block_body:
            issues.append(
                "bypass section is missing the file-registry channel reference"
            )
    return issues
