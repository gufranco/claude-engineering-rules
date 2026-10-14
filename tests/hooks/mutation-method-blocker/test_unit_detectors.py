from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "hooks"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import mutation_detectors_assignments as assignments  # noqa: E402
from _lib import mutation_detectors_bindings as bindings  # noqa: E402
from _lib import mutation_detectors_builtins as builtins  # noqa: E402
from _lib import mutation_detectors_methods as methods  # noqa: E402


def test_assignments_extract_first_arg_balanced_simple():
    # Arrange
    masked = "Object.assign(target, source)"
    paren_idx = masked.find("(")

    # Act
    result = builtins._extract_first_arg(masked, paren_idx)

    # Assert
    assert result == "target"


def test_assignments_extract_first_arg_single_arg():
    # Arrange
    masked = "fn(only)"
    paren_idx = masked.find("(")

    # Act
    result = builtins._extract_first_arg(masked, paren_idx)

    # Assert
    assert result == "only"


def test_assignments_extract_first_arg_unbalanced_returns_none():
    # Arrange
    masked = "fn(unbalanced"
    paren_idx = masked.find("(")

    # Act
    result = builtins._extract_first_arg(masked, paren_idx)

    # Assert
    assert result is None


def test_assignments_extract_first_arg_nested_parens():
    # Arrange
    masked = "Object.assign(new Map(), source)"
    paren_idx = masked.find("(")

    # Act
    result = builtins._extract_first_arg(masked, paren_idx)

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
    result = builtins.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert result == []


def test_assignments_object_assign_fresh_target_skipped():
    # Arrange
    text = "Object.assign({}, target, source);"

    # Act
    result = builtins.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert result == []


def test_assignments_object_assign_object_create_skipped():
    # Arrange
    text = "Object.assign(Object.create(null), opts);"

    # Act
    result = builtins.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert result == []


def test_assignments_object_assign_named_target_flagged():
    # Arrange
    text = "Object.assign(existing, source);"

    # Act
    result = builtins.detect_object_assign_target_mutation(
        text, "ts", "/repo/src/app.ts"
    )

    # Assert
    assert len(result) == 1
    assert result[0].detector == "object.assign"


def test_assignments_let_could_be_const_for_head_skipped():
    # Arrange
    text = "for (let i = 0; i < 10; i++) { x++; }"

    # Act
    result = bindings.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_assignments_let_could_be_const_unmodified_flagged():
    # Arrange
    text = "let x = 1;\nconsole.warn(x);"

    # Act
    result = bindings.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert len(result) == 1
    assert result[0].detector == "let.could-be-const"


def test_assignments_let_could_be_const_reassigned_skipped():
    # Arrange
    text = "let x = 1;\nx = 2;"

    # Act
    result = bindings.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_assignments_let_could_be_const_no_lets():
    # Arrange
    text = "const x = 1;\nconst y = 2;"

    # Act
    result = bindings.detect_let_could_be_const(text, "ts", "/repo/src/app.ts")

    # Assert
    assert result == []


def test_assignments_collect_param_names_arrow_function():
    # Arrange
    text = "const fn = (alpha, beta) => alpha + beta;"

    # Act
    names = bindings._collect_param_names(text)

    # Assert
    assert "alpha" in names
    assert "beta" in names


def test_assignments_collect_param_names_skips_destructured():
    # Arrange
    text = "function fn({ a }, ...rest) { return rest; }"

    # Act
    names = bindings._collect_param_names(text)

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
