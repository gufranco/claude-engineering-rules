from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib import knowledge_notes as kn  # noqa: E402


def test_iter_notes_skips_unreadable_and_undecodable_notes(tmp_path):
    # Arrange
    wiki = tmp_path / "wiki" / "concepts"
    wiki.mkdir(parents=True)
    (wiki / "good.md").write_text("# Good\n", encoding="utf-8")
    (wiki / "binary.md").write_bytes(b"\xff\xfe\x00")
    locked = wiki / "locked.md"
    locked.write_text("# Locked\n", encoding="utf-8")
    locked.chmod(0)

    # Act
    result = [str(rel) for rel, _ in kn.iter_notes(tmp_path)]

    # Assert
    assert result == ["wiki/concepts/good.md"]
