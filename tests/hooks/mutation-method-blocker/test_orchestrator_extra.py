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
HOOK_PATH = HOOKS_DIR / "mutation-method-blocker.py"

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
    f = tmp_path / "src.ts"
    f.write_text("const x = 1\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["hook", str(f)])

    items = hook._read_batch_items()

    assert len(items) == 1
    assert items[0][0] == str(f)
    assert items[0][3] is True


def test_read_batch_items_skips_unreadable_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["hook", str(tmp_path / "ghost.ts")])

    items = hook._read_batch_items()

    assert items == []


def test_read_batch_items_handles_stdin_failure(monkeypatch) -> None:
    # to raise.
    monkeypatch.setattr(sys, "argv", ["hook"])

    class FailingStdin:
        def read(self) -> str:  # noqa: D401
            raise OSError("stdin closed")

    monkeypatch.setattr(sys, "stdin", FailingStdin())

    items = hook._read_batch_items()

    assert items == []


def test_read_batch_items_skips_blank_and_comment_lines(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["hook"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n# comment\n\n"))

    items = hook._read_batch_items()

    assert items == []


# --------------------------------------------------------------------------- #
# _entrypoint cProfile branch + OSError swallow (lines 902-918)
# --------------------------------------------------------------------------- #


def test_entrypoint_no_profile_calls_main_directly(monkeypatch) -> None:
    monkeypatch.delenv("MUTATION_METHOD_PROFILE", raising=False)
    sentinel = object()
    monkeypatch.setattr(hook, "main", lambda: sentinel)

    result = hook._entrypoint()

    assert result is sentinel


def test_entrypoint_profile_writes_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MUTATION_METHOD_PROFILE", "1")
    monkeypatch.setattr(hook.os.path, "expanduser", lambda p: str(tmp_path))
    monkeypatch.setattr(hook, "main", lambda: 0)

    rc = hook._entrypoint()

    assert rc == 0
    profile_file = tmp_path / ".claude" / "logs" / "mutation_blocker_profile.txt"
    assert profile_file.exists()


def test_entrypoint_profile_swallows_os_error(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_PROFILE", "1")
    monkeypatch.setattr(hook, "main", lambda: 7)
    # Force os.makedirs to raise OSError so the swallow branch fires.
    monkeypatch.setattr(
        hook.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(OSError("denied"))
    )

    rc = hook._entrypoint()

    assert rc == 7


def test_main_handles_disable_env(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_DISABLE", "1")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    rc = hook.main()

    assert rc == 0


def test_main_handles_invalid_json_payload(monkeypatch) -> None:
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    monkeypatch.delenv("MUTATION_METHOD_BATCH_MODE", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    rc = hook.main()

    assert rc == 0


# --------------------------------------------------------------------------- #
# CLI flags: --version, --print-detectors, --list-allowlists
# --------------------------------------------------------------------------- #


def test_handle_cli_flags_version(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["hook", "--version"])

    rc = hook._handle_cli_flags()

    assert rc == 0
    assert "mutation-method-blocker" in capsys.readouterr().out


def test_handle_cli_flags_print_detectors(monkeypatch, capsys) -> None:
    import json as _json

    monkeypatch.setattr(sys, "argv", ["hook", "--print-detectors"])

    rc = hook._handle_cli_flags()

    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert "detectors" in payload
    assert isinstance(payload["detectors"], list)
    assert len(payload["detectors"]) > 50


def test_handle_cli_flags_list_allowlists(monkeypatch, capsys) -> None:
    import json as _json

    monkeypatch.setattr(sys, "argv", ["hook", "--list-allowlists"])

    rc = hook._handle_cli_flags()

    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["version"]


def test_handle_cli_flags_no_args_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["hook"])

    rc = hook._handle_cli_flags()

    assert rc is None


def test_handle_cli_flags_print_detectors_oserror(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["hook", "--print-detectors"])
    import builtins as _builtins

    real_open = _builtins.open

    def _failing_open(path, *a, **k):
        if str(path).endswith("mutation_fix_suggestions.json"):
            raise OSError("denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr(_builtins, "open", _failing_open)

    rc = hook._handle_cli_flags()

    assert rc == 1
    assert "failed to read detector catalog" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Integration branches: ts_project_service + source-map remapping
# --------------------------------------------------------------------------- #


def test_apply_ts_project_service_disabled_returns_unchanged() -> None:
    matches: list = []

    survived, dropped = hook._apply_ts_project_service("a.ts", matches)

    assert survived == matches
    assert dropped == 0


def test_remap_via_source_map_passthrough_for_non_transpiled() -> None:
    matches: list = []

    path, out = hook._remap_via_source_map("src/app.ts", matches)

    assert path == "src/app.ts"
    assert out == matches
