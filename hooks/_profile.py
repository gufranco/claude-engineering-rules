"""Shared hook profile helper.

Provides a single source of truth for whether a hook should run based on the
active profile and the disabled-hooks list. Each hook imports `should_run`
and short-circuits at the top of its main path.

Profiles:
    minimal   - skip every advisory hook. Runs only critical security hooks
                (those listed in CRITICAL_HOOKS).
    standard  - default. All hooks run.
    strict    - all hooks run plus optional strict-only hooks may opt in
                via require_strict=True.

Per-hook bypass env vars (e.g. ALLOW_PROTECTED_BRANCH_PUSH=1) remain in force
and override profile decisions. The profile gate is consulted before per-hook
logic, so a profile=minimal short-circuits before the hook reads stdin.

Usage in a hook:

    from _profile import should_run

    if not should_run("dangerous-command-blocker"):
        sys.exit(0)
"""

from __future__ import annotations

import os

VALID_PROFILES = {"minimal", "standard", "strict"}
DEFAULT_PROFILE = "standard"

CRITICAL_HOOKS = frozenset(
    {
        "dangerous-command-blocker",
        "secret-scanner",
        "env-file-guard",
        "large-file-blocker",
        "ai-attribution-blocker",
        "internal-config-leakage",
    }
)


def _read_profile() -> str:
    raw = os.environ.get("CLAUDE_HOOK_PROFILE", "").strip().lower()
    if raw in VALID_PROFILES:
        return raw
    return DEFAULT_PROFILE


def _disabled_set() -> frozenset[str]:
    raw = os.environ.get("CLAUDE_DISABLED_HOOKS", "")
    if not raw:
        return frozenset()
    parts = (item.strip() for item in raw.split(","))
    return frozenset(p for p in parts if p)


def should_run(hook_name: str, *, require_strict: bool = False) -> bool:
    """Return True when the hook should execute under the active profile.

    Args:
        hook_name: stable identifier matching the hook filename without
            the `.py` extension (e.g. "dangerous-command-blocker").
        require_strict: when True, the hook only runs under the strict
            profile. Used by hooks that are too noisy for daily work.
    """
    if hook_name in _disabled_set():
        return False

    profile = _read_profile()

    if require_strict:
        return profile == "strict"

    if profile == "minimal":
        return hook_name in CRITICAL_HOOKS

    return True
