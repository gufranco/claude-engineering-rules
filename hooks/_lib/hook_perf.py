"""Performance-budget decorator for `~/.claude/hooks/*.py` entrypoints.

Spec: `specs/2026-05-09-claude-config-state-of-art/plan.md` 1.1.6.

Wrap a hook's `main()` (or any zero-arg callable returning an exit code) with
`@with_perf_budget(budget_ms=200)`. The wrapper measures wall-clock time and
emits an `audit_log.budget_exceeded` event when the hook overruns the
budget. The hook's exit code passes through unchanged so a slow hook still
blocks or allows correctly.

Why a decorator and not a manual timer?

  - Single source of truth for budget enforcement.
  - Audit-log event has a uniform schema across hooks, so the dashboard
    aggregator (`scripts/audit_summarize.py`) can rank slow hooks.
  - Easy to disable per-hook via `CLAUDE_HOOK_PERF_DISABLE=1`.

The decorator never raises and never alters the hook's exit code.
"""

from __future__ import annotations

import functools
import os
import sys
import time
from typing import Callable, TypeVar

ExitCode = int
Wrapped = Callable[[], ExitCode]
T = TypeVar("T", bound=Wrapped)

DEFAULT_BUDGET_MS = 200


def with_perf_budget(
    budget_ms: int = DEFAULT_BUDGET_MS,
    *,
    hook_name: str | None = None,
) -> Callable[[T], T]:
    """Return a decorator that records latency vs `budget_ms`.

    `hook_name` defaults to the wrapped function's module basename so callers
    do not need to pass it explicitly. Override only when the module name
    does not match the hook (e.g., shared modules running on behalf of
    multiple hooks).
    """

    def decorator(fn: T) -> T:
        @functools.wraps(fn)
        def wrapped() -> ExitCode:
            if os.environ.get("CLAUDE_HOOK_PERF_DISABLE") == "1":
                return fn()
            start = time.monotonic()
            try:
                code = fn()
            finally:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                if elapsed_ms > budget_ms:
                    _emit_budget_exceeded(
                        hook=hook_name or _resolve_hook_name(fn),
                        elapsed_ms=elapsed_ms,
                        budget_ms=budget_ms,
                    )
            return code

        return wrapped  # type: ignore[return-value]

    return decorator


def _resolve_hook_name(fn: Callable[..., object]) -> str:
    module = getattr(fn, "__module__", "")
    if module and module != "__main__":
        return module
    main_module = sys.modules.get("__main__")
    if main_module is not None:
        path = getattr(main_module, "__file__", "") or ""
        if path:
            return os.path.basename(path).removesuffix(".py")
    return "unknown"


def _emit_budget_exceeded(*, hook: str, elapsed_ms: int, budget_ms: int) -> None:
    try:
        sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
        from _lib.audit_log import record as _record
    except ImportError:
        return
    try:
        _record(
            hook=hook,
            decision="budget_exceeded",
            latency_ms=elapsed_ms,
            budget_ms=budget_ms,
            level="warn",
        )
    except (OSError, TypeError, ValueError):
        return
