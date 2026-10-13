from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from _helpers.cov_env import apply_coverage_env

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "validate-patterns.py"

BLOCKER = """
SAFE_CLEANUP = [("dist", "remove dist")]
CATASTROPHIC = [(r"\\bmkfs\\b", "format filesystem")]
CRITICAL_PATHS = [(FORCE_PUSH_LONG, "use lease"), (r"\\bdropdb\\b", "drop")]
SUSPICIOUS = [(r"\\bsudo\\b", "sudo")]
"""


@pytest.fixture(scope="module")
def validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_validate_patterns", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, blocker: str, lib: str) -> tuple[Path, Path]:
    blocker_path = tmp_path / "blocker.py"
    blocker_path.write_text(blocker, encoding="utf-8")
    lib_path = tmp_path / "lib.py"
    lib_path.write_text(lib, encoding="utf-8")
    return blocker_path, lib_path


def test_the_repository_patterns_are_valid() -> None:
    # Arrange
    argv = [sys.executable, str(SCRIPT)]

    # Act
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 0
    assert proc.stdout.splitlines()[-1] == "PASSED: All patterns valid, no duplicates"


def test_a_named_pattern_from_the_lib_is_validated(
    validator: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, 'FORCE_PUSH_LONG = r"--force\\b"\n')

    # Act
    errors, total = validator.validate(str(blocker), str(lib))

    # Assert
    assert (errors, total) == ([], 5)


def test_a_malformed_lib_constant_fails(validator: ModuleType, tmp_path: Path) -> None:
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, 'FORCE_PUSH_LONG = r"--force(unclosed"\n')

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert [error.split(":")[0] for error in errors] == [
        "  CRITICAL_PATHS",
        "  git_invocation.FORCE_PUSH_LONG",
    ]


def test_a_name_the_lib_does_not_define_fails(
    validator: ModuleType, tmp_path: Path
) -> None:
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, 'OTHER = r"x"\n')

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors == ["  CRITICAL_PATHS: unresolved pattern name FORCE_PUSH_LONG"]


def test_a_lib_that_cannot_load_fails(validator: ModuleType, tmp_path: Path) -> None:
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, "import re\nre.compile('(')\n")

    # Act
    errors, total = validator.validate(str(blocker), str(lib))

    # Assert
    assert (errors, total) == (
        [
            f"  could not load {lib}: PatternError: missing ), "
            "unterminated subpattern at position 0"
        ],
        0,
    )


def test_a_duplicate_across_lists_fails(validator: ModuleType, tmp_path: Path) -> None:
    # Arrange
    blocker_source = BLOCKER.replace('r"\\bsudo\\b"', 'r"\\bmkfs\\b"')
    blocker, lib = _write(tmp_path, blocker_source, 'FORCE_PUSH_LONG = r"--force"\n')

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors == [
        "  Duplicate pattern in SUSPICIOUS (also in CATASTROPHIC): '\\\\bmkfs\\\\b'"
    ]


def test_a_missing_required_list_fails(validator: ModuleType, tmp_path: Path) -> None:
    # Arrange
    blocker, lib = _write(
        tmp_path, 'CATASTROPHIC = [(r"x", "x")]\n', 'FORCE_PUSH_LONG = r"y"\n'
    )

    # Act
    errors, _total = validator.validate(str(blocker), str(lib))

    # Assert
    assert errors == [
        "  Required pattern list(s) missing from blocker: "
        "['CRITICAL_PATHS', 'SAFE_CLEANUP', 'SUSPICIOUS']"
    ]


def test_every_table_shape_is_read(validator: ModuleType, tmp_path: Path) -> None:
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


INVALID_FORCE = (
    "invalid regex: '(--force' -- missing ), unterminated subpattern at position 0"
)


@pytest.mark.parametrize(
    ("lib_source", "code", "tail"),
    [
        (
            'FORCE_PUSH_LONG = r"--force"\n',
            0,
            ["Total patterns: 5", "PASSED: All patterns valid, no duplicates"],
        ),
        (
            'FORCE_PUSH_LONG = r"(--force"\n',
            1,
            [
                "Total patterns: 5",
                "",
                "FAILED: 2 error(s) found:",
                "",
                f"  CRITICAL_PATHS: {INVALID_FORCE}",
                f"  git_invocation.FORCE_PUSH_LONG: {INVALID_FORCE}",
            ],
        ),
    ],
)
def test_main_exits_with_the_verdict(
    validator: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    lib_source: str,
    code: int,
    tail: list[str],
) -> None:
    # Arrange
    blocker, lib = _write(tmp_path, BLOCKER, lib_source)
    monkeypatch.setattr(validator, "BLOCKER_PATH", str(blocker))
    monkeypatch.setattr(validator, "LIB_PATH", str(lib))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        validator.main()

    # Assert
    assert exit_info.value.code == code
    assert capsys.readouterr().out.splitlines()[-len(tail) :] == tail


def test_main_fails_when_a_source_file_is_missing(
    validator: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    absent = tmp_path / "absent.py"
    monkeypatch.setattr(validator, "BLOCKER_PATH", str(absent))

    # Act
    with pytest.raises(SystemExit) as exit_info:
        validator.main()

    # Assert
    assert exit_info.value.code == 1
    assert capsys.readouterr().out == f"{absent} not found\n"
