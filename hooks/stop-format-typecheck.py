#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.hook_warning import emit_warning  # noqa: E402
from _lib.project_scope import walk_up  # noqa: E402

from _lib.bypass import is_bypassed  # noqa: E402

from _lib.hook_profile import should_run  # noqa: E402


HOOK_NAME = "stop-format-typecheck"
ENV_DISABLE = "STOP_FORMAT_DISABLE"
ENV_BATCH = "CLAUDE_FORMATTER_BATCH"
BATCH_DIR = Path.home() / ".claude" / "cache"
TSC_REPORT_LINES = 30
CONFIG_SEARCH_LIMIT = 20
FORMATTER_CONFIGS = {
    "prettier": (
        ".prettierrc",
        ".prettierrc.json",
        ".prettierrc.yaml",
        ".prettierrc.yml",
        ".prettierrc.js",
        ".prettierrc.cjs",
        ".prettierrc.mjs",
        ".prettierrc.toml",
        "prettier.config.js",
        "prettier.config.cjs",
        "prettier.config.mjs",
    ),
    "shfmt": (".editorconfig",),
    "rubocop": (".rubocop.yml",),
}
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


def batch_path(session_id: str) -> Path:
    override = os.environ.get(ENV_BATCH)
    if override:
        return Path(override)
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id) or "default"
    return BATCH_DIR / f"edit-batch-{safe}.txt"


def _session_id() -> str:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError as error:
        sys.stderr.write(f"{HOOK_NAME}: unreadable payload: {error}\n")
        return ""
    return str(payload.get("session_id") or "") if isinstance(payload, dict) else ""


def _claim(batch: Path) -> list[str]:
    claimed = batch.with_name(batch.name + ".claimed")
    try:
        os.replace(batch, claimed)
    except FileNotFoundError:
        return []
    try:
        return claimed.read_text(encoding="utf-8").splitlines()
    finally:
        claimed.unlink(missing_ok=True)


def _package_names_prettier(directory: Path) -> bool:
    package = directory / "package.json"
    return package.is_file() and '"prettier"' in package.read_text(encoding="utf-8")


def configured(tool: str, path: Path) -> bool:
    markers = FORMATTER_CONFIGS.get(tool)
    if markers is None:
        return True
    return any(
        any((directory / marker).is_file() for marker in markers)
        or (tool == "prettier" and _package_names_prettier(directory))
        for directory in walk_up(path.parent, limit=CONFIG_SEARCH_LIMIT)
    )


def _run_quietly(argv: list[str]) -> None:
    try:
        subprocess.run(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=FORMATTER_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as error:
        sys.stderr.write(f"stop-format-typecheck: {argv[0]} failed: {error}\n")


def _format_with(tool: str, *args: str) -> None:
    if shutil.which(tool) is None:
        return
    _run_quietly([tool, *args])


def _find_ts_workspace(path: Path) -> Path | None:
    """Return the nearest TypeScript workspace, bounded by the repository.

    Without the boundary the walk reaches the home directory and can adopt an
    unrelated workspace as the one to type-check.
    """
    for current in walk_up(path.parent, limit=20):
        if (current / "tsconfig.json").is_file() and (
            current / "package.json"
        ).is_file():
            return current
    return None


EXTENSION_BUCKETS = (
    (PRETTIER_EXTS, "prettier"),
    (PYTHON_EXTS, "python"),
    (GO_EXTS, "go"),
    (RUST_EXTS, "rust"),
    (RUBY_EXTS, "ruby"),
    (SHELL_EXTS, "shell"),
)
BUCKET_TOOL = {"prettier": "prettier", "shell": "shfmt", "ruby": "rubocop"}


def _bucket(path: Path) -> str | None:
    ext = path.suffix.lstrip(".").lower()
    name = next((bucket for exts, bucket in EXTENSION_BUCKETS if ext in exts), None)
    if name is None or not configured(BUCKET_TOOL.get(name, name), path):
        return None
    return name


def _format_python(files: list[str]) -> None:
    if shutil.which("ruff"):
        _format_with("ruff", "format", *files)
    elif shutil.which("black"):
        _format_with("black", "--quiet", *files)


def _format_all(buckets: dict[str, list[str]]) -> None:
    if buckets.get("prettier"):
        _format_with("prettier", "--write", *buckets["prettier"])
    if buckets.get("python"):
        _format_python(buckets["python"])
    if buckets.get("go"):
        _format_with("gofmt", "-w", *buckets["go"])
    for path in buckets.get("rust", []):
        _format_with("rustfmt", path)
    if buckets.get("ruby"):
        _format_with("rubocop", "-A", "--fail-level", "E", *buckets["ruby"])
    if buckets.get("shell"):
        _format_with("shfmt", "-w", *buckets["shell"])


def _tsc_report(workspace: Path) -> str | None:
    argv = [
        "npx",
        "--no-install",
        "tsc",
        "--noEmit",
        "--incremental",
        "--tsBuildInfoFile",
        "node_modules/.cache/tsc-hook.tsbuildinfo",
    ]
    try:
        result = subprocess.run(
            argv,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=TSC_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as error:
        return f"tsc in {workspace} did not run: {error}"
    if result.returncode == 0:
        return None
    lines = (result.stdout + result.stderr).strip().splitlines()[:TSC_REPORT_LINES]
    return f"tsc in {workspace} failed:\n" + "\n".join(lines)


def _typecheck(ts_files: list[Path]) -> list[str]:
    workspaces = OrderedDict(
        (str(ws), None) for ws in map(_find_ts_workspace, ts_files) if ws is not None
    )
    reports = [_tsc_report(Path(ws)) for ws in workspaces if Path(ws).is_dir()]
    return [report for report in reports if report]


def main() -> int:
    if os.environ.get(ENV_DISABLE) == "1" or is_bypassed(HOOK_NAME):
        return 0
    if not should_run(HOOK_NAME):
        return 0
    names = OrderedDict(
        (line.strip(), None) for line in _claim(batch_path(_session_id()))
    )
    files = [Path(name) for name in names if name and Path(name).is_file()]
    buckets: dict[str, list[str]] = {}
    for path in files:
        bucket = _bucket(path)
        if bucket:
            buckets = {**buckets, bucket: [*buckets.get(bucket, []), str(path)]}
    _format_all(buckets)
    ts_files = [path for path in files if path.suffix.lstrip(".").lower() in TS_EXTS]
    reports = _typecheck(ts_files)
    if reports:
        emit_warning("\n\n".join(reports), event="Stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
