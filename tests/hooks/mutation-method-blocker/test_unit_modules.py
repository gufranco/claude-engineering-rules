"""Unit-level coverage for detector modules and hook helpers.

Item 143 of the plan. The subprocess-based suite under this directory
exercises the end-to-end hook contract; this file targets specific lines
that the integration tests do not reach: pure helpers, error branches,
and edge-case parsing inside the detector modules.

Tests import the modules directly via sys.path manipulation. The hook
entry point is loaded via importlib because the file name uses a hyphen
(`mutation-method-blocker.py`) and is not importable via `import`.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
HOOKS_DIR = REPO_ROOT / "hooks"
HOOK_PATH = HOOKS_DIR / "mutation-method-blocker.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "_mmb_hook_under_test", str(HOOK_PATH)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load hook module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOOK_MODULE = _load_hook_module()

import mutation_allowlists as allowlists  # noqa: E402
import mutation_detectors_assignments as assignments  # noqa: E402
import mutation_detectors_core as core  # noqa: E402
import mutation_detectors_methods as methods  # noqa: E402
import suppression as supp  # noqa: E402


def test_detect_lang_empty_path():
    # Arrange
    path = ""

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result is None


def test_detect_lang_unknown_extension():
    # Arrange
    path = "/repo/src/app.rs"

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result is None


def test_detect_lang_tsx():
    # Arrange
    path = "/repo/src/Component.tsx"

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result == "tsx"


def test_detect_lang_mjs_maps_to_js():
    # Arrange
    path = "/repo/src/main.mjs"

    # Act
    result = core.detect_lang(path)

    # Assert
    assert result == "js"


def test_supports_ast_none():
    # Arrange
    lang = None

    # Act
    result = core.supports_ast(lang)

    # Assert
    assert result is False


def test_supports_ast_unsupported():
    # Arrange
    lang = "rust"

    # Act
    result = core.supports_ast(lang)

    # Assert
    assert result is False


def test_supports_ast_tsx_true():
    # Arrange
    lang = "tsx"

    # Act
    result = core.supports_ast(lang)

    # Assert
    assert result is True


def test_strip_strings_comments_empty():
    # Arrange
    line = ""

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert result == ""


def test_strip_strings_comments_unclosed_block_comment():
    # Arrange
    line = "code /* unclosed comment continues forever"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert result.startswith("code ")
    assert "unclosed" not in result


def test_strip_strings_comments_backslash_escape():
    # Arrange
    line = 'const s = "a\\"b\\"c";'

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert "a" not in result.split('"')[1] if '"' in result else True
    assert len(result) == len(line)


def test_strip_strings_comments_template_literal_interpolation():
    # Arrange
    line = "const s = `value=${user.name}`;"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert len(result) == len(line)
    assert "${user.name}" not in result


def test_strip_strings_comments_template_with_nested_braces():
    # Arrange
    line = "const s = `a${{x: 1}.x}b`;"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert len(result) == len(line)


def test_strip_strings_comments_block_comment_closed():
    # Arrange
    line = "code /* inner */ tail"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert "inner" not in result
    assert result.endswith("tail")


def test_strip_strings_comments_line_comment():
    # Arrange
    line = "code // tail comment"

    # Act
    result = core.strip_strings_comments(line)

    # Assert
    assert "tail" not in result


def test_window_around_empty_lines():
    # Arrange
    lines: list[str] = []

    # Act
    result = core.window_around(lines, 5)

    # Assert
    assert result == ""


def test_window_around_clamp_lower():
    # Arrange
    lines = ["a", "b", "c"]

    # Act
    result = core.window_around(lines, 1, before=10, after=0)

    # Assert
    assert result == "a"


def test_window_around_clamp_upper():
    # Arrange
    lines = ["a", "b", "c"]

    # Act
    result = core.window_around(lines, 3, before=0, after=10)

    # Assert
    assert result == "c"


def test_truncate_excerpt_short():
    # Arrange
    line = "  short  "

    # Act
    result = core.truncate_excerpt(line, limit=120)

    # Assert
    assert result == "short"


def test_truncate_excerpt_long():
    # Arrange
    line = "x" * 200

    # Act
    result = core.truncate_excerpt(line, limit=10)

    # Assert
    assert result.endswith("...")
    assert len(result) <= 13


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

    # Act
    first = core.ast_grep_path()
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

    def boom(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="ast-grep", timeout=2.0)

    monkeypatch.setattr(core.subprocess, "run", boom)

    # Act
    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    # Assert
    assert result == []


def test_run_ast_grep_oserror(monkeypatch):
    # Arrange
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    def boom(*_args, **_kwargs):
        raise OSError("not found")

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


def test_suppression_lone_block_disable_recognized():
    # Arrange
    lines = ["// eslint-disable", "items.push(x);", "items.pop();", "// eslint-enable"]

    # Act
    state = supp.compute_block_state(lines)

    # Assert
    assert 0 in state.disabled_lines
    assert 1 in state.disabled_lines
    assert 2 in state.disabled_lines


def test_suppression_top_of_file_marker_blank_skip():
    # Arrange
    lines = ["", "", "// @ts-nocheck", "items.push(x);"]

    # Act
    result = supp.has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert result is True


def test_suppression_top_of_file_marker_scan_limit():
    # Arrange
    lines = [f"const x{i} = 1;" for i in range(15)] + ["// @ts-nocheck"]

    # Act
    result = supp.has_top_of_file_marker(lines, "@ts-nocheck")

    # Assert
    assert result is False


def test_suppression_top_of_file_marker_empty_marker():
    # Arrange
    lines = ["// foo"]

    # Act
    result = supp.has_top_of_file_marker(lines, "")

    # Assert
    assert result is False


def test_suppression_is_suppressed_invalid_index_high():
    # Arrange
    lines = ["a", "b"]

    # Act
    result = supp.is_suppressed(lines, 5)

    # Assert
    assert result is False


def test_suppression_is_suppressed_negative_index():
    # Arrange
    lines = ["a", "b"]

    # Act
    result = supp.is_suppressed(lines, -1)

    # Assert
    assert result is False


def test_suppression_is_suppressed_block_state_none_computes():
    # Arrange
    lines = ["/* eslint-disable */", "items.push(x);", "/* eslint-enable */"]

    # Act
    result = supp.is_suppressed(lines, 1, block_state=None)

    # Assert
    assert result is True


def test_suppression_is_suppressed_hook_marker():
    # Arrange
    lines = ["items.push(x); // allow-mutation -- justified"]

    # Act
    result = supp.is_suppressed(lines, 0, hook_marker="allow-mutation")

    # Assert
    assert result is True


def test_suppression_strip_strings_backslash():
    # Arrange
    line = 'const s = "a\\"b";'

    # Act
    result = supp._strip_strings(line)

    # Assert
    assert len(result) == len(line)
    assert "a" not in result.split('"')[1] if '"' in result else True


def test_suppression_has_inline_marker_outside_comment():
    # Arrange
    line = 'const s = "@ts-ignore comment-like";'

    # Act
    result = supp.has_inline_marker(line, "@ts-ignore")

    # Assert
    assert result is False


def test_suppression_has_inline_marker_in_block_comment():
    # Arrange
    line = "/* @ts-ignore */ items.push(x);"

    # Act
    result = supp.has_inline_marker(line, "@ts-ignore")

    # Assert
    assert result is True


def test_suppression_has_justification_trailer_no_match():
    # Arrange
    line = "// allow-mutation"

    # Act
    result = supp.has_justification_trailer(line)

    # Assert
    assert result is False


def test_suppression_has_justification_trailer_present():
    # Arrange
    line = "// allow-mutation -- legitimate use"

    # Act
    result = supp.has_justification_trailer(line)

    # Assert
    assert result is True


def test_suppression_preceding_disable_next_line():
    # Arrange
    lines = ["// eslint-disable-next-line", "items.push(x);"]

    # Act
    result = supp.is_suppressed(lines, 1)

    # Assert
    assert result is True


def test_suppression_lone_block_disable_helper_non_comment():
    # Arrange
    line = "items.push(x);"

    # Act
    result = supp._is_lone_block_disable(line)

    # Assert
    assert result is False


def test_suppression_lone_block_disable_with_eslint_disable():
    # Arrange
    line = "// eslint-disable"

    # Act
    result = supp._is_lone_block_disable(line)

    # Assert
    assert result is True


def test_suppression_has_ts_nocheck_directive_present():
    # Arrange
    lines = ["// @ts-nocheck", "items.push(x);"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is True


def test_suppression_has_ts_nocheck_directive_with_blank_lines():
    # Arrange
    lines = ["", "", "// @ts-nocheck", "code();"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is True


def test_suppression_has_ts_nocheck_directive_absent():
    # Arrange
    lines = ["// regular comment", "items.push(x);"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is False


def test_suppression_has_ts_nocheck_directive_past_scan_limit():
    # Arrange
    lines = [f"// filler {i}" for i in range(15)] + ["// @ts-nocheck"]

    # Act
    result = supp.has_ts_nocheck_directive(lines)

    # Assert
    assert result is False


def test_allowlists_skip_path_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.skip_path(path)

    # Assert
    assert result is True


def test_allowlists_skip_path_test_suffix():
    # Arrange
    path = "/repo/src/foo.test.ts"

    # Act
    result = allowlists.skip_path(path)

    # Assert
    assert result is True


def test_allowlists_skip_extension_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.skip_extension(path)

    # Assert
    assert result is True


def test_allowlists_is_hot_path_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.is_hot_path(path)

    # Assert
    assert result is False


def test_allowlists_is_hot_path_crypto():
    # Arrange
    path = "/repo/src/crypto/cipher.ts"

    # Act
    result = allowlists.is_hot_path(path)

    # Assert
    assert result is True


def test_allowlists_is_framework_receiver_pattern_match():
    # Arrange
    line = "app.router.push('/home');"

    # Act
    result = allowlists.is_framework_receiver(line, None)

    # Assert
    assert result is True


def test_allowlists_is_framework_receiver_unknown_owner():
    # Arrange
    line = "myList.push(x);"

    # Act
    result = allowlists.is_framework_receiver(line, "myList")

    # Assert
    assert result is False


def test_allowlists_is_state_mgmt_filename_empty():
    # Arrange
    path = ""

    # Act
    result = allowlists.is_state_mgmt_filename(path)

    # Assert
    assert result is False


def test_allowlists_is_state_mgmt_filename_slice():
    # Arrange
    path = "/repo/src/userSlice.ts"

    # Act
    result = allowlists.is_state_mgmt_filename(path)

    # Assert
    assert result is True


def test_allowlists_is_in_state_mgmt_scope_empty_window():
    # Arrange
    window = ""
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is False
    assert label is None


def test_allowlists_is_in_state_mgmt_scope_zustand():
    # Arrange
    window = "set(produce((draft) => { draft.count += 1; }))"
    file_path = "/repo/src/store.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is True
    assert label == "zustand-produce"


def test_allowlists_is_in_state_mgmt_scope_yjs():
    # Arrange
    window = "const arr = new Y.Array(); arr.push([1]);"
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is True
    assert label == "yjs-crdt"


def test_allowlists_is_in_state_mgmt_scope_filename_fallback():
    # Arrange
    window = "items.push(x);"
    file_path = "/repo/src/userSlice.ts"

    # Act
    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    # Assert
    assert in_scope is True
    assert label == "state-mgmt-filename"


def test_allowlists_is_param_reassign_allowed_name_yes():
    # Arrange
    name = "acc"

    # Act
    result = allowlists.is_param_reassign_allowed_name(name)

    # Assert
    assert result is True


def test_allowlists_is_param_reassign_allowed_name_no():
    # Arrange
    name = "myCustomVar"

    # Act
    result = allowlists.is_param_reassign_allowed_name(name)

    # Assert
    assert result is False


def test_assignments_extract_first_arg_balanced_simple():
    # Arrange
    masked = "Object.assign(target, source)"
    paren_idx = masked.find("(")

    # Act
    result = assignments._extract_first_arg(masked, paren_idx)

    # Assert
    assert result == "target"


def test_assignments_extract_first_arg_single_arg():
    # Arrange
    masked = "fn(only)"
    paren_idx = masked.find("(")

    # Act
    result = assignments._extract_first_arg(masked, paren_idx)

    # Assert
    assert result == "only"


def test_assignments_extract_first_arg_unbalanced_returns_none():
    # Arrange
    masked = "fn(unbalanced"
    paren_idx = masked.find("(")

    # Act
    result = assignments._extract_first_arg(masked, paren_idx)

    # Assert
    assert result is None


def test_assignments_extract_first_arg_nested_parens():
    # Arrange
    masked = "Object.assign(new Map(), source)"
    paren_idx = masked.find("(")

    # Act
    result = assignments._extract_first_arg(masked, paren_idx)

    # Assert
    assert result == "new Map()"


def test_assignments_iter_lines_skips_blanks():
    # Arrange
    text = "a\n\n   \nb"

    # Act
    result = assignments._iter_lines(text)

    # Assert
    assert len(result) == 2
    assert result[0][0] == 1
    assert result[1][0] == 4


def test_assignments_looks_like_declaration_const():
    # Arrange
    raw = "const x = 1;"
    masked = raw

    # Act
    result = assignments._looks_like_declaration(raw, masked)

    # Assert
    assert result is True


def test_assignments_looks_like_declaration_class_field():
    # Arrange
    raw = "  public name: string;"
    masked = raw

    # Act
    result = assignments._looks_like_declaration(raw, masked)

    # Assert
    assert result is True


def test_assignments_looks_like_declaration_typed_no_value():
    # Arrange
    raw = "  name: string"
    masked = raw

    # Act
    result = assignments._looks_like_declaration(raw, masked)

    # Assert
    assert result is True


def test_assignments_looks_like_declaration_assignment():
    # Arrange
    raw = "obj.prop = value"
    masked = raw

    # Act
    result = assignments._looks_like_declaration(raw, masked)

    # Assert
    assert result is False


def test_assignments_object_assign_unbalanced_skipped():
    # Arrange
    text = "Object.assign(target source"

    # Act
    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert result == []


def test_assignments_object_assign_fresh_target_skipped():
    # Arrange
    text = "Object.assign({}, target, source);"

    # Act
    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert result == []


def test_assignments_object_assign_object_create_skipped():
    # Arrange
    text = "Object.assign(Object.create(null), opts);"

    # Act
    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert result == []


def test_assignments_object_assign_named_target_flagged():
    # Arrange
    text = "Object.assign(existing, source);"

    # Act
    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert len(result) == 1
    assert result[0].detector == "object.assign"


def test_assignments_let_could_be_const_for_head_skipped():
    # Arrange
    text = "for (let i = 0; i < 10; i++) { x++; }"

    # Act
    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_assignments_let_could_be_const_unmodified_flagged():
    # Arrange
    text = "let x = 1;\nconsole.warn(x);"

    # Act
    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert len(result) == 1
    assert result[0].detector == "let.could-be-const"


def test_assignments_let_could_be_const_reassigned_skipped():
    # Arrange
    text = "let x = 1;\nx = 2;"

    # Act
    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_assignments_let_could_be_const_no_lets():
    # Arrange
    text = "const x = 1;\nconst y = 2;"

    # Act
    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_assignments_collect_param_names_arrow_function():
    # Arrange
    text = "const fn = (alpha, beta) => alpha + beta;"

    # Act
    names = assignments._collect_param_names(text)

    # Assert
    assert "alpha" in names
    assert "beta" in names


def test_assignments_collect_param_names_skips_destructured():
    # Arrange
    text = "function fn({ a }, ...rest) { return rest; }"

    # Act
    names = assignments._collect_param_names(text)

    # Assert
    assert "a" not in names
    assert "rest" not in names


def test_methods_iter_lines_skips_blanks():
    # Arrange
    text = "a\n\nb"

    # Act
    result = methods._iter_lines(text)

    # Assert
    assert len(result) == 2


def test_methods_bracket_dispatch_in_string_skipped():
    # Arrange
    text = "const s = \"items['push'](x)\";"

    # Act
    result = methods.detect_bracket_dispatch(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_methods_bracket_dispatch_real_call_flagged():
    # Arrange
    text = "items['push'](value);"

    # Act
    result = methods.detect_bracket_dispatch(text, "ts", "/repo/src/app.ts")

    # Assert
    assert len(result) == 1
    assert "bracket-dispatch.push" in result[0].detector


def test_methods_collection_kind_weakset():
    # Arrange
    window = "const ws = new WeakSet();"

    # Act
    result = methods._collection_receiver_kind(window)

    # Assert
    assert result == "WeakSet"


def test_methods_collection_kind_set():
    # Arrange
    window = "const s = new Set();"

    # Act
    result = methods._collection_receiver_kind(window)

    # Assert
    assert result == "Set"


def test_methods_collection_kind_inconclusive():
    # Arrange
    window = "const x = 1;"

    # Act
    result = methods._collection_receiver_kind(window)

    # Assert
    assert result is None


def test_hook_file_marker_blank_lines_then_marker():
    # Arrange
    lines = ["", "", "// @allow-mutation -- justified", "items.push(x);"]

    # Act
    result = HOOK_MODULE._file_marker_active(lines)

    # Assert
    assert result is True


def test_hook_file_marker_without_justification_inactive():
    # Arrange
    lines = ["// @allow-mutation", "items.push(x);"]

    # Act
    result = HOOK_MODULE._file_marker_active(lines)

    # Assert
    assert result is False


def test_hook_file_marker_past_top_scan_limit():
    # Arrange
    lines = [f"const v{i} = 1;" for i in range(15)] + [
        "// @allow-mutation -- late"
    ]

    # Act
    result = HOOK_MODULE._file_marker_active(lines)

    # Assert
    assert result is False


def test_hook_line_only_marker_excludes_file_form():
    # Arrange
    line = "// @allow-mutation -- file form"

    # Act
    result = HOOK_MODULE._is_line_only_marker(line)

    # Assert
    assert result is False


def test_hook_line_only_marker_with_justification():
    # Arrange
    line = "items.push(x); // allow-mutation -- justified"

    # Act
    result = HOOK_MODULE._is_line_only_marker(line)

    # Assert
    assert result is True


def test_hook_line_allow_marker_invalid_index():
    # Arrange
    lines = ["a"]

    # Act
    result = HOOK_MODULE._line_allow_marker_active(lines, 5)

    # Assert
    assert result is False


def test_hook_line_allow_marker_negative_index():
    # Arrange
    lines = ["a"]

    # Act
    result = HOOK_MODULE._line_allow_marker_active(lines, -1)

    # Assert
    assert result is False


def test_hook_line_allow_marker_same_line():
    # Arrange
    lines = ["items.push(x); // allow-mutation -- justified"]

    # Act
    result = HOOK_MODULE._line_allow_marker_active(lines, 0)

    # Assert
    assert result is True


def test_hook_line_allow_marker_preceding_line():
    # Arrange
    lines = ["// allow-mutation -- justified", "items.push(x);"]

    # Act
    result = HOOK_MODULE._line_allow_marker_active(lines, 1)

    # Assert
    assert result is True


def test_hook_inside_state_mgmt_scope_empty_lines_state_filename():
    # Arrange
    lines: list[str] = []
    file_path = "/repo/src/userSlice.ts"

    # Act
    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 0, file_path)

    # Assert
    assert in_scope is True
    assert label == "state-mgmt-filename"


def test_hook_inside_state_mgmt_scope_empty_lines_regular_path():
    # Arrange
    lines: list[str] = []
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 0, file_path)

    # Assert
    assert in_scope is False
    assert label is None


def test_hook_inside_state_mgmt_scope_blank_opener():
    # Arrange
    lines = [
        "createSlice({",
        "",
        "  reducers: {",
        "    inc(state) { state.count += 1; }",
        "  }",
        "})",
    ]
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 3, file_path)

    # Assert
    assert in_scope is True
    assert label == "redux-toolkit"


def test_hook_inside_state_mgmt_scope_yjs_receiver_match():
    # Arrange
    lines = [
        "const yArr = new Y.Array();",
        "yArr.push([1]);",
    ]
    file_path = "/repo/src/app.ts"

    # Act
    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 1, file_path)

    # Assert
    assert in_scope is True
    assert label == "yjs-crdt"


def test_hook_main_invalid_json_payload(monkeypatch):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO("not-json"))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 0


def test_hook_main_disable_env(monkeypatch):
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_DISABLE", "1")
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO('{"tool_name": "Write"}'))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 0


def test_hook_main_no_findings_perf_budget_exceeded(monkeypatch, capsys):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "const x = 1;"},
    }
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    counter = iter([0.0, 1.0])
    monkeypatch.setattr(HOOK_MODULE.time, "perf_counter", lambda: next(counter))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 0


def test_hook_main_block_perf_budget_exceeded(monkeypatch, capsys):
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(x);"},
    }
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    counter = iter([0.0, 1.0])
    monkeypatch.setattr(HOOK_MODULE.time, "perf_counter", lambda: next(counter))

    # Act
    result = HOOK_MODULE.main()

    # Assert
    assert result == 2
    captured = capsys.readouterr()
    assert "array.push" in captured.err


def test_hook_normalize_payload_unsupported_tool():
    # Arrange
    tool = "Bash"
    tool_input = {"command": "ls"}

    # Act
    result = HOOK_MODULE._normalize_payload(tool, tool_input)

    # Assert
    assert result == []


def test_hook_normalize_payload_multi_edit_with_dict_edits():
    # Arrange
    tool = "MultiEdit"
    tool_input = {
        "file_path": "/repo/src/app.ts",
        "edits": [
            {"new_string": "items.push(x);"},
            "not-a-dict",
            {"new_string": 123},
        ],
    }

    # Act
    result = HOOK_MODULE._normalize_payload(tool, tool_input)

    # Assert
    assert len(result) == 1
    assert result[0][0] == "/repo/src/app.ts"
    assert result[0][2] == "items.push(x);"


def test_hook_format_findings_truncates_after_max():
    # Arrange
    matches = [
        core.Match(
            line=i, col=1, text=f"line{i}", detector="array.push", fix_hint="hint"
        )
        for i in range(1, 12)
    ]

    # Act
    out = HOOK_MODULE._format_findings("/repo/src/app.ts", matches)

    # Assert
    assert any("more" in line for line in out)


def test_hook_build_message_contains_rule_reference():
    # Arrange
    findings = ["  - /repo/src/app.ts:", "      L1:1 [array.push] items.push(x);"]

    # Act
    msg = HOOK_MODULE._build_message(findings)

    # Assert
    assert "Immutability" in msg
    assert "array.push" in msg


def test_hook_filter_matches_file_marker_suppresses_all():
    # Arrange
    text = "// @allow-mutation -- justified\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons == {"file-marker": 1}


def test_hook_filter_matches_param_allowlist_property_skipped():
    # Arrange
    text = "function reduce(acc, x) { acc.foo = x; }"
    matches = [
        core.Match(
            line=1,
            col=27,
            text=text,
            detector="property.assignment",
            metadata={"receiver": "acc", "prop": "foo"},
        )
    ]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons.get("param-allowlist") == 1


def test_hook_filter_matches_framework_receiver_array_push_skipped():
    # Arrange
    text = "router.push('/home');\n"
    matches = [
        core.Match(
            line=1,
            col=1,
            text=text.strip(),
            detector="array.push",
            metadata={"owner": "router"},
        )
    ]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons.get("framework-receiver") == 1


def test_hook_filter_matches_ts_nocheck_suppresses_all():
    # Arrange
    text = "// @ts-nocheck\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    # Act
    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    # Assert
    assert survived == []
    assert reasons == {"ts-nocheck": 1}


def test_hook_inside_state_mgmt_scope_same_line_immer_produce():
    # Arrange
    lines = ["const next = produce(state, (draft) => { draft.items.push(1); });"]

    # Act
    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(
        lines, 0, "/repo/src/feature.ts"
    )

    # Assert
    assert in_scope is True
    assert label == "immer-produce"
