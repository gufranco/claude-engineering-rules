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
SCRIPTS_DIR = REPO_ROOT / "hooks"
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

from _lib import mutation_allowlists as allowlists  # noqa: E402
from _lib import mutation_detectors_assignments as assignments  # noqa: E402
from _lib import mutation_detectors_core as core  # noqa: E402
from _lib import mutation_detectors_methods as methods  # noqa: E402
from _lib import suppression as supp  # noqa: E402


def test_detect_lang_empty_path():
    path = ""

    result = core.detect_lang(path)

    assert result is None


def test_detect_lang_unknown_extension():
    path = "/repo/src/app.rs"

    result = core.detect_lang(path)

    assert result is None


def test_detect_lang_tsx():
    path = "/repo/src/Component.tsx"

    result = core.detect_lang(path)

    assert result == "tsx"


def test_detect_lang_mjs_maps_to_js():
    path = "/repo/src/main.mjs"

    result = core.detect_lang(path)

    assert result == "js"


def test_supports_ast_none():
    lang = None

    result = core.supports_ast(lang)

    assert result is False


def test_supports_ast_unsupported():
    lang = "rust"

    result = core.supports_ast(lang)

    assert result is False


def test_supports_ast_tsx_true():
    lang = "tsx"

    result = core.supports_ast(lang)

    assert result is True


def test_strip_strings_comments_empty():
    line = ""

    result = core.strip_strings_comments(line)

    assert result == ""


def test_strip_strings_comments_unclosed_block_comment():
    line = "code /* unclosed comment continues forever"

    result = core.strip_strings_comments(line)

    assert result.startswith("code ")
    assert "unclosed" not in result


def test_strip_strings_comments_backslash_escape():
    line = 'const s = "a\\"b\\"c";'

    result = core.strip_strings_comments(line)

    assert "a" not in result.split('"')[1] if '"' in result else True
    assert len(result) == len(line)


def test_strip_strings_comments_template_literal_interpolation():
    line = "const s = `value=${user.name}`;"

    result = core.strip_strings_comments(line)

    assert len(result) == len(line)
    assert "${user.name}" not in result


def test_strip_strings_comments_template_with_nested_braces():
    line = "const s = `a${{x: 1}.x}b`;"

    result = core.strip_strings_comments(line)

    assert len(result) == len(line)


def test_strip_strings_comments_block_comment_closed():
    line = "code /* inner */ tail"

    result = core.strip_strings_comments(line)

    assert "inner" not in result
    assert result.endswith("tail")


def test_strip_strings_comments_line_comment():
    line = "code // tail comment"

    result = core.strip_strings_comments(line)

    assert "tail" not in result


def test_window_around_empty_lines():
    lines: list[str] = []

    result = core.window_around(lines, 5)

    assert result == ""


def test_window_around_clamp_lower():
    lines = ["a", "b", "c"]

    result = core.window_around(lines, 1, before=10, after=0)

    assert result == "a"


def test_window_around_clamp_upper():
    lines = ["a", "b", "c"]

    result = core.window_around(lines, 3, before=0, after=10)

    assert result == "c"


def test_truncate_excerpt_short():
    line = "  short  "

    result = core.truncate_excerpt(line, limit=120)

    assert result == "short"


def test_truncate_excerpt_long():
    line = "x" * 200

    result = core.truncate_excerpt(line, limit=10)

    assert result.endswith("...")
    assert len(result) <= 13


def test_ast_grep_path_disabled_via_env(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", None, raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", False, raising=False)
    monkeypatch.setenv("MUTATION_METHOD_AST", "0")

    result = core.ast_grep_path()

    assert result is None


