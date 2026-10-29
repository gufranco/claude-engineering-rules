#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.guard_runner import Edit, Finding, GuardSpec, run_guard  # noqa: E402
from _lib.workflow_rules import find, is_workflow  # noqa: E402

WHY = (
    "CI is the one gate every change passes, so its defaults decide speed, cost\n"
    "and supply-chain exposure for the whole project. A moving runner label\n"
    "changes the image without a commit, a needless macOS runner is slow and\n"
    "costly, a tag on a third-party action can be repointed by its owner, npm,\n"
    "npx and pip bypass the committed pnpm and uv lockfiles, a run without a\n"
    "concurrency group keeps billing after a newer push superseded it, and a\n"
    "cancelled release stops halfway through publishing."
)

FIX = (
    "  - runs-on: the newest GA Ubuntu LTS label, such as ubuntu-26.04. A job\n"
    "    that needs macOS, such as a Homebrew tap, an Xcode build or a project\n"
    "    that only runs on macOS, uses a pinned macOS label.\n"
    "  - uses: actions/* and github/* on a version tag; every other action on a\n"
    "    40-character commit SHA with the version in a trailing comment.\n"
    "  - Install with `corepack pnpm install --frozen-lockfile` or\n"
    "    `uv sync --locked`, and run tools with `pnpm exec` or `uv run`.\n"
    "  - A push or pull_request workflow sets a top-level concurrency group with\n"
    "    cancel-in-progress: true. A release runs in its own workflow, on\n"
    "    workflow_run, release, repository_dispatch or a tag push, with\n"
    "    cancel-in-progress: false.\n"
    "  - step-security/harden-runner is the first step of every job."
)

BYPASS_WHEN = (
    "The guard misreads this workflow, such as a trigger block it cannot parse,\n"
    "and the owner approved the exception."
)


def _find(edit: Edit) -> tuple[Finding, ...]:
    return find(edit.path, edit.text, edit.full_file)


SPEC = GuardSpec(
    hook_id="workflow-guard",
    env_disable="WORKFLOW_GUARD_DISABLE",
    rule_anchor="standards/infrastructure.md#ci-workflow-defaults",
    intro="GitHub Actions workflow departs from the CI defaults:",
    why=WHY,
    fix=FIX,
    bypass_when=BYPASS_WHEN,
    safety="CI drifts onto moving images, mutable actions and unlocked installs.",
    reason="workflow CI defaults",
    applies_to=is_workflow,
    find=_find,
)


if __name__ == "__main__":
    sys.exit(run_guard(SPEC))
