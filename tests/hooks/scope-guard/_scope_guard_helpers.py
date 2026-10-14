from __future__ import annotations
import os
import time


HOOK = "scope-guard"


def make_plan(tmp_path, paths: list[str]) -> str:
    spec_dir = tmp_path / "specs" / "2026-05-29-feature"
    spec_dir.mkdir(parents=True)
    body = ["# Plan", "", "## Task breakdown", ""]
    for i, p in enumerate(paths, start=1):
        body.append(f"{i}. Update `{p}` with new behavior.")
    plan = spec_dir / "plan.md"
    plan.write_text("\n".join(body))
    os.utime(plan, (time.time(), time.time()))
    return str(plan)


def write_plan(directory, paths: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = ["# Plan", "", "## Task breakdown", ""]
    for index, path in enumerate(paths, start=1):
        body.append(f"{index}. Update `{path}` with new behavior.")
    plan = directory / "plan.md"
    plan.write_text("\n".join(body))
    os.utime(plan, (time.time(), time.time()))


def edit_payload(tool_use, tmp_path, rel: str) -> dict:
    return tool_use(
        "Edit",
        {"file_path": str(tmp_path / rel), "old_string": "a", "new_string": "b"},
        cwd=str(tmp_path),
    )
