from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
from _usag_support import CONTENT_SHA256, VanishingPath


def test_manifest_claims_reads_digests_and_sizes(hook, tmp_path: Path) -> None:
    # Arrange
    digest = "a" * 64
    body = {"artifacts": [{"accepted": [{"size": 1024, "sha256": digest}]}]}
    (tmp_path / "artifacts.manifest.json").write_text(json.dumps(body))

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == {digest}
    assert sizes == {1024}


def test_manifest_claims_tolerates_unknown_shapes(hook, tmp_path: Path) -> None:
    # Arrange
    digest = "b" * 64
    body = {"nested": [{"deeper": {"sha256": digest.upper(), "size": 7}}]}
    (tmp_path / "artifacts.manifest.json").write_text(json.dumps(body))

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == {digest}
    assert sizes == {7}


def test_manifest_claims_ignores_malformed_digest_and_size(
    hook, tmp_path: Path
) -> None:
    # Arrange
    body = {"accepted": [{"sha256": "tooshort", "size": -1}]}
    (tmp_path / "artifacts.manifest.json").write_text(json.dumps(body))

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == set()
    assert sizes == set()


def test_manifest_claims_survives_invalid_json(hook, tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "artifacts.manifest.json").write_text("{ not json")

    # Act
    digests, sizes = hook._manifest_claims(tmp_path)

    # Assert
    assert digests == set()
    assert sizes == set()


def test_manifest_claims_empty_when_no_manifest(hook, tmp_path: Path) -> None:
    # Arrange
    root = tmp_path

    # Act
    digests, sizes = hook._manifest_claims(root)

    # Assert
    assert digests == set()
    assert sizes == set()


def test_sha256_returns_none_for_unreadable_path(hook, tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "ghost.bin"

    # Act
    result = hook._sha256(path)

    # Assert
    assert result is None


def test_sha256_returns_the_known_digest(hook: ModuleType, tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "payload.bin"
    target.write_bytes(b"content")

    # Act
    result = hook._sha256(target)

    # Assert
    assert result == CONTENT_SHA256


def test_classify_returns_none_for_missing_path(hook, tmp_path: Path) -> None:
    # Arrange
    text = "ghost.bin"

    # Act
    result = hook._classify(text, tmp_path, set(), set())

    # Assert
    assert result is None


def test_classify_flags_artifact_extension(hook, tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "game.gba").write_bytes(b"rom")

    # Act
    result = hook._classify("game.gba", tmp_path, set(), set())

    # Assert
    assert result == ".gba is a user-supplied artifact extension"


def test_classify_flags_manifest_digest(hook, tmp_path: Path) -> None:
    # Arrange
    body = b"content"
    (tmp_path / "blob.dat").write_bytes(body)
    digest = CONTENT_SHA256

    # Act
    result = hook._classify("blob.dat", tmp_path, {digest}, {len(body)})

    # Assert
    assert result == f"SHA-256 {digest[:12]} is declared in the artifacts manifest"


def test_classify_ignores_size_match_with_different_content(
    hook, tmp_path: Path
) -> None:
    # Arrange
    (tmp_path / "blob.dat").write_bytes(b"xxxxxxxx")

    # Act
    result = hook._classify("blob.dat", tmp_path, {"c" * 64}, {8})

    # Assert
    assert result is None


def test_classify_accepts_absolute_paths(hook, tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "game.nds"
    target.write_bytes(b"rom")

    # Act
    result = hook._classify(str(target), tmp_path, set(), set())

    # Assert
    assert result == ".nds is a user-supplied artifact extension"


def test_classify_resolves_paths_relative_to_the_working_directory(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    workdir = tmp_path / "packages" / "emulator"
    workdir.mkdir(parents=True)
    (workdir / "game.gba").write_bytes(b"rom")
    monkeypatch.chdir(workdir)

    # Act
    result = hook._classify("game.gba", tmp_path, set(), set())

    # Assert
    assert result == ".gba is a user-supplied artifact extension"


def test_resolve_returns_none_for_missing_absolute_path(hook, tmp_path: Path) -> None:
    # Arrange
    name = str(tmp_path / "ghost.bin")

    # Act
    result = hook._resolve(name, tmp_path)

    # Assert
    assert result is None


def test_classify_survives_stat_failure_after_is_file(
    hook, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(hook, "Path", VanishingPath)

    # Act
    result = hook._classify(str(tmp_path / "blob.dat"), tmp_path, {"d" * 64}, {8})

    # Assert
    assert result is None
