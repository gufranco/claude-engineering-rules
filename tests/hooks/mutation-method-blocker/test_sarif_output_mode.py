"""SARIF output mode + batch mode integration tests.

Items 221, 227, 228, 229 of the plan. Verifies the hook:

  * Emits SARIF JSON on stdout when MUTATION_METHOD_OUTPUT=sarif (item 221).
  * Reads file paths from stdin when MUTATION_METHOD_BATCH_MODE=1 (item 227).
  * Combines findings across files into a single SARIF document (item 228).
  * Honors MUTATION_METHOD_FAIL_THRESHOLD for batch exit codes (item 229).
"""

from __future__ import annotations

import json
import subprocess
import sys


from conftest import HOOK_PATH, _build_env, make_edit_payload


def _run_hook_with_env(payload: dict, env: dict[str, str]):
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_build_env(env),
        timeout=10.0,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _run_batch_hook(file_list_text: str, env: dict[str, str]):
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=file_list_text,
        capture_output=True,
        text=True,
        env=_build_env(env),
        timeout=10.0,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_sarif_output_mode_emits_sarif_on_stdout():
    """Item 221: MUTATION_METHOD_OUTPUT=sarif emits SARIF on stdout."""
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "sarif"}

    # Act
    code, stdout, stderr = _run_hook_with_env(payload, env)

    # Assert
    assert stdout.strip(), "SARIF output must appear on stdout"
    parsed = json.loads(stdout)
    assert parsed["version"] == "2.1.0"
    assert parsed["runs"][0]["tool"]["driver"]["name"] == "mutation-method-blocker"
    assert len(parsed["runs"][0]["results"]) >= 1


def test_sarif_output_mode_emits_empty_envelope_on_clean_input():
    """Item 221: even with no findings, SARIF mode emits a valid envelope."""
    # Arrange
    snippet = "const arr = [1, 2, 3]\nconst next = [...arr, 4]\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "sarif"}

    # Act
    code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    assert code == 0
    parsed = json.loads(stdout)
    assert parsed["runs"][0]["results"] == []


def test_default_output_mode_emits_text(tmp_path):
    """Default MUTATION_METHOD_OUTPUT (text) preserves stderr block render."""
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env: dict[str, str] = {}

    # Act
    code, stdout, stderr = _run_hook_with_env(payload, env)

    # Assert
    assert code == 2
    assert "array.push" in stderr
    assert "$schema" not in stdout, "default mode must not emit SARIF on stdout"


def test_batch_mode_reads_paths_from_stdin(tmp_path):
    """Item 227: MUTATION_METHOD_BATCH_MODE=1 reads file paths from stdin."""
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "a.ts").write_text("const arr = [1]\narr.push(2)\n", encoding="utf-8")
    file_list = f"{src / 'a.ts'}\n"
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "sarif",
    }

    # Act
    code, stdout, _stderr = _run_batch_hook(file_list, env)

    # Assert
    parsed = json.loads(stdout)
    results = parsed["runs"][0]["results"]
    assert len(results) >= 1
    assert results[0]["properties"]["detector"].startswith("array.")
    assert code == 1


def test_batch_mode_combines_multiple_files_into_one_sarif(tmp_path):
    """Item 228: batch mode combines findings into a single SARIF document."""
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "dirty1.ts").write_text("const a = [1]\na.push(2)\n", encoding="utf-8")
    (src / "dirty2.ts").write_text("const b = [3]\nb.sort()\n", encoding="utf-8")
    (src / "clean.ts").write_text("const c = [...[1, 2], 3]\n", encoding="utf-8")
    file_list = "\n".join(
        [
            str(src / "dirty1.ts"),
            str(src / "dirty2.ts"),
            str(src / "clean.ts"),
        ]
    )
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "sarif",
    }

    # Act
    code, stdout, _stderr = _run_batch_hook(file_list, env)

    # Assert
    parsed = json.loads(stdout)
    results = parsed["runs"][0]["results"]
    assert len(results) == 2
    detectors = {r["properties"]["detector"] for r in results}
    assert "array.push" in detectors
    assert "array.sort" in detectors
    assert code == 1


def test_batch_mode_fail_threshold_none_always_exits_zero(tmp_path):
    """Item 229: MUTATION_METHOD_FAIL_THRESHOLD=none always exits 0."""
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "dirty.ts").write_text("const a = [1]\na.push(2)\n", encoding="utf-8")
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "sarif",
        "MUTATION_METHOD_FAIL_THRESHOLD": "none",
    }

    # Act
    code, stdout, _stderr = _run_batch_hook(str(src / "dirty.ts") + "\n", env)

    # Assert
    parsed = json.loads(stdout)
    assert len(parsed["runs"][0]["results"]) >= 1
    assert code == 0


def test_batch_mode_fail_threshold_error_default(tmp_path):
    """Item 229: default threshold is 'error', non-zero on error findings."""
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "dirty.ts").write_text("const a = [1]\na.push(2)\n", encoding="utf-8")
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "sarif",
    }

    # Act
    code, _stdout, _stderr = _run_batch_hook(str(src / "dirty.ts") + "\n", env)

    # Assert
    assert code == 1


def test_batch_mode_skips_blank_and_comment_lines(tmp_path):
    """Stdin-supplied file list ignores blank lines and lines starting with #."""
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "a.ts").write_text("const a = [1]\na.push(2)\n", encoding="utf-8")
    file_list = "\n".join(
        [
            "# header comment",
            "",
            str(src / "a.ts"),
            "",
            "# trailing comment",
        ]
    )
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "sarif",
    }

    # Act
    code, stdout, _stderr = _run_batch_hook(file_list, env)

    # Assert
    parsed = json.loads(stdout)
    assert len(parsed["runs"][0]["results"]) == 1


def test_sarif_output_mode_includes_partial_fingerprints(tmp_path):
    """SARIF output must include partialFingerprints for stable dedup."""
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "sarif"}

    # Act
    _code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    parsed = json.loads(stdout)
    result = parsed["runs"][0]["results"][0]
    fp = result["partialFingerprints"]["primaryLocationLineHash"]
    assert len(fp) == 64
