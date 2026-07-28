"""Tests for `scripts/hook_contract_lint.py`.
The linter walks a hooks directory and emits Finding objects per file. Tests
build synthetic hook directories under `tmp_path` so the suite never depends
on the live `~/.claude/hooks/` tree.
"""

from __future__ import annotations
import io
import json
import sys
import textwrap
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import hook_contract_lint  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    """Empty directory the tests fill with synthetic hook files."""
    target = tmp_path / "hooks"
    target.mkdir()
    return target


def _write_hook(directory: Path, name: str, source: str) -> Path:
    path = directory / f"{name}.py"
    path.write_text(textwrap.dedent(source).lstrip() + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# _hook_basename
# --------------------------------------------------------------------------- #
def test_hook_basename_strips_py_extension():
    path = "/tmp/hooks/secret-scanner.py"
    result = hook_contract_lint._hook_basename(path)
    assert result == "secret-scanner"


def test_hook_basename_handles_no_extension():
    path = "/tmp/hooks/script"
    result = hook_contract_lint._hook_basename(path)
    assert result == "script"


# --------------------------------------------------------------------------- #
# _iter_hook_files
# --------------------------------------------------------------------------- #
def test_iter_hook_files_returns_sorted_python_files(hooks_dir: Path):
    _write_hook(hooks_dir, "zebra", "import sys\n")
    _write_hook(hooks_dir, "alpha", "import sys\n")
    (hooks_dir / "ignore.txt").write_text("noop", encoding="utf-8")
    (hooks_dir / "_helper").write_text("noop", encoding="utf-8")  # underscore prefix
    paths = list(hook_contract_lint._iter_hook_files(str(hooks_dir)))
    assert [Path(p).name for p in paths] == ["alpha.py", "zebra.py"]


def test_iter_hook_files_skips_underscore_prefixed_files(hooks_dir: Path):
    _write_hook(hooks_dir, "_internal", "import sys\n")
    _write_hook(hooks_dir, "public", "import sys\n")
    paths = list(hook_contract_lint._iter_hook_files(str(hooks_dir)))
    assert [Path(p).name for p in paths] == ["public.py"]


def test_iter_hook_files_returns_empty_for_missing_dir(tmp_path: Path):
    missing = tmp_path / "no-such-dir"
    paths = list(hook_contract_lint._iter_hook_files(str(missing)))
    assert paths == []


def test_iter_hook_files_skips_subdirectories(hooks_dir: Path):
    nested = hooks_dir / "nested.py"
    nested.mkdir()  # a directory named like a python file should be skipped
    _write_hook(hooks_dir, "real", "import sys\n")
    paths = list(hook_contract_lint._iter_hook_files(str(hooks_dir)))
    assert [Path(p).name for p in paths] == ["real.py"]


# --------------------------------------------------------------------------- #
# _read_source
# --------------------------------------------------------------------------- #
def test_read_source_returns_file_content(hooks_dir: Path):
    path = _write_hook(hooks_dir, "demo", "print('hi')")
    source = hook_contract_lint._read_source(str(path))
    assert source.startswith("print('hi')")


def test_read_source_returns_empty_on_missing_file(tmp_path: Path):
    missing = tmp_path / "nope.py"
    source = hook_contract_lint._read_source(str(missing))
    assert source == ""


# --------------------------------------------------------------------------- #
# _collect_imports
# --------------------------------------------------------------------------- #
def test_collect_imports_captures_top_level_imports():
    source = textwrap.dedent(
        """
        import os
        import sys
        from hook_io import block, allow
        from collections.abc import Iterable
        """
    ).lstrip()
    tree = hook_contract_lint._parse_module(source)
    assert tree is not None
    imports = hook_contract_lint._collect_imports(tree)
    assert {"os", "sys", "hook_io", "collections"} <= imports


def test_collect_imports_handles_relative_imports():
    source = textwrap.dedent(
        """
        from . import sibling
        """
    ).lstrip()
    tree = hook_contract_lint._parse_module(source)
    assert tree is not None
    imports = hook_contract_lint._collect_imports(tree)
    assert imports == set()


# --------------------------------------------------------------------------- #
# _find_sys_exit_two_lines
# --------------------------------------------------------------------------- #
def test_find_sys_exit_two_lines_collects_calls():
    source = textwrap.dedent(
        """
        import sys
        if True:
            sys.exit(2)
        sys.exit(0)
        sys.exit(2)
        """
    ).lstrip()
    tree = hook_contract_lint._parse_module(source)
    assert tree is not None
    lines = hook_contract_lint._find_sys_exit_two_lines(tree)
    assert lines == [3, 5]


def test_find_sys_exit_two_lines_recognizes_bare_exit():
    source = textwrap.dedent(
        """
        if True:
            exit(2)
        """
    ).lstrip()
    tree = hook_contract_lint._parse_module(source)
    assert tree is not None
    lines = hook_contract_lint._find_sys_exit_two_lines(tree)
    assert lines == [2]


def test_find_sys_exit_two_lines_ignores_other_codes():
    source = textwrap.dedent(
        """
        import sys
        sys.exit(0)
        sys.exit(1)
        sys.exit("error")
        sys.exit(code)
        sys.exit()
        """
    ).lstrip()
    tree = hook_contract_lint._parse_module(source)
    assert tree is not None
    lines = hook_contract_lint._find_sys_exit_two_lines(tree)
    assert lines == []


# --------------------------------------------------------------------------- #
# _parse_module
# --------------------------------------------------------------------------- #
def test_parse_module_returns_none_for_invalid_syntax():
    tree = hook_contract_lint._parse_module("def broken(:")
    assert tree is None


# --------------------------------------------------------------------------- #
# lint_file
# --------------------------------------------------------------------------- #
def test_lint_file_reports_invalid_python(hooks_dir: Path):
    path = _write_hook(hooks_dir, "broken", "def broken(:")
    findings = hook_contract_lint.lint_file(str(path))
    assert len(findings) == 1
    assert findings[0].code == "HC100"
    assert findings[0].severity == "error"


def test_lint_file_returns_empty_for_unreadable_file(tmp_path: Path):
    path = tmp_path / "ghost.py"
    findings = hook_contract_lint.lint_file(str(path))
    assert findings == []


def test_lint_file_flags_migration_target_without_shim(hooks_dir: Path):
    path = _write_hook(
        hooks_dir,
        "secret-scanner",
        """
        import sys
        sys.exit(2)
        """,
    )
    findings = hook_contract_lint.lint_file(str(path))
    codes = [f.code for f in findings]
    assert "HC001" in codes
    assert "HC002" in codes
    severities = {f.severity for f in findings}
    assert severities == {"error"}


def test_lint_file_flags_each_sys_exit_two_in_target(hooks_dir: Path):
    path = _write_hook(
        hooks_dir,
        "mutation-method-blocker",
        """
        import sys
        sys.exit(2)
        sys.exit(2)
        """,
    )
    findings = hook_contract_lint.lint_file(str(path))
    line_findings = [f for f in findings if f.code == "HC002"]
    assert [f.line for f in line_findings] == [2, 3]


def test_lint_file_clean_when_target_uses_shim(hooks_dir: Path):
    path = _write_hook(
        hooks_dir,
        "conventional-commits",
        """
        import sys
        from hook_io import block, allow
        block("nope")
        sys.exit(0)
        """,
    )
    findings = hook_contract_lint.lint_file(str(path))
    assert findings == []


def test_lint_file_info_for_legacy_hook_without_shim(hooks_dir: Path):
    path = _write_hook(
        hooks_dir,
        "git-author-guard",
        """
        import sys
        sys.exit(2)
        """,
    )
    findings = hook_contract_lint.lint_file(str(path))
    assert len(findings) == 1
    assert findings[0].code == "HC010"
    assert findings[0].severity == "info"
    assert findings[0].line == 2


def test_lint_file_clean_for_legacy_hook_using_shim(hooks_dir: Path):
    path = _write_hook(
        hooks_dir,
        "git-author-guard",
        """
        import sys
        from _lib import hook_io
        sys.exit(hook_io.allow())
        """,
    )
    findings = hook_contract_lint.lint_file(str(path))
    assert findings == []


def test_lint_file_clean_for_legacy_hook_without_block(hooks_dir: Path):
    path = _write_hook(
        hooks_dir,
        "english-only-reminder",
        """
        import sys
        sys.exit(0)
        """,
    )
    findings = hook_contract_lint.lint_file(str(path))
    assert findings == []


# --------------------------------------------------------------------------- #
# lint_directory
# --------------------------------------------------------------------------- #
def test_lint_directory_aggregates_findings(hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "secret-scanner",
        """
        import sys
        sys.exit(2)
        """,
    )
    _write_hook(
        hooks_dir,
        "git-author-guard",
        """
        import sys
        sys.exit(2)
        """,
    )
    findings = hook_contract_lint.lint_directory(str(hooks_dir))
    by_hook = {f.hook for f in findings}
    assert by_hook == {"secret-scanner", "git-author-guard"}


def test_lint_directory_respects_include_filter(hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "secret-scanner",
        """
        import sys
        sys.exit(2)
        """,
    )
    _write_hook(
        hooks_dir,
        "git-author-guard",
        """
        import sys
        sys.exit(2)
        """,
    )
    findings = hook_contract_lint.lint_directory(
        str(hooks_dir), include=["git-author-guard"]
    )
    assert {f.hook for f in findings} == {"git-author-guard"}


def test_lint_directory_returns_empty_for_clean_tree(hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "english-only-reminder",
        """
        import sys
        sys.exit(0)
        """,
    )
    findings = hook_contract_lint.lint_directory(str(hooks_dir))
    assert findings == []


# --------------------------------------------------------------------------- #
# formatters
# --------------------------------------------------------------------------- #
def test_format_table_for_empty_findings_returns_no_findings_message():
    out = hook_contract_lint._format_table([])
    assert out == "No findings.\n"


def test_format_table_includes_path_and_line():
    finding = hook_contract_lint.Finding(
        hook="secret-scanner",
        path="/tmp/hooks/secret-scanner.py",
        severity="error",
        code="HC002",
        message="raw sys.exit(2)",
        line=42,
    )
    out = hook_contract_lint._format_table([finding])
    assert "secret-scanner" in out
    assert "HC002" in out
    assert "/tmp/hooks/secret-scanner.py:42" in out


def test_format_json_round_trips_findings():
    finding = hook_contract_lint.Finding(
        hook="secret-scanner",
        path="/tmp/hooks/secret-scanner.py",
        severity="error",
        code="HC002",
        message="raw sys.exit(2)",
        line=42,
    )
    raw = hook_contract_lint._format_json([finding])
    parsed = json.loads(raw)
    assert parsed[0]["hook"] == "secret-scanner"
    assert parsed[0]["line"] == 42


# --------------------------------------------------------------------------- #
# _exit_code_for
# --------------------------------------------------------------------------- #
def test_exit_code_for_clean_findings_is_zero():
    code = hook_contract_lint._exit_code_for([], strict=False)
    assert code == 0


def test_exit_code_for_info_finding_default_zero():
    info = hook_contract_lint.Finding(
        hook="x", path="/x.py", severity="info", code="HC010", message="x"
    )
    code = hook_contract_lint._exit_code_for([info], strict=False)
    assert code == 0


def test_exit_code_for_info_finding_strict_one():
    info = hook_contract_lint.Finding(
        hook="x", path="/x.py", severity="info", code="HC010", message="x"
    )
    code = hook_contract_lint._exit_code_for([info], strict=True)
    assert code == 1


def test_exit_code_for_error_finding_is_one():
    err = hook_contract_lint.Finding(
        hook="x", path="/x.py", severity="error", code="HC001", message="x"
    )
    code = hook_contract_lint._exit_code_for([err], strict=False)
    assert code == 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_table_output_clean_tree(capsys, hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "english-only-reminder",
        """
        import sys
        sys.exit(0)
        """,
    )
    code = hook_contract_lint._cli(["--hooks-dir", str(hooks_dir)])
    captured = capsys.readouterr()
    assert code == 0
    assert "No findings." in captured.out


def test_cli_table_output_reports_target_violation(capsys, hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "secret-scanner",
        """
        import sys
        sys.exit(2)
        """,
    )
    code = hook_contract_lint._cli(["--hooks-dir", str(hooks_dir)])
    captured = capsys.readouterr()
    assert code == 1
    assert "HC001" in captured.out
    assert "HC002" in captured.out


def test_cli_json_output_is_valid(capsys, hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "secret-scanner",
        """
        import sys
        sys.exit(2)
        """,
    )
    code = hook_contract_lint._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    data = json.loads(captured.out)
    assert any(item["code"] == "HC001" for item in data)


def test_cli_strict_makes_info_fail(capsys, hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "git-author-guard",
        """
        import sys
        sys.exit(2)
        """,
    )
    code_default = hook_contract_lint._cli(["--hooks-dir", str(hooks_dir)])
    capsys.readouterr()
    code_strict = hook_contract_lint._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--strict",
        ]
    )
    capsys.readouterr()
    assert code_default == 0
    assert code_strict == 1


