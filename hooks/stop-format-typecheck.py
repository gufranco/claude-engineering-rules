#!/usr/bin/env python3
"""Stop hook: format every batched file once, run tsc once per TS workspace.

Reads the per-session batch file written by the PostToolUse formatter accumulator,
deduplicates, groups by extension, and invokes each formatter a single time with
the full file list. Clears the batch file at the end.

Batch file path: `$CLAUDE_FORMATTER_BATCH` if set, else `~/.claude/cache/edit-batch.txt`.

Bypass channels:
    1. Env var `STOP_FORMAT_DISABLE=1` (parent shell).
    2. File registry entry for hook `stop-format-typecheck`.
    3. Profile gate via `hook_profile.should_run`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.bypass import is_bypassed  # noqa: E402

try:
    from _lib.hook_profile import should_run
except Exception:  # noqa: BLE001

    def should_run(_name: str) -> bool:  # type: ignore[override]
        return True


HOOK_NAME = "stop-format-typecheck"
ENV_DISABLE = "STOP_FORMAT_DISABLE"
ENV_BATCH = "CLAUDE_FORMATTER_BATCH"
DEFAULT_BATCH = Path.home() / ".claude" / "cache" / "edit-batch.txt"
TSC_TIMEOUT_SECONDS = 60
FORMATTER_TIMEOUT_SECONDS = 60

PRETTIER_EXTS = {
    "js",
    "jsx",
    "ts",
    "tsx",
    "json",
    "css",
    "scss",
    "html",
    "md",
    "yaml",
    "yml",
}
PYTHON_EXTS = {"py"}
GO_EXTS = {"go"}
RUST_EXTS = {"rs"}
RUBY_EXTS = {"rb"}
SHELL_EXTS = {"sh", "bash", "zsh"}
TS_EXTS = {"ts", "tsx"}


def _batch_path() -> Path:
    override = os.environ.get(ENV_BATCH)
    return Path(override) if override else DEFAULT_BATCH


def _run_quietly(argv: list[str]) -> None:
    try:
        subprocess.run(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=FORMATTER_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass


def _format_with(tool: str, *args: str) -> None:
    if shutil.which(tool) is None:
        return
    _run_quietly([tool, *args])


def _find_ts_workspace(path: Path) -> Path | None:
    current = path.parent.resolve()
    root = Path(current.root)
    while current != root and current != current.parent:
        if (current / "tsconfig.json").is_file() and (
            current / "package.json"
        ).is_file():
            return current
        current = current.parent
    return None


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1":
        return 0
    if is_bypassed(HOOK_NAME):
        return 0
    if not should_run(HOOK_NAME):
        return 0
    batch = _batch_path()
    if not batch.is_file():
        return 0
    raw = batch.read_text(encoding="utf-8")
    if not raw.strip():
        return 0
    seen: OrderedDict[str, None] = OrderedDict()
    for line in raw.splitlines():
        candidate = line.strip()
        if candidate:
            seen.setdefault(candidate, None)
    files = [Path(name) for name in seen if Path(name).is_file()]
    if not files:
        batch.write_text("", encoding="utf-8")
        return 0

    buckets: dict[str, list[str]] = {
        "prettier": [],
        "python": [],
        "go": [],
        "rust": [],
        "ruby": [],
        "shell": [],
    }
    ts_files: list[Path] = []
    for path in files:
        ext = path.suffix.lstrip(".").lower()
        if ext in PRETTIER_EXTS:
            buckets["prettier"].append(str(path))
            if ext in TS_EXTS:
                ts_files.append(path)
        elif ext in PYTHON_EXTS:
            buckets["python"].append(str(path))
        elif ext in GO_EXTS:
            buckets["go"].append(str(path))
        elif ext in RUST_EXTS:
            buckets["rust"].append(str(path))
        elif ext in RUBY_EXTS:
            buckets["ruby"].append(str(path))
        elif ext in SHELL_EXTS:
            buckets["shell"].append(str(path))

    if buckets["prettier"]:
        _format_with("prettier", "--write", *buckets["prettier"])
    if buckets["python"]:
        if shutil.which("black"):
            _format_with("black", "--quiet", *buckets["python"])
        elif shutil.which("ruff"):
            _format_with("ruff", "format", *buckets["python"])
    if buckets["go"]:
        _format_with("gofmt", "-w", *buckets["go"])
    if buckets["rust"]:
        for path in buckets["rust"]:
            _format_with("rustfmt", path)
    if buckets["ruby"]:
        _format_with("rubocop", "-A", "--fail-level", "E", *buckets["ruby"])
    if buckets["shell"]:
        _format_with("shfmt", "-w", *buckets["shell"])

    workspaces: OrderedDict[str, None] = OrderedDict()
    for path in ts_files:
        ws = _find_ts_workspace(path)
        if ws is not None:
            workspaces.setdefault(str(ws), None)
    for ws_path in workspaces:
        cwd = Path(ws_path)
        if not cwd.is_dir():
            continue
        try:
            subprocess.run(
                [
                    "npx",
                    "--no-install",
                    "tsc",
                    "--noEmit",
                    "--incremental",
                    "--tsBuildInfoFile",
                    "node_modules/.cache/tsc-hook.tsbuildinfo",
                ],
                cwd=str(cwd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TSC_TIMEOUT_SECONDS,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    batch.write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
