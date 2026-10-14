from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "hooks"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_allowlists as allowlists  # noqa: E402


def test_allowlists_skip_path_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.skip_path(path)

    # Assert
    assert result is True


def test_allowlists_skip_path_test_suffix():
    # Arrange
    path = "/repo/src/foo.test.ts"

    # Act
    result = allowlists.skip_path(path)

    # Assert
    assert result is True


def test_allowlists_skip_extension_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.skip_extension(path)

    # Assert
    assert result is True


def test_allowlists_is_hot_path_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.is_hot_path(path)

    # Assert
    assert result is False


def test_allowlists_is_hot_path_crypto():
    # Arrange
    path = "/repo/src/crypto/cipher.ts"

    # Act
    result = allowlists.is_hot_path(path)

    # Assert
    assert result is True


def test_allowlists_is_framework_receiver_pattern_match():
    # Arrange
    line = "app.router.push('/home');"

    # Act
    result = allowlists.is_framework_receiver(line, None)

    # Assert
    assert result is True


def test_allowlists_is_framework_receiver_unknown_owner():
    # Arrange
    line = "myList.push(x);"

    # Act
    result = allowlists.is_framework_receiver(line, "myList")

    # Assert
    assert result is False


def test_allowlists_is_state_mgmt_filename_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.is_state_mgmt_filename(path)

    # Assert
    assert result is False


def test_allowlists_is_state_mgmt_filename_slice():
    # Arrange
    path = "/repo/src/userSlice.ts"

    # Act
    result = allowlists.is_state_mgmt_filename(path)

    # Assert
    assert result is True


def test_allowlists_is_in_state_mgmt_scope_empty_window():
    # Arrange
    window = ""
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is False
    assert label is None


def test_allowlists_is_in_state_mgmt_scope_zustand():
    # Arrange
    window = "set(produce((draft) => { draft.count += 1; }))"
    file_path = "/repo/src/store.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is True
    assert label == "zustand-produce"


def test_allowlists_is_in_state_mgmt_scope_yjs():
    # Arrange
    window = "const arr = new Y.Array(); arr.push([1]);"
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is True
    assert label == "yjs-crdt"


def test_allowlists_is_in_state_mgmt_scope_filename_fallback():
    # Arrange
    window = "items.push(x);"
    file_path = "/repo/src/userSlice.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is True
    assert label == "state-mgmt-filename"


def test_allowlists_is_param_reassign_allowed_name_yes():
    # Arrange
    name = "acc"

    # Act
    result = allowlists.is_param_reassign_allowed_name(name)

    # Assert
    assert result is True


def test_allowlists_is_param_reassign_allowed_name_no():
    # Arrange
    name = "myCustomVar"

    # Act
    result = allowlists.is_param_reassign_allowed_name(name)

    # Assert
    assert result is False
