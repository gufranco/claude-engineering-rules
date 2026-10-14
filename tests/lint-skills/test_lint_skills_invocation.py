from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest


from _helpers.lint_skills_support import (
    COMPLETE_FIELDS,
    LINTER,
    make_skill,
    run_linter,
)


STRICT_YAML_CORPUS = (
    "a: plain value",
    "a: x: y",
    "a: ends with colon:",
    "a: @mention",
    "a: `tick",
    "a: %directive",
    "a: *alias",
    "a: !tag value",
    "a: ,comma",
    "a: ]bracket",
    "a: }brace",
    "a: - dash",
    "a: ? question",
    "a: -x",
    "a: x:y",
    "a: http://example.com/path",
    "a: value #comment",
    'a: "quoted: fine"',
    'a: "quoted" trailing',
    "a: 'it''s fine'",
    "a: 'single' trailing",
    "a: [x, y]",
    "a: |x",
    "a: |\n  literal: text",
    "a: >\n  folded: text",
    "a: x\n  more y",
    "a: x\n  more: y",
    "a:\n  - Read\n  - Edit",
)


def load_linter_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_skills", LINTER)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {LINTER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def yaml_accepts(raw: str) -> bool:
    yaml = pytest.importorskip("yaml")
    try:
        yaml.safe_load(raw)
    except yaml.YAMLError:
        return False
    return True


def test_warns_on_noop_user_invocable(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Adequate description with enough characters to pass the length check.\n"
        f"{COMPLETE_FIELDS}\n"
        "user-invocable: true"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "noop-user-invocable" in proc.stdout


def test_warns_on_trigger_list_on_user_invoked_skill(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: Deploys things. Use when user says "deploy" or "ship it".\n'
        "disable-model-invocation: true\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "trigger-list-on-user-invoked" in proc.stdout


def test_warns_on_routing_clause_on_user_invoked_skill(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Deploys things to production. Do NOT use for code review.\n"
        "disable-model-invocation: true\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "trigger-list-on-user-invoked" in proc.stdout


def test_user_invoked_one_line_description_passes_strict(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Merge a shipped PR, verify the deployment, and watch its health.\n"
        "disable-model-invocation: true\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_model_invoked_trigger_list_passes_strict(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: Deploys things to production. Use when user says "deploy".\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_default_discovery_skips_dot_and_harness_directories(tmp_path, full_body):
    # Arrange
    fm = (
        "name: kept\n"
        "description: Adequate description with enough characters to pass the length check."
    )
    make_skill(tmp_path, "kept", fm, full_body)
    make_skill(tmp_path, ".trash", "name: other", "no sections")
    make_skill(tmp_path, "synced", "name: other", "no sections")

    # Act
    proc = run_linter(["--skills-dir", str(tmp_path / "skills")])

    # Assert
    assert proc.returncode == 0, proc.stdout
    assert "1 files scanned, 0 errors" in proc.stdout


@pytest.mark.parametrize("raw", STRICT_YAML_CORPUS)
def test_strict_check_agrees_with_pyyaml(raw):
    # Arrange
    module = load_linter_module()

    # Act
    errors = module.find_yaml_errors(raw)

    # Assert
    assert (errors == []) is yaml_accepts(raw), errors
