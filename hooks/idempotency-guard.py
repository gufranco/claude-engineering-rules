#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.guard_runner import GuardSpec, run_guard  # noqa: E402
from _lib.idempotency_detectors import applies_to, find  # noqa: E402

WHY = (
    "An operation that is safe to run once but changes or fails on the second run\n"
    "turns every retry, re-install and re-apply into an incident: scripts die on a\n"
    "half-finished machine, rc files grow a duplicate line per run, Terraform plans\n"
    "never converge, and a retried send writes the message twice.\n"
    "See ~/.claude/standards/idempotency.md."
)

FIX = (
    "  - Shell: `mkdir -p`, `ln -sfn`, `grep -qxF line file || echo line >> file`,\n"
    "    `typeset -U path` in zsh, `command -v tool ||` before installing.\n"
    "  - Terraform: `plantimestamp()`, `time_static`, `random_uuid`, provider\n"
    "    resources over provisioners, and named attributes in `ignore_changes`.\n"
    "  - Kafka: keep `enable.idempotence` on, with `acks=all`.\n"
    "  - BullMQ: keep completed jobs for the dedup window, `removeOnComplete: { age }`."
)

BYPASS_WHEN = (
    "The non-idempotent form is the contract, such as `mkdir` used as an atomic lock\n"
    "or a provisioner with no provider equivalent. Prefer the tool's own suppression\n"
    "comment on that line, such as `# shellcheck disable=` or `# tflint-ignore`."
)

SPEC = GuardSpec(
    hook_id="idempotency-guard",
    env_disable="IDEMPOTENCY_GUARD_DISABLE",
    rule_anchor="standards/idempotency.md#per-language-checks",
    intro="Operations that are not safe to repeat:",
    why=WHY,
    fix=FIX,
    bypass_when=BYPASS_WHEN,
    safety="re-runs and retries fail or duplicate their effect.",
    reason="non-idempotent operation",
    applies_to=applies_to,
    find=find,
)


if __name__ == "__main__":
    sys.exit(run_guard(SPEC))
