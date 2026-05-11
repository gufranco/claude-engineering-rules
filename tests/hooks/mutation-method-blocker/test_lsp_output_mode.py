"""LSP output mode integration tests.

Plan item 372. Verifies the hook:

  * Emits LSP 3.17 Diagnostic[] JSON on stdout when MUTATION_METHOD_OUTPUT=lsp.
  * Produces output that conforms to schemas/mutation-method-blocker-lsp.schema.json.
  * Uses 0-based line/character offsets (LSP convention).
  * Emits file:// URIs (LSP requirement for editor matching).
  * Combines findings across files into separate documents.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from conftest import HOOK_PATH, _build_env, make_edit_payload

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "schemas"
    / "mutation-method-blocker-lsp.schema.json"
)


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


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_document_array(documents: list[dict]) -> list[str]:
    """Minimal structural validator: walks the LSP shape and returns errors.

    The Python stdlib has no JSON Schema validator and we don't want to add a
    runtime dependency on `jsonschema` just for tests. This walker enforces
    the same invariants as the schema document.
    """
    errors: list[str] = []
    _load_schema()
    mmb_pattern = re.compile(r"^MMB[0-9]{3}$")
    if not isinstance(documents, list):
        return [f"top-level must be an array, got {type(documents).__name__}"]
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            errors = [*errors, f"document[{index}] is not an object"]
            continue
        uri = document.get("uri")
        if not isinstance(uri, str) or not uri.startswith("file:///"):
            errors = [*errors, f"document[{index}].uri must be file:/// URI"]
        diagnostics = document.get("diagnostics")
        if not isinstance(diagnostics, list):
            errors = [*errors, f"document[{index}].diagnostics must be an array"]
            continue
        for diag_index, diag in enumerate(diagnostics):
            prefix = f"document[{index}].diagnostics[{diag_index}]"
            if not isinstance(diag, dict):
                errors = [*errors, f"{prefix} is not an object"]
                continue
            severity = diag.get("severity")
            if severity not in (1, 2, 3, 4):
                errors = [*errors, f"{prefix}.severity must be 1-4, got {severity}"]
            code = diag.get("code")
            if not isinstance(code, str) or not mmb_pattern.match(code):
                errors = [*errors, f"{prefix}.code must match MMB### (got {code!r})"]
            if diag.get("source") != "mutation-method-blocker":
                errors = [*errors, f"{prefix}.source must be mutation-method-blocker"]
            message = diag.get("message")
            if not isinstance(message, str) or not message:
                errors = [*errors, f"{prefix}.message must be a non-empty string"]
            rng = diag.get("range")
            if not isinstance(rng, dict):
                errors = [*errors, f"{prefix}.range must be an object"]
                continue
            for end in ("start", "end"):
                pos = rng.get(end)
                if not isinstance(pos, dict):
                    errors = [*errors, f"{prefix}.range.{end} must be an object"]
                    continue
                line = pos.get("line")
                char = pos.get("character")
                if not isinstance(line, int) or line < 0:
                    errors = [
                        *errors,
                        f"{prefix}.range.{end}.line must be a non-negative int",
                    ]
                if not isinstance(char, int) or char < 0:
                    errors = [
                        *errors,
                        f"{prefix}.range.{end}.character must be a non-negative int",
                    ]
    return errors


def test_lsp_output_mode_emits_lsp_json_on_stdout():
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "lsp"}

    # Act
    code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    documents = json.loads(stdout)
    assert documents, "LSP mode must emit at least one PublishDiagnosticsParams"
    assert documents[0]["diagnostics"]
    assert documents[0]["diagnostics"][0]["source"] == "mutation-method-blocker"
    assert code == 2


def test_lsp_output_mode_empty_envelope_on_clean_input():
    # Arrange
    snippet = "const arr = [1, 2, 3]\nconst next = [...arr, 4]\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "lsp"}

    # Act
    code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    documents = json.loads(stdout)
    assert documents == []
    assert code == 0


def test_lsp_output_uses_zero_based_offsets():
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "lsp"}

    # Act
    _code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    documents = json.loads(stdout)
    diag = documents[0]["diagnostics"][0]
    assert diag["range"]["start"]["line"] == 1, (
        "line 2 in the snippet must report as line index 1 (LSP is 0-based)"
    )
    assert diag["range"]["end"]["line"] == 1
    assert diag["range"]["end"]["character"] > diag["range"]["start"]["character"]


def test_lsp_output_includes_mmb_code():
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "lsp"}

    # Act
    _code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    documents = json.loads(stdout)
    diag = documents[0]["diagnostics"][0]
    assert diag["code"] == "MMB001", (
        f"expected MMB001 for array.push, got {diag['code']}"
    )


def test_lsp_output_conforms_to_schema():
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\nconst m = new Map()\nm.set('a', 1)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "lsp"}

    # Act
    _code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    documents = json.loads(stdout)
    errors = _validate_document_array(documents)
    assert errors == [], f"LSP output failed schema validation: {errors}"


def test_lsp_output_combines_multiple_files(tmp_path):
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "a.ts").write_text("const a = [1]\na.push(2)\n", encoding="utf-8")
    (src / "b.ts").write_text("const b = [3]\nb.sort()\n", encoding="utf-8")
    file_list = "\n".join([str(src / "a.ts"), str(src / "b.ts")])
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "lsp",
    }

    # Act
    _code, stdout, _stderr = _run_batch_hook(file_list, env)

    # Assert
    documents = json.loads(stdout)
    uris = sorted(d["uri"] for d in documents)
    assert len(uris) == 2
    assert all(u.startswith("file:///") for u in uris)
    assert _validate_document_array(documents) == []


def test_lsp_output_clean_input_emits_empty_array_in_batch_mode(tmp_path):
    # Arrange
    src = tmp_path / "src" / "business"
    src.mkdir(parents=True)
    (src / "clean.ts").write_text(
        "const arr = [1, 2, 3]\nconst next = [...arr, 4]\n", encoding="utf-8"
    )
    env = {
        "MUTATION_METHOD_BATCH_MODE": "1",
        "MUTATION_METHOD_OUTPUT": "lsp",
    }

    # Act
    code, stdout, _stderr = _run_batch_hook(str(src / "clean.ts") + "\n", env)

    # Assert
    assert json.loads(stdout) == []
    assert code == 0


def test_lsp_severity_maps_to_lsp_diagnostic_severity():
    # Arrange
    snippet = "const arr = [1, 2, 3]\narr.push(4)\n"
    payload = make_edit_payload("/repo/src/business/orders.ts", snippet)
    env = {"MUTATION_METHOD_OUTPUT": "lsp"}

    # Act
    _code, stdout, _stderr = _run_hook_with_env(payload, env)

    # Assert
    documents = json.loads(stdout)
    diag = documents[0]["diagnostics"][0]
    assert diag["severity"] in (1, 2), (
        f"expected Error (1) or Warning (2) for an unambiguous array.push, got {diag['severity']}"
    )
