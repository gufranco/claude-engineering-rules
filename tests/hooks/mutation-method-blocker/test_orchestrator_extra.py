"""Extra coverage for `hooks/mutation-method-blocker.py`.

Targets the internal helpers and the orchestrator branches not exercised
by the existing subprocess-driven tests:

  - Env-flag readers (`_debug_mode`, `_concise_mode`, `_profile_mode`,
    `_experimental_enabled`).
  - `_read_batch_items` argv path and OSError handling.
  - The `_entrypoint` cProfile branch and the file-write `OSError` swallow.
  - `main()` disable-env and invalid-JSON branches.
"""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "hooks"
SCRIPTS_DIR = REPO_ROOT / "scripts"
HOOK_PATH = HOOKS_DIR / "mutation-method-blocker.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))


def _load_hook():
    """Load the hyphenated hook module by spec and cache under a normal name."""
    if "mutation_method_blocker" in sys.modules:
        return sys.modules["mutation_method_blocker"]
    spec = importlib.util.spec_from_file_location("mutation_method_blocker", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation_method_blocker"] = module
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


# --------------------------------------------------------------------------- #
# env-flag readers (lines 291, 649)
# --------------------------------------------------------------------------- #


def test_debug_mode_returns_true_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_DEBUG", "1")
    assert hook._debug_mode() is True


def test_debug_mode_returns_false_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MUTATION_METHOD_DEBUG", raising=False)
    assert hook._debug_mode() is False


def test_concise_mode_returns_true_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_CONCISE", "1")
    assert hook._concise_mode() is True


def test_concise_mode_returns_false_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("MUTATION_METHOD_CONCISE", raising=False)
    assert hook._concise_mode() is False


def test_profile_mode_returns_true_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_PROFILE", "1")
    assert hook._profile_mode() is True


def test_experimental_enabled_returns_true_for_set_var(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN", "1")
    assert hook._experimental_enabled("OPTIONAL_CHAIN_ASSIGN") is True


def test_experimental_enabled_returns_false_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("MUTATION_METHOD_EXPERIMENTAL_FOO", raising=False)
    assert hook._experimental_enabled("FOO") is False


# --------------------------------------------------------------------------- #
# _read_batch_items argv + OSError + stdin failure (lines 735, 739-740, 750-751)
# --------------------------------------------------------------------------- #


def test_read_batch_items_uses_argv_when_provided(tmp_path: Path, monkeypatch) -> None:
    # Arrange
    f = tmp_path / "src.ts"
    f.write_text("const x = 1\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["hook", str(f)])

    # Act
    items = hook._read_batch_items()

    # Assert
    assert len(items) == 1
    assert items[0][0] == str(f)
    assert items[0][3] is True


def test_read_batch_items_skips_unreadable_path(tmp_path: Path, monkeypatch) -> None:
    # Arrange: argv lists a non-existent file
    monkeypatch.setattr(sys, "argv", ["hook", str(tmp_path / "ghost.ts")])

    # Act
    items = hook._read_batch_items()

    # Assert
    assert items == []


def test_read_batch_items_handles_stdin_failure(monkeypatch) -> None:
    # Arrange: argv is empty (only program name) so stdin is read; force read
    # to raise.
    monkeypatch.setattr(sys, "argv", ["hook"])

    class FailingStdin:
        def read(self) -> str:  # noqa: D401
            raise OSError("stdin closed")

    monkeypatch.setattr(sys, "stdin", FailingStdin())

    # Act
    items = hook._read_batch_items()

    # Assert
    assert items == []


def test_read_batch_items_skips_blank_and_comment_lines(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(sys, "argv", ["hook"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n# comment\n\n"))

    # Act
    items = hook._read_batch_items()

    # Assert
    assert items == []


# --------------------------------------------------------------------------- #
# _entrypoint cProfile branch + OSError swallow (lines 902-918)
# --------------------------------------------------------------------------- #


def test_entrypoint_no_profile_calls_main_directly(monkeypatch) -> None:
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_PROFILE", raising=False)
    sentinel = object()
    monkeypatch.setattr(hook, "main", lambda: sentinel)

    # Act
    result = hook._entrypoint()

    # Assert
    assert result is sentinel


def test_entrypoint_profile_writes_report(monkeypatch, tmp_path: Path) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_PROFILE", "1")
    monkeypatch.setattr(hook.os.path, "expanduser", lambda p: str(tmp_path))
    monkeypatch.setattr(hook, "main", lambda: 0)

    # Act
    rc = hook._entrypoint()

    # Assert
    assert rc == 0
    profile_file = tmp_path / ".claude" / "logs" / "mutation_blocker_profile.txt"
    assert profile_file.exists()


def test_entrypoint_profile_swallows_os_error(monkeypatch) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_PROFILE", "1")
    monkeypatch.setattr(hook, "main", lambda: 7)
    # Force os.makedirs to raise OSError so the swallow branch fires.
    monkeypatch.setattr(
        hook.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(OSError("denied"))
    )

    # Act
    rc = hook._entrypoint()

    # Assert: the inner main() return is preserved despite the OSError
    assert rc == 7


def test_main_handles_disable_env(monkeypatch) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_DISABLE", "1")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    # Act
    rc = hook.main()

    # Assert
    assert rc == 0


def test_main_handles_invalid_json_payload(monkeypatch) -> None:
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    monkeypatch.delenv("MUTATION_METHOD_BATCH_MODE", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    # Act
    rc = hook.main()

    # Assert
    assert rc == 0


# --------------------------------------------------------------------------- #
# CLI flags: --version, --print-detectors, --list-allowlists
# --------------------------------------------------------------------------- #


def test_handle_cli_flags_version(monkeypatch, capsys) -> None:
    # Arrange
    monkeypatch.setattr(sys, "argv", ["hook", "--version"])

    # Act
    rc = hook._handle_cli_flags()

    # Assert
    assert rc == 0
    assert "mutation-method-blocker" in capsys.readouterr().out


def test_handle_cli_flags_print_detectors(monkeypatch, capsys) -> None:
    # Arrange
    import json as _json

    monkeypatch.setattr(sys, "argv", ["hook", "--print-detectors"])

    # Act
    rc = hook._handle_cli_flags()

    # Assert
    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert "detectors" in payload
    assert isinstance(payload["detectors"], list)
    assert len(payload["detectors"]) > 50


def test_handle_cli_flags_list_allowlists(monkeypatch, capsys) -> None:
    # Arrange
    import json as _json

    monkeypatch.setattr(sys, "argv", ["hook", "--list-allowlists"])

    # Act
    rc = hook._handle_cli_flags()

    # Assert
    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["version"]


def test_handle_cli_flags_no_args_returns_none(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(sys, "argv", ["hook"])

    # Act
    rc = hook._handle_cli_flags()

    # Assert
    assert rc is None


def test_handle_cli_flags_print_detectors_oserror(monkeypatch, capsys) -> None:
    # Arrange: force open() inside the flag handler to raise OSError.
    monkeypatch.setattr(sys, "argv", ["hook", "--print-detectors"])
    import builtins as _builtins

    real_open = _builtins.open

    def _failing_open(path, *a, **k):
        if str(path).endswith("mutation_fix_suggestions.json"):
            raise OSError("denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr(_builtins, "open", _failing_open)

    # Act
    rc = hook._handle_cli_flags()

    # Assert
    assert rc == 1
    assert "failed to read detector catalog" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Integration branches: ts_project_service + source-map remapping
# --------------------------------------------------------------------------- #


def test_apply_ts_project_service_disabled_returns_unchanged() -> None:
    # Arrange
    matches: list = []

    # Act
    survived, dropped = hook._apply_ts_project_service("a.ts", matches)

    # Assert: ts_ps_enabled() is false by default in test env
    assert survived == matches
    assert dropped == 0


def test_remap_via_source_map_passthrough_for_non_transpiled() -> None:
    # Arrange
    matches: list = []

    # Act
    path, out = hook._remap_via_source_map("src/app.ts", matches)

    # Assert: non-transpiled path returns unchanged
    assert path == "src/app.ts"
    assert out == matches
