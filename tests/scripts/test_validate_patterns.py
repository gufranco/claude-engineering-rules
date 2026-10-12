from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "validate-patterns.py"

BLOCKER = """
SAFE_CLEANUP = [("dist", "remove dist")]
CATASTROPHIC = [(r"\\bmkfs\\b", "format filesystem")]
CRITICAL_PATHS = [(FORCE_PUSH_LONG, "use lease"), (r"\\bdropdb\\b", "drop")]
SUSPICIOUS = [(r"\\bsudo\\b", "sudo")]
"""


@pytest.fixture(scope="module")
def validator():
    spec = importlib.util.spec_from_file_location("_validate_patterns", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, blocker: str, lib: str) -> tuple[Path, Path]:
    blocker_path = tmp_path / "blocker.py"
    blocker_path.write_text(blocker, encoding="utf-8")
    lib_path = tmp_path / "lib.py"
    lib_path.write_text(lib, encoding="utf-8")
    return blocker_path, lib_path


def test_the_repository_patterns_are_valid():
    # Arrange
    argv = [sys.executable, str(SCRIPT)]

    # Act
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert "PASSED: All patterns valid, no duplicates" in proc.stdout
    assert "git_invocation constants:" in proc.stdout


def test_a_named_pattern_from_the_lib_is_validated(validator, tmp_path):
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, 'FORCE_PUSH_LONG = r"--force\\b"\n')

    # Act
    errors, total = validator.validate(str(blocker), str(lib))

    # Assert
    assert (errors, total) == ([], 5)


def test_a_malformed_lib_constant_fails(validator, tmp_path):
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, 'FORCE_PUSH_LONG = r"--force(unclosed"\n')

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert [error.split(":")[0] for error in errors] == [
        "  CRITICAL_PATHS",
        "  git_invocation.FORCE_PUSH_LONG",
    ]


def test_a_name_the_lib_does_not_define_fails(validator, tmp_path):
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, 'OTHER = r"x"\n')

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors == ["  CRITICAL_PATHS: unresolved pattern name FORCE_PUSH_LONG"]


def test_a_lib_that_cannot_load_fails(validator, tmp_path):
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, "import re\nre.compile('(')\n")

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors[0].startswith("  could not load")


def test_a_duplicate_across_lists_fails(validator, tmp_path):
    # Arrange
    blocker_source = BLOCKER.replace('r"\\bsudo\\b"', 'r"\\bmkfs\\b"')
    blocker, lib = _write(tmp_path, blocker_source, 'FORCE_PUSH_LONG = r"--force"\n')

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors == [
        "  Duplicate pattern in SUSPICIOUS (also in CATASTROPHIC): '\\\\bmkfs\\\\b'"
    ]


def test_a_missing_required_list_fails(validator, tmp_path):
    # Arrange
    blocker, lib = _write(
        tmp_path, 'CATASTROPHIC = [(r"x", "x")]\n', 'FORCE_PUSH_LONG = r"y"\n'
    )

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors[0].startswith("  Required pattern list(s) missing from blocker:")


def test_every_table_shape_is_read(validator, tmp_path):
    # Arrange
    blocker_source = (
        BLOCKER.replace("SUSPICIOUS =", "SUSPICIOUS: list[tuple[str, str]] =")
        + 'EXTRA = [r"\\bshred\\b"]\nlowercase = ["ignored"]\nLIMIT = 3\n'
        + "A, B = 1, 2\nEMPTY = []\n"
    )
    blocker, lib = _write(tmp_path, blocker_source, 'FORCE_PUSH_LONG = r"--force"\n')

    # Act
    errors, total = validator.validate(str(blocker), str(lib))

    # Assert
    assert (errors, total) == ([], 6)


@pytest.mark.parametrize(
    ("lib_source", "code", "verdict"),
    [
        ('FORCE_PUSH_LONG = r"--force"\n', 0, "PASSED"),
        ('FORCE_PUSH_LONG = r"(--force"\n', 1, "FAILED: 2 error(s) found"),
    ],
)
def test_main_exits_with_the_verdict(
    validator, tmp_path, monkeypatch, capsys, lib_source, code, verdict
):
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, lib_source)
    monkeypatch.setattr(validator, "BLOCKER_PATH", str(blocker))
    monkeypatch.setattr(validator, "LIB_PATH", str(lib))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        validator.main()

    # Assert
    assert exit_info.value.code == code
    assert verdict in capsys.readouterr().out


def test_main_fails_when_a_source_file_is_missing(validator, tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(validator, "BLOCKER_PATH", str(tmp_path / "absent.py"))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        validator.main()

    # Assert
    assert exit_info.value.code == 1
