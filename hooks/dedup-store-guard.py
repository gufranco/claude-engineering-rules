#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.dedup_detectors import find, is_dedup_source  # noqa: E402
from _lib.guard_runner import Edit, Finding, GuardSpec, run_guard  # noqa: E402

WHY = (
    "A process-local collection is empty after every deploy, every crash, and on\n"
    "every replica that did not handle the first delivery. The duplicate the code\n"
    "appears to prevent is processed anyway, and the failure only appears under\n"
    "the conditions that matter. See ~/.claude/standards/idempotency.md, Storage."
)

FIX = (
    "  - Insert the dedup key into the same database transaction as the business\n"
    "    write, with a unique constraint on the key: `INSERT ... ON CONFLICT DO\n"
    "    NOTHING`, Prisma or Drizzle upsert, Rails `create_or_find_by`, JPA with a\n"
    "    unique index created by a migration. A conflict means the work happened.\n"
    "  - Or Redis with persistence: `SET key 1 NX EX <ttl>`; a null reply is a duplicate.\n"
    "  - The TTL must exceed the producer's maximum redelivery window, which is\n"
    "    commonly three days for payment webhooks and 5 minutes for SQS FIFO.\n"
    "  - Go `singleflight`, Elixir ETS and Clojure atoms die with the process too."
)

BYPASS_WHEN = (
    "The collection coordinates work inside one process rather than recording that\n"
    "a business effect already happened, such as a single-flight promise map."
)


def _find(edit: Edit) -> tuple[Finding, ...]:
    return find(edit.path, edit.text)


SPEC = GuardSpec(
    hook_id="dedup-store-guard",
    env_disable="DEDUP_STORE_DISABLE",
    rule_anchor="standards/idempotency.md#storage",
    intro="Deduplication state held in process memory:",
    why=WHY,
    fix=FIX,
    bypass_when=BYPASS_WHEN,
    safety="duplicate side effects ship, and only under restart or scale-out.",
    reason="in-memory dedup store",
    applies_to=is_dedup_source,
    find=_find,
)


if __name__ == "__main__":
    sys.exit(run_guard(SPEC))
