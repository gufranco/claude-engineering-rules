from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from _lib.mutation_allowlists import (  # noqa: E402
    is_framework_receiver,
    is_state_mgmt_filename,
    skip_extension,
)


@pytest.mark.parametrize("path", ["src/a.mts", "src/b.cts", "src/c.ts"])
def test_module_typescript_extensions_are_scanned(path):
    # Arrange
    file_path = path

    # Act
    result = skip_extension(file_path)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "path",
    [
        "src/users/users.service.ts",
        "src/app/app.component.ts",
        "src/lib/datastore.ts",
        "src/lib/restore.ts",
    ],
)
def test_ordinary_modules_are_not_exempt_by_name(path):
    # Arrange
    file_path = path

    # Act
    result = is_state_mgmt_filename(file_path)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "path",
    [
        "src/store.ts",
        "src/user.store.ts",
        "src/features/cart.slice.ts",
        "src/reducer.js",
    ],
)
def test_state_management_files_stay_exempt(path):
    # Arrange
    file_path = path

    # Act
    result = is_state_mgmt_filename(file_path)

    # Assert
    assert result is True


@pytest.mark.parametrize(
    ("line", "owner"),
    [
        ("results.push(row);", "results"),
        ("errors.push(new Error('x'));", "errors"),
        ("queue.push(job);", "queue"),
        ("router.push('/a'); items.push(1);", "items"),
    ],
)
def test_local_arrays_are_not_framework_receivers(line, owner):
    # Arrange
    receiver = owner

    # Act
    result = is_framework_receiver(line, receiver)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    ("line", "owner"),
    [
        ("router.push('/a');", "router"),
        ("routerRef.current.push('/a');", None),
        ("window.dataLayer.push({ event: 'x' });", None),
    ],
)
def test_framework_receivers_stay_exempt(line, owner):
    # Arrange
    receiver = owner

    # Act
    result = is_framework_receiver(line, receiver)

    # Assert
    assert result is True
