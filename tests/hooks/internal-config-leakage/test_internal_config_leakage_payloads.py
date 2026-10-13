from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib import internal_config_leakage_payloads as payloads  # noqa: E402


def test_referenced_files_strip_the_at_prefix_and_deduplicate() -> None:
    # Arrange
    cmd = "gh api x --input @a.json -F body=@b.md --body-file=a.json"

    # Act
    paths = payloads.extract_referenced_files(cmd)

    # Assert
    assert paths == ["a.json", "b.md"]


def test_text_blocks_list_top_level_fields_before_comment_bodies() -> None:
    # Arrange
    content = json.dumps(
        {"title": "T", "body": "B", "comments": [{"body": "C"}, "skip", {"body": " "}]}
    )

    # Act
    blocks = payloads.extract_publishing_text_blocks(content)

    # Assert
    assert blocks == [("body", "B"), ("title", "T"), ("comments[0].body", "C")]


def test_a_pull_request_shape_counts_as_publishing_json() -> None:
    # Arrange
    content = json.dumps({"title": "T", "draft": True})

    # Act
    publishing = payloads.looks_like_publishing_json(content)

    # Assert
    assert publishing is True


def test_a_missing_payload_file_reads_as_none(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "absent.json"

    # Act
    content = payloads.read_payload_file(str(missing))

    # Assert
    assert content is None