def test_cli_include_limits_targets(capsys, hooks_dir: Path):
    _write_hook(
        hooks_dir,
        "secret-scanner",
        """
        import sys
        sys.exit(2)
        """,
    )
    _write_hook(
        hooks_dir,
        "git-author-guard",
        """
        import sys
        sys.exit(2)
        """,
    )
    code = hook_contract_lint._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--include",
            "git-author-guard",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0  # info-only finding under default strictness
    parsed = json.loads(captured.out)
    assert all(item["hook"] == "git-author-guard" for item in parsed)


def test_cli_main_block_executes_when_invoked_as_script(monkeypatch, tmp_path: Path):
    fake_hooks = tmp_path / "hooks"
    fake_hooks.mkdir()
    (fake_hooks / "english-only-reminder.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        sys, "argv", ["hook_contract_lint.py", "--hooks-dir", str(fake_hooks)]
    )
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    rc = hook_contract_lint._cli(sys.argv[1:])
    assert rc == 0
    assert "No findings." in buf.getvalue()


def test_cli_default_hooks_dir_is_user_hooks(monkeypatch, hooks_dir: Path):
    monkeypatch.setattr(hook_contract_lint, "DEFAULT_HOOKS_DIR", str(hooks_dir))
    _write_hook(
        hooks_dir,
        "english-only-reminder",
        """
        import sys
        sys.exit(0)
        """,
    )
    code = hook_contract_lint._cli([])
    assert code == 0
