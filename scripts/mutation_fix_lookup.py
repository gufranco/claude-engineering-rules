"""Fix-suggestion lookup table for the mutation-method-blocker hook.

Loads `~/.claude/hooks/mutation_fix_suggestions.json` once at import time.
The JSON is keyed by detector tag (`array.push`, `collection.map.set`, ...)
with a category-prefix fallback so dynamic codes like `date.setMonth` and
`typed-array.fill` resolve via the `date.setter` / `typed-array` entries.

Public API:

    suggest_fix(detector_code: str, line_text: str = "") -> str | None
    fix_suggestions_enabled() -> bool

When the env var `MUTATION_METHOD_FIX_SUGGESTIONS=0` is set, the helper
returns `None` so detectors fall back to their hard-coded fix strings.
This is useful for benchmarking the suggestion overhead and for downstream
agents that prefer raw detector tags without prose.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Final

_HOOK_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "hooks"
_FIX_TABLE_PATH: Final[Path] = _HOOK_DIR / "mutation_fix_suggestions.json"

_TABLE: dict[str, Any] = {}
_EXACT: dict[str, dict[str, str]] = {}
_BY_CATEGORY: dict[str, dict[str, str]] = {}


def _load_table() -> None:
    """Populate module-level lookup dicts. Safe to call repeatedly."""
    global _TABLE, _EXACT, _BY_CATEGORY
    if _TABLE:
        return
    try:
        raw = _FIX_TABLE_PATH.read_text(encoding="utf-8")
    except OSError:
        _TABLE = {"_meta": {}, "exact": {}, "by_category": {}}
        _EXACT = {}
        _BY_CATEGORY = {}
        return
    try:
        _TABLE = json.loads(raw)
    except json.JSONDecodeError:
        _TABLE = {"_meta": {}, "exact": {}, "by_category": {}}
    _EXACT = _TABLE.get("exact", {}) or {}
    _BY_CATEGORY = _TABLE.get("by_category", {}) or {}


_load_table()


def fix_suggestions_enabled() -> bool:
    """Return False when the env var disables fix suggestions."""
    val = os.environ.get("MUTATION_METHOD_FIX_SUGGESTIONS", "1")
    return val not in ("0", "false", "False", "FALSE", "no", "off")


def tc39_stage_filter() -> int:
    """Return the minimum TC39 stage required for a suggestion to surface.

    Default `4` shows only Stage 4 (shipped) features. Setting the env var
    `MUTATION_METHOD_TC39_STAGE_FILTER=3` opts into Stage 3 entries.
    Setting `=2` opts into Stage 2 hack-stage entries. Values below `2`
    are clamped to `2`; values above `4` are clamped to `4`.

    Pre-Stage-4 suggestions are prefixed with a proposal-volatility
    warning so consumers (CI, IDE) can highlight them.
    """
    raw = os.environ.get("MUTATION_METHOD_TC39_STAGE_FILTER", "4")
    try:
        val = int(raw)
    except ValueError:
        return 4
    if val < 2:
        return 2
    if val > 4:
        return 4
    return val


def _entry_stage(entry: dict[str, Any]) -> int:
    """Return the TC39 stage for an entry. Stage 4 when unspecified."""
    stage = entry.get("stage")
    if isinstance(stage, int) and 1 <= stage <= 4:
        return stage
    return 4


def _category_lookup(detector_code: str) -> dict[str, str] | None:
    """Resolve a detector tag to a category entry.

    Tries longest prefix first so `date.setter` wins over `date` for a code
    like `date.setMonth`, and `typed-array` wins for `typed-array.fill`.
    """
    if not detector_code:
        return None
    if "date.set" in detector_code and "date.setter" in _BY_CATEGORY:
        return _BY_CATEGORY["date.setter"]
    parts = detector_code.split(".")
    for cut in range(len(parts), 0, -1):
        prefix = ".".join(parts[:cut])
        if prefix in _BY_CATEGORY:
            return _BY_CATEGORY[prefix]
    return None


def suggest_fix(detector_code: str, line_text: str = "") -> str | None:
    """Return the fix suggestion for a detector code, or None when disabled.

    Resolution order:
      1. Env-var gate (`MUTATION_METHOD_FIX_SUGGESTIONS=0` short-circuits to None).
      2. Stage filter (`MUTATION_METHOD_TC39_STAGE_FILTER`): entries above
         the configured max stage return None so unstable proposals do not
         appear in suggestions by default.
      3. Exact match in the `exact` table.
      4. Category prefix match in the `by_category` table.
      5. None (caller falls back to its hard-coded fix string).
    """
    if not fix_suggestions_enabled():
        return None
    if not detector_code:
        return None
    min_stage = tc39_stage_filter()
    exact = _EXACT.get(detector_code)
    if exact:
        entry_stage = _entry_stage(exact)
        if entry_stage < min_stage:
            return None
        fix = exact.get("fix")
        if entry_stage < 4 and fix:
            return f"[Stage {entry_stage} proposal, semantics may evolve] {fix}"
        return fix
    category = _category_lookup(detector_code)
    if category:
        entry_stage = _entry_stage(category)
        if entry_stage < min_stage:
            return None
        fix = category.get("fix")
        if entry_stage < 4 and fix:
            return f"[Stage {entry_stage} proposal, semantics may evolve] {fix}"
        return fix
    return None


def detector_code_to_mmb(detector_code: str) -> str | None:
    """Return the stable MMB code for a detector tag, or None."""
    if not detector_code:
        return None
    exact = _EXACT.get(detector_code)
    if exact:
        return exact.get("code")
    category = _category_lookup(detector_code)
    if category:
        return category.get("code")
    return None
