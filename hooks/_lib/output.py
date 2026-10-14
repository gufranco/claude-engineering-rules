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


def _bypass_block(hook: str, bypass_when: str, env_var: str, safety: str | None) -> str:
    safety_line = safety or "subsequent runs of the same payload will not be checked."
    return (
        f"{bypass_when}\n"
        f"env: {env_var}=1 (parent shell)\n"
        f'file: python scripts/bypass.py set {hook} --ttl 600 --reason "<why>"\n'
        f"safety: {safety_line}"
    )


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
    bodies = (
        _cap(detected),
        _cap(why),
        _cap(fix),
        _bypass_block(hook, _cap(bypass_when), env_var, safety),
        decision,
    )
    sections = (
        line
        for label, body in zip(_SECTION_ORDER, bodies, strict=True)
        for line in (label, _indent(body), "")
    )
    return "\n".join([f"BLOCKED by {hook} ({rule_anchor})", "", *sections])


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


_DECISION_MARKER: Final = "Decision guidance for Claude:"
_BYPASS_MARKER: Final = "If the rule does not apply here:"


def _order_issues(message: str) -> list[str]:
    issues: list[str] = []
    last_pos = -1
    for label in _SECTION_ORDER:
        pos = message.find(label)
        if pos == -1:
            issues.append(f"missing required section '{label}'")
        elif pos < last_pos:
            issues.append(f"section '{label}' appears out of order")
        else:
            last_pos = pos
    return issues


def _decision_issues(message: str, decision_pos: int) -> list[str]:
    if decision_pos == -1:
        return []
    tail = message[decision_pos + len(_DECISION_MARKER) :].strip().splitlines()
    first_line = tail[0].strip() if tail else ""
    if first_line in DECISION_VERBS:
        return []
    return [f"decision verb {first_line!r} is not one of {sorted(DECISION_VERBS)}"]


def _bypass_issues(message: str, decision_pos: int) -> list[str]:
    bypass_pos = message.find(_BYPASS_MARKER)
    if bypass_pos == -1:
        return []
    block_body = (
        message[bypass_pos:decision_pos]
        if decision_pos > bypass_pos
        else message[bypass_pos:]
    )
    issues: list[str] = []
    if "env:" not in block_body and "_DISABLE" not in block_body:
        issues.append("bypass section is missing the env-var channel reference")
    if "file:" not in block_body and "scripts/bypass.py" not in block_body:
        issues.append("bypass section is missing the file-registry channel reference")
    return issues


def validate_block_message(message: str) -> list[str]:
    header = (
        []
        if message.lstrip().startswith("BLOCKED by ")
        else ["missing 'BLOCKED by <hook>' header on first line"]
    )
    decision_pos = message.find(_DECISION_MARKER)
    return [
        *header,
        *_order_issues(message),
        *_decision_issues(message, decision_pos),
        *_bypass_issues(message, decision_pos),
    ]
