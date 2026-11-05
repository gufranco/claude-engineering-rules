from __future__ import annotations

import json
import os
from pathlib import PurePath

POLICY_STEMS = frozenset(
    {
        "clean_room",
        "clean-room",
        "cleanroom",
        "license",
        "licence",
        "copying",
        "notice",
        "third_party_notices",
        "third-party-notices",
        "thirdpartynotices",
        "legal",
    }
)
POLICY_SUFFIXES = frozenset({"", ".md", ".txt", ".rst"})
LICENSE_TEXT_DIRECTORY = "licenses"

ASK_REASON = (
    "{name} is a legal policy file: it decides what the project may copy, ship, "
    "or claim, and it changes only with the maintainer's approval. Approve this "
    "edit only if you asked for it. Rule: rules/clean-room.md"
)


def is_legal_policy_file(file_path: str) -> bool:
    path = PurePath(file_path)
    if path.parent.name.lower() == LICENSE_TEXT_DIRECTORY:
        return True
    name = path.name.lower()
    suffix = PurePath(name).suffix
    if suffix not in POLICY_SUFFIXES:
        return False
    return name.removesuffix(suffix) in POLICY_STEMS


def needs_approval(tool_name: str, file_path: str) -> bool:
    if not is_legal_policy_file(file_path):
        return False
    return tool_name != "Write" or os.path.exists(file_path)


def ask_decision(file_path: str) -> str:
    reason = ASK_REASON.format(name=PurePath(file_path).name)
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        }
    )
