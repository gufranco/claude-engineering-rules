from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
LOOKUP_SOURCE = REPO_ROOT / "hooks" / "_lib" / "mutation_fix_lookup.py"
TABLE_NAME = "mutation_fix_suggestions.json"


def _install_lookup(hook_dir: Path) -> Path:
    lib_dir = hook_dir / "_lib"
    lib_dir.mkdir(parents=True)
    target = lib_dir / "mutation_fix_lookup.py"
    shutil.copyfile(LOOKUP_SOURCE, target)
    return target


def _import_lookup(module_path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(code: str, fix: str, category_code: str, category_fix: str) -> str:
    return json.dumps(
        {
            "_meta": {},
            "exact": {"widget.push": {"code": code, "category": "widget", "fix": fix}},
            "by_category": {"widget": {"code": category_code, "fix": category_fix}},
        }
    )


def test_missing_table_yields_no_suggestion(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    module_path = _install_lookup(tmp_path)

    # Act
    lookup = _import_lookup(module_path, f"lookup_{faker.uuid4().replace('-', '')}")

    # Assert
    assert (
        lookup.suggest_fix("array.push"),
        lookup.detector_code_to_mmb("array.push"),
    ) == (
        None,
        None,
    )


def test_invalid_json_table_yields_no_suggestion(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    module_path = _install_lookup(tmp_path)
    (tmp_path / TABLE_NAME).write_text(faker.sentence() + " {", encoding="utf-8")

    # Act
    lookup = _import_lookup(module_path, f"lookup_{faker.uuid4().replace('-', '')}")

    # Assert
    assert (
        lookup.suggest_fix("array.push"),
        lookup.detector_code_to_mmb("array.push"),
    ) == (
        None,
        None,
    )


def test_table_beside_the_module_drives_exact_suggestions(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    module_path = _install_lookup(tmp_path)
    code = f"MMB{faker.random_int(100, 999)}"
    fix = faker.sentence()
    (tmp_path / TABLE_NAME).write_text(
        _table(code, fix, f"MMB{faker.random_int(100, 999)}", faker.sentence()),
        encoding="utf-8",
    )

    # Act
    lookup = _import_lookup(module_path, f"lookup_{faker.uuid4().replace('-', '')}")

    # Assert
    assert (
        lookup.suggest_fix("widget.push"),
        lookup.detector_code_to_mmb("widget.push"),
    ) == (
        fix,
        code,
    )


def test_table_beside_the_module_drives_category_fallback(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    module_path = _install_lookup(tmp_path)
    category_code = f"MMB{faker.random_int(100, 999)}"
    category_fix = faker.sentence()
    (tmp_path / TABLE_NAME).write_text(
        _table(
            f"MMB{faker.random_int(100, 999)}",
            faker.sentence(),
            category_code,
            category_fix,
        ),
        encoding="utf-8",
    )
    detector = f"widget.{faker.word()}"

    # Act
    lookup = _import_lookup(module_path, f"lookup_{faker.uuid4().replace('-', '')}")

    # Assert
    assert (lookup.suggest_fix(detector), lookup.detector_code_to_mmb(detector)) == (
        category_fix,
        category_code,
    )


def test_load_table_keeps_the_first_loaded_table(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    module_path = _install_lookup(tmp_path)
    table_path = tmp_path / TABLE_NAME
    first_fix = faker.sentence()
    table_path.write_text(
        _table("MMB101", first_fix, "MMB100", faker.sentence()), encoding="utf-8"
    )
    lookup = _import_lookup(module_path, f"lookup_{faker.uuid4().replace('-', '')}")
    table_path.write_text(
        _table("MMB201", faker.sentence(), "MMB200", faker.sentence()),
        encoding="utf-8",
    )

    # Act
    lookup._load_table()

    # Assert
    assert lookup.suggest_fix("widget.push") == first_fix


def test_detector_code_to_mmb_returns_none_for_empty(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    module_path = _install_lookup(tmp_path)
    (tmp_path / TABLE_NAME).write_text(
        _table("MMB101", faker.sentence(), "MMB100", faker.sentence()),
        encoding="utf-8",
    )
    lookup = _import_lookup(module_path, f"lookup_{faker.uuid4().replace('-', '')}")

    # Act
    result = lookup.detector_code_to_mmb("")

    # Assert
    assert result is None
