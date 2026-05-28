#!/usr/bin/env python3
"""Tampering detection for the mutation-method-blocker hook.

Plan items 271-273 (D32). On hook startup, the wrapper computes SHA-256
of the running script and compares against `hooks/.integrity.json`.
Mismatch logs a warning to stderr but does not block execution; the
goal is detection, not enforcement (the hook still runs).

Maintenance:

    python3 hooks/_lib/hook_integrity.py --update     # regenerate baseline
    python3 hooks/_lib/hook_integrity.py --verify     # verify all hooks

Schema (`hooks/.integrity.json`):

    {
      "version": 1,
      "files": {
        "<relative-path>": "<hex-sha256>"
      }
    }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"
INTEGRITY_FILE = HOOKS_DIR / ".integrity.json"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gather_hook_files() -> list[Path]:
    return sorted(
        p for p in HOOKS_DIR.iterdir() if p.is_file() and p.suffix in {".py", ".sh"}
    )


def _load_baseline() -> dict[str, str]:
    if not INTEGRITY_FILE.exists():
        return {}
    try:
        data = json.loads(INTEGRITY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data.get("files", {}) if isinstance(data, dict) else {}


def update_baseline() -> int:
    """Regenerate the integrity manifest from the current hook files."""
    files = {str(p.relative_to(REPO_ROOT)): _hash_file(p) for p in _gather_hook_files()}
    INTEGRITY_FILE.write_text(
        json.dumps({"version": 1, "files": files}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    sys.stdout.write(f"Wrote integrity manifest for {len(files)} hook(s).\n")
    return 0


def verify_baseline() -> int:
    """Compare each hook's current hash against the manifest."""
    baseline = _load_baseline()
    if not baseline:
        sys.stderr.write(
            f"No integrity manifest at {INTEGRITY_FILE}; run --update to seed.\n"
        )
        return 1
    mismatches: list[str] = []
    missing: list[str] = []
    for relpath, expected in baseline.items():
        path = REPO_ROOT / relpath
        if not path.exists():
            missing.append(relpath)
            continue
        actual = _hash_file(path)
        if actual != expected:
            mismatches.append(f"{relpath}: expected {expected[:12]}, got {actual[:12]}")
    if mismatches or missing:
        for entry in mismatches:
            sys.stderr.write(f"MISMATCH {entry}\n")
        for entry in missing:
            sys.stderr.write(f"MISSING  {entry}\n")
        return 2
    sys.stdout.write(f"All {len(baseline)} hook(s) match manifest.\n")
    return 0


def assert_self(script_path: str | Path) -> bool:
    """Return True when the running script matches the manifest entry.

    Imported by hooks at startup to detect tampering. A mismatch logs a
    warning to stderr but does not raise; tampering detection is
    advisory, not enforcement.
    """
    baseline = _load_baseline()
    if not baseline:
        return True
    path = Path(script_path).resolve()
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return True
    expected = baseline.get(str(rel))
    if not expected:
        return True
    actual = _hash_file(path)
    if actual != expected:
        sys.stderr.write(
            f"hook_integrity: {rel} hash drifted "
            f"(expected {expected[:12]}, got {actual[:12]}). "
            "Run hooks/_lib/hook_integrity.py --update if intentional.\n"
        )
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Hook integrity manager")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--update", action="store_true", help="regenerate manifest")
    grp.add_argument("--verify", action="store_true", help="verify all hooks")
    args = parser.parse_args()
    if args.update:
        return update_baseline()
    return verify_baseline()


if __name__ == "__main__":
    sys.exit(main())
