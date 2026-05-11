"""ts-morph integration shim (plan item 381).

The mutation-method-blocker hook is regex-first by design: it analyzes the
text payload of a single Edit/Write call without parsing the project. When
the hook is uncertain about a receiver, this shim consults the TypeScript
compiler indirectly via the `ts-morph` library to retrieve authoritative
`readonly` type annotations.

The bridge is a soft dependency. If `ts-morph` is not installed or the
shim helper script is missing, every query returns `unknown` and the hook
falls back to its built-in pattern matching. The bridge MUST NOT block the
hook: a 200ms timeout caps each query.

Public API:

  query_readonly(file_path: str, receiver: str, line: int) -> TypeAnswer
  is_bridge_available() -> bool

Returns:

  TypeAnswer.READONLY   compiler reports the receiver is `Readonly<T>`,
                       `readonly`, `ReadonlyArray<T>`, `ReadonlyMap`, etc.
  TypeAnswer.MUTABLE    compiler reports the receiver is plainly mutable.
  TypeAnswer.UNKNOWN    bridge unavailable, timeout, or compiler error.

When TypeScript Project Service (TS 5.6+) is preferred and the env var
`MUTATION_METHOD_TS_PROJECT_SERVICE=1` is set, the bridge attempts to use
the Project Service protocol instead of spawning a full `tsc` process. The
Project Service is faster but requires a recent TypeScript install.

Environment variables:

  MUTATION_METHOD_TYPE_BRIDGE         1 to enable (default 0).
  MUTATION_METHOD_TS_PROJECT_SERVICE  1 for Project Service mode (TS 5.6+).
  MUTATION_METHOD_BRIDGE_TIMEOUT_MS   Per-query timeout in ms (default 200).
  MUTATION_METHOD_BRIDGE_NODE_BIN     Path to node binary (default: PATH).
"""

from __future__ import annotations

import enum
import json
import os
import shutil
import subprocess

ENV_FLAG = "MUTATION_METHOD_TYPE_BRIDGE"
ENV_PROJECT_SERVICE = "MUTATION_METHOD_TS_PROJECT_SERVICE"
ENV_TIMEOUT_MS = "MUTATION_METHOD_BRIDGE_TIMEOUT_MS"
ENV_NODE_BIN = "MUTATION_METHOD_BRIDGE_NODE_BIN"

DEFAULT_TIMEOUT_MS = 200


class TypeAnswer(enum.Enum):
    """Tri-state result from the type bridge."""

    READONLY = "readonly"
    MUTABLE = "mutable"
    UNKNOWN = "unknown"


def is_bridge_available() -> bool:
    """True when the bridge can be invoked.

    Checks node binary presence and the `MUTATION_METHOD_TYPE_BRIDGE`
    opt-in flag. Does not verify `ts-morph` is installed; that check
    happens inside the spawned helper.
    """
    if os.environ.get(ENV_FLAG, "0") != "1":
        return False
    node_bin = os.environ.get(ENV_NODE_BIN, "")
    if node_bin:
        return os.path.isfile(node_bin)
    return shutil.which("node") is not None


def _timeout_seconds() -> float:
    raw = os.environ.get(ENV_TIMEOUT_MS, "")
    if raw.isdigit():
        return max(1, int(raw)) / 1000.0
    return DEFAULT_TIMEOUT_MS / 1000.0


def _node_binary() -> str:
    return os.environ.get(ENV_NODE_BIN) or "node"


def query_readonly(file_path: str, receiver: str, line: int) -> TypeAnswer:
    """Ask the TypeScript compiler whether `receiver` is readonly at `line`.

    Returns UNKNOWN on any failure (bridge disabled, node missing,
    timeout, ts-morph not installed, parse error). The hook treats
    UNKNOWN as "no opinion" and continues with its pattern-based logic.
    """
    if not is_bridge_available():
        return TypeAnswer.UNKNOWN
    payload = json.dumps(
        {
            "file": file_path,
            "receiver": receiver,
            "line": line,
            "projectService": os.environ.get(ENV_PROJECT_SERVICE, "0") == "1",
        }
    )
    helper_path = os.path.join(
        os.path.expanduser("~/.claude"), "scripts", "ts_bridge_helper.js"
    )
    if not os.path.isfile(helper_path):
        return TypeAnswer.UNKNOWN
    try:
        completed = subprocess.run(
            [_node_binary(), helper_path],
            input=payload,
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return TypeAnswer.UNKNOWN
    if completed.returncode != 0:
        return TypeAnswer.UNKNOWN
    try:
        result = json.loads(completed.stdout.strip())
    except (ValueError, json.JSONDecodeError):
        return TypeAnswer.UNKNOWN
    verdict = result.get("verdict")
    if verdict == "readonly":
        return TypeAnswer.READONLY
    if verdict == "mutable":
        return TypeAnswer.MUTABLE
    return TypeAnswer.UNKNOWN
