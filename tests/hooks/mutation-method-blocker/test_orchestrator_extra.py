"""Extra coverage for `hooks/mutation-method-blocker.py`.

Targets the internal helpers and the orchestrator branches not exercised
by the existing subprocess-driven tests:

  - Env-flag readers (`_debug_mode`, `_concise_mode`, `_profile_mode`,
    `_experimental_enabled`).
  - `_fail_threshold` fallback for unknown values.
  - `_confidence_to_level` non-integer / level branches.
  - `_batch_exit_code` empty findings, warning, note thresholds.
  - `_read_batch_items` argv path and OSError handling.
  - The `_entrypoint` cProfile branch and the file-write `OSError` swallow.
  - The `main()` empty-items SARIF path and the confidence ValueError swallow.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
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
# _fail_threshold fallback (line 346)
# --------------------------------------------------------------------------- #


def test_fail_threshold_returns_default_for_unknown_value(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "garbage")
    assert hook._fail_threshold() == "error"


def test_fail_threshold_accepts_warning(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "warning")
    assert hook._fail_threshold() == "warning"


def test_fail_threshold_accepts_note(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "note")
    assert hook._fail_threshold() == "note"


def test_fail_threshold_accepts_none(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "none")
    assert hook._fail_threshold() == "none"


# --------------------------------------------------------------------------- #
# _confidence_to_level branches (lines 685-686, 689-691)
# --------------------------------------------------------------------------- #


def test_confidence_to_level_returns_error_for_high() -> None:
    assert hook._confidence_to_level("5") == "error"
    assert hook._confidence_to_level("9") == "error"


def test_confidence_to_level_returns_warning_for_mid() -> None:
    assert hook._confidence_to_level("3") == "warning"
    assert hook._confidence_to_level("4") == "warning"


def test_confidence_to_level_returns_note_for_low() -> None:
    assert hook._confidence_to_level("1") == "note"
    assert hook._confidence_to_level("0") == "note"


def test_confidence_to_level_falls_back_for_non_integer() -> None:
    assert hook._confidence_to_level("not-a-number") == "error"


def test_confidence_to_level_falls_back_for_none() -> None:
    assert hook._confidence_to_level(None) == "error"


# --------------------------------------------------------------------------- #
# _batch_exit_code branches (lines 706, 714-720)
# --------------------------------------------------------------------------- #


class _FakeMatch:
    def __init__(self, confidence: str) -> None:
        self.metadata = {"confidence": confidence}


class _FakeFinding:
    def __init__(self, confidence: str) -> None:
        self.match = _FakeMatch(confidence)


def test_batch_exit_code_returns_zero_for_empty_findings(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "error")
    assert hook._batch_exit_code([]) == 0


def test_batch_exit_code_returns_zero_for_threshold_none(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "none")
    assert hook._batch_exit_code([_FakeFinding("5")]) == 0


def test_batch_exit_code_threshold_error_warning_findings(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "error")
    # Warning-only findings
    assert hook._batch_exit_code([_FakeFinding("3")]) == 0


def test_batch_exit_code_threshold_warning_with_warning(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "warning")
    assert hook._batch_exit_code([_FakeFinding("3")]) == 1


def test_batch_exit_code_threshold_warning_only_note(monkeypatch) -> None:
    # threshold=warning, finding at note level -> exit 0
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "warning")
    assert hook._batch_exit_code([_FakeFinding("1")]) == 0


def test_batch_exit_code_threshold_note(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "note")
    assert hook._batch_exit_code([_FakeFinding("1")]) == 1


def test_batch_exit_code_handles_finding_without_match_attr(monkeypatch) -> None:
    monkeypatch.setenv("MUTATION_METHOD_FAIL_THRESHOLD", "error")
    # When the finding is itself a Match, the code path uses it directly.
    plain_match = _FakeMatch("5")
    assert hook._batch_exit_code([plain_match]) == 1


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


# --------------------------------------------------------------------------- #
# main() empty-items SARIF + confidence ValueError (lines 784-786, 814-815)
# --------------------------------------------------------------------------- #


def test_main_empty_items_sarif_writes_empty_doc(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"tool_name":"Edit","tool_input":{}}')
    )
    monkeypatch.setenv("MUTATION_METHOD_OUTPUT", "sarif")
    monkeypatch.delenv("MUTATION_METHOD_BATCH_MODE", raising=False)
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    buf = io.StringIO()

    # Act
    with redirect_stdout(buf):
        rc = hook.main()

    # Assert
    assert rc == 0
    payload = json.loads(buf.getvalue().strip())
    assert payload["runs"][0]["results"] == []


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
