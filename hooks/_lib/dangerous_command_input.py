from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn


@dataclass(frozen=True, slots=True)
class CommandInput:
    command: str
    cwd: str


def read_command(refuse: Callable[[str], NoReturn]) -> CommandInput:
    try:
        data = json.loads(sys.stdin.read())
    except ValueError as exc:
        refuse(f"stdin is not UTF-8 JSON ({type(exc).__name__})")
    if not isinstance(data, dict):
        refuse("the payload is not a JSON object")
    tool_input = data.get("tool_input", data.get("input", {}))
    if not isinstance(tool_input, dict):
        refuse("tool_input is not an object")
    command = tool_input.get("command", "")
    if not isinstance(command, str):
        refuse("tool_input.command is not a string")
    cwd = data.get("cwd", "")
    return CommandInput(command, cwd if isinstance(cwd, str) else "")
