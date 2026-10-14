from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.analyzer_runs import ANALYZERS  # noqa: E402

STANDARD = REPO_ROOT / "standards" / "immutability.md"
ROW = re.compile(
    r"^\| (?P<language>[^|]+?) \| `(?P<tool>[^`]+)` \| `(?P<rule>[^`]+)` \| (?P<severity>Blocks|Warns) \|$"
)


def _documented() -> frozenset[tuple[str, str, str]]:
    text = STANDARD.read_text(encoding="utf-8")
    section = text.split("## Analyzer Catalog", 1)[1].split("\n## ", 1)[0]
    return frozenset(
        (m.group("tool"), m.group("rule"), m.group("severity"))
        for m in (ROW.match(line) for line in section.splitlines())
        if m is not None
    )


def _implemented() -> frozenset[tuple[str, str, str]]:
    return frozenset(
        (analyzer.name, rule, severity)
        for analyzer in ANALYZERS.values()
        for rules, severity in (
            (analyzer.blocking, "Blocks"),
            (analyzer.advisory, "Warns"),
        )
        for rule in rules
    )


def test_catalog_matches_the_analyzer_rules():
    # Arrange
    implemented = _implemented()

    # Act
    documented = _documented()

    # Assert
    assert (implemented - documented, documented - implemented) == (
        frozenset(),
        frozenset(),
    )
