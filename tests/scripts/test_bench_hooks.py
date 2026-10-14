from __future__ import annotations

from pathlib import Path

import pytest
from faker import Faker

from _helpers.bench_hooks_support import (
    _allow_hook,
    _write_hook,
    bench_hooks,
)


def test_percentile_empty_returns_zero() -> None:
    # Arrange
    values: list[float] = []

    # Act
    result = bench_hooks._percentile(values, 0.5)

    # Assert
    assert result == 0.0


def test_percentile_single_value_returns_value() -> None:
    # Arrange
    values = [42.5]

    # Act
    result = bench_hooks._percentile(values, 0.99)

    # Assert
    assert result == 42.5


def test_percentile_p50_of_three() -> None:
    # Arrange
    values = [1.0, 2.0, 3.0]

    # Act
    result = bench_hooks._percentile(values, 0.5)

    # Assert
    assert result == 2.0


def test_percentile_interpolates_between_ranks() -> None:
    # Arrange
    values = [10.0, 20.0, 30.0, 40.0]

    # Act
    result = bench_hooks._percentile(values, 0.5)

    # Assert
    assert result == 25.0


def test_percentile_p95_picks_upper_rank() -> None:
    # Arrange
    values = [float(i) for i in range(1, 11)]

    # Act
    result = bench_hooks._percentile(values, 0.95)

    # Assert
    assert result == pytest.approx(9.55)


def test_percentile_p99_max_when_only_one_above_rank() -> None:
    # Arrange
    values = [1.0, 2.0]

    # Act
    result = bench_hooks._percentile(values, 0.99)

    # Assert
    assert result == pytest.approx(1.99)


def test_discover_hooks_returns_sorted_python_files(hooks_dir: Path) -> None:
    # Arrange
    _write_hook(hooks_dir, "z-last", _allow_hook())
    _write_hook(hooks_dir, "a-first", _allow_hook())
    _write_hook(hooks_dir, "m-mid", _allow_hook())

    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))

    # Assert
    assert [Path(p).name for p in discovered] == ["a-first.py", "m-mid.py", "z-last.py"]


def test_discover_hooks_skips_underscore_prefixed_files(hooks_dir: Path) -> None:
    # Arrange
    _write_hook(hooks_dir, "_helper", _allow_hook())
    _write_hook(hooks_dir, "real", _allow_hook())

    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))

    # Assert
    assert [Path(p).name for p in discovered] == ["real.py"]


def test_discover_hooks_skips_non_python_files(hooks_dir: Path) -> None:
    # Arrange
    (hooks_dir / "config.txt").write_text("data", encoding="utf-8")
    (hooks_dir / "README.md").write_text("docs", encoding="utf-8")
    _write_hook(hooks_dir, "real", _allow_hook())

    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))

    # Assert
    assert [Path(p).name for p in discovered] == ["real.py"]


def test_discover_hooks_skips_directories_with_py_suffix(
    hooks_dir: Path,
) -> None:
    # Arrange
    (hooks_dir / "fake.py").mkdir()
    _write_hook(hooks_dir, "real", _allow_hook())

    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))

    # Assert
    assert [Path(p).name for p in discovered] == ["real.py"]


def test_discover_hooks_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "does-not-exist"

    # Act
    discovered = bench_hooks.discover_hooks(str(missing))

    # Assert
    assert discovered == []


def test_discover_hooks_returns_empty_for_empty_dir(hooks_dir: Path) -> None:
    # Arrange
    argument = str(hooks_dir)

    # Act
    discovered = bench_hooks.discover_hooks(argument)

    # Assert
    assert discovered == []


def test_hook_basename_strips_dotpy(faker: Faker) -> None:
    # Arrange
    name = faker.word()
    path = f"/{faker.word()}/hooks/{name}.py"

    # Act
    result = bench_hooks._hook_basename(path)

    # Assert
    assert result == name


def test_hook_basename_returns_basename_for_no_extension(faker: Faker) -> None:
    # Arrange
    name = faker.word()
    path = f"/{faker.word()}/hooks/{name}"

    # Act
    result = bench_hooks._hook_basename(path)

    # Assert
    assert result == name
