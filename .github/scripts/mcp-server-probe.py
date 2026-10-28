#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

START_TIMEOUT_SECONDS = 3


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True, slots=True)
class Server:
    name: str
    command: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Probe:
    outcome: Outcome
    line: str


def load_servers(settings: Path) -> list[Server]:
    servers = json.loads(settings.read_text(encoding="utf-8")).get("mcpServers", {})
    return [
        Server(name, str(cfg.get("command", "")), tuple(map(str, cfg.get("args", []))))
        for name, cfg in servers.items()
    ]


def probe(server: Server, verbose: bool) -> Probe:
    if not server.command or shutil.which(server.command) is None:
        return Probe(
            Outcome.SKIP,
            f"SKIP ({server.name}): command not found: {server.command}",
        )
    try:
        completed = subprocess.run(
            [server.command, *server.args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=START_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Probe(
            Outcome.PASS,
            f"PASS ({server.name}): started successfully (timed out as expected)",
        )
    if completed.returncode == 0:
        return Probe(Outcome.PASS, f"PASS ({server.name}): exited cleanly")
    detail = (
        f"\n  Command: {' '.join([server.command, *server.args])}" if verbose else ""
    )
    return Probe(
        Outcome.FAIL,
        f"FAIL ({server.name}): exited with code {completed.returncode}{detail}",
    )


def summary(probes: list[Probe]) -> str:
    counts = {outcome: sum(p.outcome is outcome for p in probes) for outcome in Outcome}
    return (
        f"Results: {counts[Outcome.PASS]} passed, {counts[Outcome.FAIL]} failed, "
        f"{counts[Outcome.SKIP]} skipped"
    )


def main(argv: list[str], home: Path) -> int:
    settings = home / ".claude" / "settings.json"
    if not settings.is_file():
        print(f"ERROR: settings.json not found at {settings}")
        return 1
    servers = load_servers(settings)
    if not servers:
        print("No MCP servers configured in settings.json.")
        return 0
    print("=== MCP Health Check ===\n")
    probes = [probe(server, bool(argv)) for server in servers]
    for result in probes:
        print(result.line)
    print(f"\n{summary(probes)}")
    return 1 if any(p.outcome is Outcome.FAIL for p in probes) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], Path.home()))
