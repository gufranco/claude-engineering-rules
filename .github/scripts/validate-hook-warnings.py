#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = "hooks/_lib/hook_warning.py"
USER_ONLY = re.compile(r"""["']systemMessage["']""")
ADVISORY_AUDIT = re.compile(r"""decision\s*=\s*["'](?:warn|advise)["']""")
MODEL_CHANNEL = re.compile(r"""\bemit_warning\(|["']additionalContext["']""")
EXEMPT = {
    "hooks/mutation-method-blocker.py": "logs its own scan time, no finding about the code",
}


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    line: int
    kind: str


def hook_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for pattern in ("hooks/*.py", "hooks/_lib/*.py")
        for path in root.glob(pattern)
    )


def _first_line(text: str, pattern: re.Pattern[str]) -> int:
    match = pattern.search(text)
    return text.count("\n", 0, match.start()) + 1 if match else 0


def file_findings(root: Path, relative: str) -> list[Finding]:
    if relative == HELPER or relative in EXEMPT:
        return []
    text = (root / relative).read_text(encoding="utf-8")
    found: list[Finding] = []
    if USER_ONLY.search(text):
        found = [Finding(relative, _first_line(text, USER_ONLY), "user-only channel")]
    if ADVISORY_AUDIT.search(text) and not MODEL_CHANNEL.search(text):
        line = _first_line(text, ADVISORY_AUDIT)
        found = [*found, Finding(relative, line, "silent advisory")]
    return found


def findings(root: Path) -> list[Finding]:
    return [
        finding
        for relative in hook_files(root)
        for finding in file_findings(root, relative)
    ]


def check(root: Path) -> int:
    found = findings(root)
    if not found:
        print("PASSED: every hook advisory reaches the model.")
        return 0
    for finding in found:
        print(f"{finding.path}:{finding.line}: {finding.kind}")
    print(
        f"FAILED: {len(found)} hook advisory path(s) never reach the model. Send "
        "advisories through emit_warning in hooks/_lib/hook_warning.py, which hands "
        "them to the model with the investigate instruction, and user-only notices "
        "through emit_user_notice."
    )
    return 1


def main() -> int:
    return check(REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