def test_ast_grep_path_cached_returns_same(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/usr/bin/cached", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    first = core.ast_grep_path()
    second = core.ast_grep_path()

    assert first == "/usr/bin/cached"
    assert second == "/usr/bin/cached"


def test_ast_grep_path_resolves_via_which(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", None, raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", False, raising=False)
    monkeypatch.delenv("MUTATION_METHOD_AST", raising=False)
    monkeypatch.setattr(
        core.shutil,
        "which",
        lambda name: "/fake/ast-grep" if name == "ast-grep" else None,
    )

    result = core.ast_grep_path()

    assert result == "/fake/ast-grep"


def test_run_ast_grep_no_binary(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", None, raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    assert result == []


def test_run_ast_grep_unsupported_lang(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    result = core.run_ast_grep("$X.push($Y)", "code", "rust")

    assert result == []


def test_run_ast_grep_empty_source(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    result = core.run_ast_grep("$X.push($Y)", "", "ts")

    assert result == []


def test_run_ast_grep_timeout(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    def boom(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="ast-grep", timeout=2.0)

    monkeypatch.setattr(core.subprocess, "run", boom)

    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    assert result == []


def test_run_ast_grep_oserror(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)

    def boom(*_args, **_kwargs):
        raise OSError("not found")

    monkeypatch.setattr(core.subprocess, "run", boom)

    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    assert result == []


def test_run_ast_grep_non_zero_exit(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    monkeypatch.setattr(
        core.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=2, stdout="", stderr=""),
    )

    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    assert result == []


def test_run_ast_grep_valid_output(monkeypatch):
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

    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    assert len(result) == 2
    assert result[0].line == 5
    assert result[0].col == 3
    assert result[0].detector == "ast"
    assert result[0].node_type == "call_expression"


def test_run_ast_grep_exit_code_one_returns_no_matches(monkeypatch):
    monkeypatch.setattr(core, "_AST_GREP_PATH", "/fake/ast-grep", raising=False)
    monkeypatch.setattr(core, "_AST_GREP_RESOLVED", True, raising=False)
    monkeypatch.setattr(
        core.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    result = core.run_ast_grep("$X.push($Y)", "code", "ts")

    assert result == []


def test_suppression_lone_block_disable_recognized():
    lines = ["// eslint-disable", "items.push(x);", "items.pop();", "// eslint-enable"]

    state = supp.compute_block_state(lines)

    assert 0 in state.disabled_lines
    assert 1 in state.disabled_lines
    assert 2 in state.disabled_lines


def test_suppression_top_of_file_marker_blank_skip():
    lines = ["", "", "// @ts-nocheck", "items.push(x);"]

    result = supp.has_top_of_file_marker(lines, "@ts-nocheck")

    assert result is True


def test_suppression_top_of_file_marker_scan_limit():
    lines = [f"const x{i} = 1;" for i in range(15)] + ["// @ts-nocheck"]

    result = supp.has_top_of_file_marker(lines, "@ts-nocheck")

    assert result is False


def test_suppression_top_of_file_marker_empty_marker():
    lines = ["// foo"]

    result = supp.has_top_of_file_marker(lines, "")

    assert result is False


def test_suppression_is_suppressed_invalid_index_high():
    lines = ["a", "b"]

    result = supp.is_suppressed(lines, 5)

    assert result is False


def test_suppression_is_suppressed_negative_index():
    lines = ["a", "b"]

    result = supp.is_suppressed(lines, -1)

    assert result is False


def test_suppression_is_suppressed_block_state_none_computes():
    lines = ["/* eslint-disable */", "items.push(x);", "/* eslint-enable */"]

    result = supp.is_suppressed(lines, 1, block_state=None)

    assert result is True


def test_suppression_ignores_our_own_allow_marker():
    lines = ["items.push(x); // allow-mutation -- justified"]

    result = supp.is_suppressed(lines, 0)

    assert result is False


def test_suppression_strip_strings_backslash():
    line = 'const s = "a\\"b";'

    result = supp._strip_strings(line)

    assert len(result) == len(line)
    assert "a" not in result.split('"')[1] if '"' in result else True


def test_suppression_has_inline_marker_outside_comment():
    line = 'const s = "@ts-ignore comment-like";'

    result = supp.has_inline_marker(line, "@ts-ignore")

    assert result is False


def test_suppression_has_inline_marker_in_block_comment():
    line = "/* @ts-ignore */ items.push(x);"

    result = supp.has_inline_marker(line, "@ts-ignore")

    assert result is True


def test_suppression_preceding_disable_next_line():
    lines = ["// eslint-disable-next-line", "items.push(x);"]

    result = supp.is_suppressed(lines, 1)

    assert result is True


def test_suppression_lone_block_disable_helper_non_comment():
    line = "items.push(x);"

    result = supp._is_lone_block_disable(line)

    assert result is False


def test_suppression_lone_block_disable_with_eslint_disable():
    line = "// eslint-disable"

    result = supp._is_lone_block_disable(line)

    assert result is True


def test_suppression_has_ts_nocheck_directive_present():
    lines = ["// @ts-nocheck", "items.push(x);"]

    result = supp.has_ts_nocheck_directive(lines)

    assert result is True


def test_suppression_has_ts_nocheck_directive_with_blank_lines():
    lines = ["", "", "// @ts-nocheck", "code();"]

    result = supp.has_ts_nocheck_directive(lines)

    assert result is True


def test_suppression_has_ts_nocheck_directive_absent():
    lines = ["// regular comment", "items.push(x);"]

    result = supp.has_ts_nocheck_directive(lines)

    assert result is False


def test_suppression_has_ts_nocheck_directive_past_scan_limit():
    lines = [f"// filler {i}" for i in range(15)] + ["// @ts-nocheck"]

    result = supp.has_ts_nocheck_directive(lines)

    assert result is False


def test_allowlists_skip_path_empty():
    path = ""

    result = allowlists.skip_path(path)

    assert result is True


def test_allowlists_skip_path_test_suffix():
    path = "/repo/src/foo.test.ts"

    result = allowlists.skip_path(path)

    assert result is True


def test_allowlists_skip_extension_empty():
    path = ""

    result = allowlists.skip_extension(path)

    assert result is True


def test_allowlists_is_hot_path_empty():
    path = ""

    result = allowlists.is_hot_path(path)

    assert result is False


def test_allowlists_is_hot_path_crypto():
    path = "/repo/src/crypto/cipher.ts"

    result = allowlists.is_hot_path(path)

    assert result is True


def test_allowlists_is_framework_receiver_pattern_match():
    line = "app.router.push('/home');"

    result = allowlists.is_framework_receiver(line, None)

    assert result is True


def test_allowlists_is_framework_receiver_unknown_owner():
    line = "myList.push(x);"

    result = allowlists.is_framework_receiver(line, "myList")

    assert result is False


def test_allowlists_is_state_mgmt_filename_empty():
    path = ""

    result = allowlists.is_state_mgmt_filename(path)

    assert result is False


def test_allowlists_is_state_mgmt_filename_slice():
    path = "/repo/src/userSlice.ts"

    result = allowlists.is_state_mgmt_filename(path)

    assert result is True


def test_allowlists_is_in_state_mgmt_scope_empty_window():
    window = ""
    file_path = "/repo/src/app.ts"

    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    assert in_scope is False
    assert label is None


def test_allowlists_is_in_state_mgmt_scope_zustand():
    window = "set(produce((draft) => { draft.count += 1; }))"
    file_path = "/repo/src/store.ts"

    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    assert in_scope is True
    assert label == "zustand-produce"


def test_allowlists_is_in_state_mgmt_scope_yjs():
    window = "const arr = new Y.Array(); arr.push([1]);"
    file_path = "/repo/src/app.ts"

    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    assert in_scope is True
    assert label == "yjs-crdt"


def test_allowlists_is_in_state_mgmt_scope_filename_fallback():
    window = "items.push(x);"
    file_path = "/repo/src/userSlice.ts"

    in_scope, label = allowlists.is_in_state_mgmt_scope(window, file_path)

    assert in_scope is True
    assert label == "state-mgmt-filename"


def test_allowlists_is_param_reassign_allowed_name_yes():
    name = "acc"

    result = allowlists.is_param_reassign_allowed_name(name)

    assert result is True


def test_allowlists_is_param_reassign_allowed_name_no():
    name = "myCustomVar"

    result = allowlists.is_param_reassign_allowed_name(name)

    assert result is False


def test_assignments_extract_first_arg_balanced_simple():
    masked = "Object.assign(target, source)"
    paren_idx = masked.find("(")

    result = assignments._extract_first_arg(masked, paren_idx)

    assert result == "target"


def test_assignments_extract_first_arg_single_arg():
    masked = "fn(only)"
    paren_idx = masked.find("(")

    result = assignments._extract_first_arg(masked, paren_idx)

    assert result == "only"


def test_assignments_extract_first_arg_unbalanced_returns_none():
    masked = "fn(unbalanced"
    paren_idx = masked.find("(")

    result = assignments._extract_first_arg(masked, paren_idx)

    assert result is None


def test_assignments_extract_first_arg_nested_parens():
    masked = "Object.assign(new Map(), source)"
    paren_idx = masked.find("(")

    result = assignments._extract_first_arg(masked, paren_idx)

    assert result == "new Map()"


def test_assignments_iter_lines_skips_blanks():
    text = "a\n\n   \nb"

    result = assignments._iter_lines(text)

    assert len(result) == 2
    assert result[0][0] == 1
    assert result[1][0] == 4


def test_assignments_looks_like_declaration_const():
    raw = "const x = 1;"
    masked = raw

    result = assignments._looks_like_declaration(raw, masked)

    assert result is True


def test_assignments_looks_like_declaration_class_field():
    raw = "  public name: string;"
    masked = raw

    result = assignments._looks_like_declaration(raw, masked)

    assert result is True


def test_assignments_looks_like_declaration_typed_no_value():
    raw = "  name: string"
    masked = raw

    result = assignments._looks_like_declaration(raw, masked)

    assert result is True


def test_assignments_looks_like_declaration_assignment():
    raw = "obj.prop = value"
    masked = raw

    result = assignments._looks_like_declaration(raw, masked)

    assert result is False


def test_assignments_object_assign_unbalanced_skipped():
    text = "Object.assign(target source"

    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    assert result == []


def test_assignments_object_assign_fresh_target_skipped():
    text = "Object.assign({}, target, source);"

    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    assert result == []


def test_assignments_object_assign_object_create_skipped():
    text = "Object.assign(Object.create(null), opts);"

    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    assert result == []


def test_assignments_object_assign_named_target_flagged():
    text = "Object.assign(existing, source);"

    result = assignments.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    assert len(result) == 1
    assert result[0].detector == "object.assign"


def test_assignments_let_could_be_const_for_head_skipped():
    text = "for (let i = 0; i < 10; i++) { x++; }"

    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    assert result == []


def test_assignments_let_could_be_const_unmodified_flagged():
    text = "let x = 1;\nconsole.warn(x);"

    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    assert len(result) == 1
    assert result[0].detector == "let.could-be-const"


def test_assignments_let_could_be_const_reassigned_skipped():
    text = "let x = 1;\nx = 2;"

    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    assert result == []


def test_assignments_let_could_be_const_no_lets():
    text = "const x = 1;\nconst y = 2;"

    result = assignments.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    assert result == []


def test_assignments_collect_param_names_arrow_function():
    text = "const fn = (alpha, beta) => alpha + beta;"

    names = assignments._collect_param_names(text)

    assert "alpha" in names
    assert "beta" in names


def test_assignments_collect_param_names_skips_destructured():
    text = "function fn({ a }, ...rest) { return rest; }"

    names = assignments._collect_param_names(text)

    assert "a" not in names
    assert "rest" not in names


def test_methods_iter_lines_skips_blanks():
    text = "a\n\nb"

    result = methods._iter_lines(text)

    assert len(result) == 2


def test_methods_bracket_dispatch_in_string_skipped():
    text = "const s = \"items['push'](x)\";"

    result = methods.detect_bracket_dispatch(text, "ts", "/repo/src/app.ts")

    assert result == []


def test_methods_bracket_dispatch_real_call_flagged():
    text = "items['push'](value);"

    result = methods.detect_bracket_dispatch(text, "ts", "/repo/src/app.ts")

    assert len(result) == 1
    assert "bracket-dispatch.push" in result[0].detector


def test_methods_collection_kind_weakset():
    window = "const ws = new WeakSet();"

    result = methods._collection_receiver_kind(window)

    assert result == "WeakSet"


def test_methods_collection_kind_set():
    window = "const s = new Set();"

    result = methods._collection_receiver_kind(window)

    assert result == "Set"


def test_methods_collection_kind_inconclusive():
    window = "const x = 1;"

    result = methods._collection_receiver_kind(window)

    assert result is None


def test_hook_exposes_no_allow_marker_api():
    removed = (
        "_file_marker_active",
        "_line_allow_marker_active",
        "_is_line_only_marker",
        "ALLOW_FILE_MARKER",
        "ALLOW_LINE_MARKER",
    )

    present = [name for name in removed if hasattr(HOOK_MODULE, name)]

    assert present == []


def test_hook_inside_state_mgmt_scope_empty_lines_state_filename():
    lines: list[str] = []
    file_path = "/repo/src/userSlice.ts"

    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 0, file_path)

    assert in_scope is True
    assert label == "state-mgmt-filename"


def test_hook_inside_state_mgmt_scope_empty_lines_regular_path():
    lines: list[str] = []
    file_path = "/repo/src/app.ts"

    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 0, file_path)

    assert in_scope is False
    assert label is None


def test_hook_inside_state_mgmt_scope_blank_opener():
    lines = [
        "createSlice({",
        "",
        "  reducers: {",
        "    inc(state) { state.count += 1; }",
        "  }",
        "})",
    ]
    file_path = "/repo/src/app.ts"

    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 3, file_path)

    assert in_scope is True
    assert label == "redux-toolkit"


def test_hook_inside_state_mgmt_scope_yjs_receiver_match():
    lines = [
        "const yArr = new Y.Array();",
        "yArr.push([1]);",
    ]
    file_path = "/repo/src/app.ts"

    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(lines, 1, file_path)

    assert in_scope is True
    assert label == "yjs-crdt"


def test_hook_main_invalid_json_payload(monkeypatch):
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO("not-json"))

    result = HOOK_MODULE.main()

    assert result == 0


def test_hook_main_disable_env(monkeypatch):
    monkeypatch.setenv("MUTATION_METHOD_DISABLE", "1")
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO('{"tool_name": "Write"}'))

    result = HOOK_MODULE.main()

    assert result == 0


def test_hook_main_no_findings_perf_budget_exceeded(monkeypatch, capsys):
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "const x = 1;"},
    }
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    counter = iter([0.0, 1.0])
    monkeypatch.setattr(HOOK_MODULE.time, "perf_counter", lambda: next(counter))

    result = HOOK_MODULE.main()

    assert result == 0


