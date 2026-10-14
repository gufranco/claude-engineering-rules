from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "hooks"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_core as core  # noqa: E402
from _helpers.raising import raising  # noqa: E402


def boom(*_args, **_kwargs):
    raise subprocess.TimeoutExpired(cmd="ast-grep", timeout=2.0)


def test_ast_grep_path_disabled_via_env(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", None, raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", False, raising=False)
    monkeypatch.setenv("MUTATION_METHOD_AST", "0")

    # Act
    result = core.ast_grep_path()

    # Assert
    assert result is None


def test_ast_grep_path_cached_returns_same(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/usr/bin/cached", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    first = core.ast_grep_path()

    # Act
    second = core.ast_grep_path()

    # Assert
    assert first == "/usr/bin/cached"
    assert second == "/usr/bin/cached"


def test_ast_grep_path_resolves_via_which(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", None, raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", False, raising=False)
    monkeypatch.delenv("MUTATION_METHOD_AST", raising=False)
    monkeypatch.setattr(
        core.shutil,
        "which",
        lambda name: "/fake/ast-grep" if name == "ast-grep" else None,
    )

    # Act
    result = core.ast_grep_path()

    # Assert
    assert result == "/fake/ast-grep"


def test_run_ast_grep_no_binary(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", None, raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert result == []


def test_run_ast_grep_unsupported_lang(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "rust")

    # Assert
    assert result == []


def test_run_ast_grep_empty_source(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    # Act
    result = core.run_ast_grep("$X.push($Y)", "", "ts")

    # Assert
    assert result == []


def test_run_ast_grep_timeout(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    monkeypatch.setattr(core.subprocess, "run", boom)

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert result == []


def test_run_ast_grep_oserror(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    boom = raising(OSError("not found"))
    monkeypatch.setattr(core.subprocess, "run", boom)

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert result == []


def test_run_ast_grep_non_zero_exit(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    monkeypatch.setattr(
        core.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=2, stdout="", stderr=""),
    )

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert result == []


def test_run_ast_grep_valid_output(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    payload = json.dumps(
        {
            "range": {"start": {"line": 4, "column": 2}},
            "text": "items.push(x)",
            "kind": "call_expression",
        }
    )
    stdout = payload + "\n\n" + "{not-json}\n" + payload + "\n"
    monkeypatch.setattr(
        core.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    )

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert len(result) == 2
    assert result[0].line == 5
    assert result[0].col == 3
    assert result[0].detector == "ast"
    assert result[0].node_type == "call_expression"


def test_run_ast_grep_exit_code_one_returns_no_matches(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    monkeypatch.setattr(
        core.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert result == []