def test_hook_main_block_perf_budget_exceeded(monkeypatch, capsys):
    monkeypatch.delenv("MUTATION_METHOD_DISABLE", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/src/app.ts", "content": "items.push(x);"},
    }
    monkeypatch.setattr(HOOK_MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    counter = iter([0.0, 1.0])
    monkeypatch.setattr(HOOK_MODULE.time, "perf_counter", lambda: next(counter))

    result = HOOK_MODULE.main()

    assert result == 2
    captured = capsys.readouterr()
    assert "array.push" in captured.err


def test_hook_normalize_payload_unsupported_tool():
    tool = "Bash"
    tool_input = {"command": "ls"}

    result = HOOK_MODULE._normalize_payload(tool, tool_input)

    assert result == []


def test_hook_normalize_payload_multi_edit_with_dict_edits():
    tool = "MultiEdit"
    tool_input = {
        "file_path": "/repo/src/app.ts",
        "edits": [
            {"new_string": "items.push(x);"},
            "not-a-dict",
            {"new_string": 123},
        ],
    }

    result = HOOK_MODULE._normalize_payload(tool, tool_input)

    assert len(result) == 1
    assert result[0][0] == "/repo/src/app.ts"
    assert result[0][2] == "items.push(x);"


def test_hook_format_findings_truncates_after_max():
    matches = [
        core.Match(
            line=i, col=1, text=f"line{i}", detector="array.push", fix_hint="hint"
        )
        for i in range(1, 12)
    ]

    out = HOOK_MODULE._format_findings("/repo/src/app.ts", matches)

    assert any("more" in line for line in out)


def test_hook_build_message_contains_rule_reference():
    findings = ["  - /repo/src/app.ts:", "      L1:1 [array.push] items.push(x);"]

    msg = HOOK_MODULE._build_message(findings)

    assert "Immutability" in msg
    assert "array.push" in msg


def test_hook_filter_matches_file_allow_marker_does_not_suppress():
    text = "// @allow-mutation -- justified\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    assert len(survived) == 1
    assert reasons == {}


def test_hook_filter_matches_ts_nocheck_still_suppresses():
    text = "// @ts-nocheck\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    assert survived == []
    assert reasons == {"ts-nocheck": 1}


def test_hook_filter_matches_param_allowlist_property_skipped():
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

    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    assert survived == []
    assert reasons.get("param-allowlist") == 1


def test_hook_filter_matches_framework_receiver_array_push_skipped():
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

    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    assert survived == []
    assert reasons.get("framework-receiver") == 1


def test_hook_filter_matches_ts_nocheck_suppresses_all():
    text = "// @ts-nocheck\nitems.push(x);\n"
    matches = [core.Match(line=2, col=1, text="items.push(x);", detector="array.push")]
    block_state = supp.compute_block_state(text.splitlines())

    survived, reasons = HOOK_MODULE._filter_matches(
        matches, text, "/repo/src/app.ts", block_state
    )

    assert survived == []
    assert reasons == {"ts-nocheck": 1}


def test_hook_inside_state_mgmt_scope_same_line_immer_produce():
    lines = ["const next = produce(state, (draft) => { draft.items.push(1); });"]

    in_scope, label = HOOK_MODULE._is_inside_state_mgmt_scope(
        lines, 0, "/repo/src/feature.ts"
    )

    assert in_scope is True
    assert label == "immer-produce"
