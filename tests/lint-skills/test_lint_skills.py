from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

LINTER = Path(__file__).resolve().parents[2] / "tools" / "lint-skills.py"

SECTION_HEADINGS = (
    "Overview",
    "When to Use",
    "Process",
    "Common Rationalizations",
    "Red Flags",
    "Verification",
)

COMPLETE_FIELDS = 'argument-hint: "/example"\nallowed-tools: "Read"'

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


def run_linter(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINTER), *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=apply_coverage_env(dict(os.environ)),
        check=False,
    )


@pytest.fixture
def full_body(faker: Faker) -> str:
    return "".join(f"## {heading}\n{faker.word()}\n" for heading in SECTION_HEADINGS)


def make_skill(root: Path, name: str, frontmatter: str, body: str) -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    sk = skill_dir / "SKILL.md"
    sk.write_text(f"---\n{frontmatter}\n---\n{body}")
    return sk


def test_full_template_passes_in_strict_mode(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Example skill that demonstrates the full template format expected by the linter."\n'
        'argument-hint: "/example <target>"\n'
        'allowed-tools: "Read, Edit"'
    )
    body = (
        "## Overview\nintro\n"
        "## When to Use\ntriggers\n"
        "## Process\nsteps\n"
        "## Common Rationalizations\nfailure modes\n"
        "## Red Flags\nwarnings\n"
        "## Verification\nself-check\n"
    )
    sk = make_skill(tmp_path, "example", fm, body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_accepts_section_aliases(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Skill with alias section names that should map to the canonical six."\n'
        'argument-hint: "/x"\n'
        'allowed-tools: "Read"'
    )
    body = (
        "## Summary\nintro\n"
        "## Triggers\nwhen to use\n"
        "## Steps\nprocess\n"
        "## Anti-patterns\ncommon rationalizations\n"
        "## Smells\nred flags\n"
        "## Self-check\nverification\n"
    )
    sk = make_skill(tmp_path, "example", fm, body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_errors_on_missing_frontmatter(tmp_path):
    # Arrange
    skill_dir = tmp_path / "skills" / "bad"
    skill_dir.mkdir(parents=True)
    sk = skill_dir / "SKILL.md"
    sk.write_text("Just a body with no frontmatter.\n## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "missing-frontmatter" in proc.stdout


def test_errors_on_missing_name(tmp_path):
    # Arrange
    fm = 'description: "A description without a name field, which should fail the linter."'
    sk = make_skill(tmp_path, "x", fm, "## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "missing-name" in proc.stdout


def test_errors_on_name_dir_mismatch(tmp_path):
    # Arrange
    fm = (
        "name: wrong\n"
        'description: "Name field does not match the parent directory name as required."'
    )
    sk = make_skill(tmp_path, "actual", fm, "## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "name-mismatch" in proc.stdout


def test_errors_on_missing_description(tmp_path):
    # Arrange
    fm = "name: example\n"
    sk = make_skill(tmp_path, "example", fm, "## Section\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "missing-description" in proc.stdout


def test_errors_on_no_sections(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Skill with valid frontmatter but no body sections at all."'
    )
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    sk = skill_dir / "SKILL.md"
    sk.write_text(f"---\n{fm}\n---\nJust prose, no headings.\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "no-sections" in proc.stdout


def test_warns_on_short_description(tmp_path):
    # Arrange
    fm = "name: example\ndescription: too short"
    sk = make_skill(tmp_path, "example", fm, "## Overview\nx\n")

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "short-description" in proc.stdout


def test_warns_on_missing_argument_hint(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'allowed-tools: "Read"'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "missing-argument-hint" in proc.stdout


def test_warns_on_missing_tool_scope(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'argument-hint: "/example"'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "missing-tool-scope" in proc.stdout


def test_warns_on_missing_sections(tmp_path):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'argument-hint: "/example"\n'
        'allowed-tools: "Read"'
    )
    body = "## Overview\nx\n## When to Use\nx\n"
    sk = make_skill(tmp_path, "example", fm, body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 0
    assert "missing-sections" in proc.stdout


def test_strict_mode_fails_on_warnings(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."\n'
        'allowed-tools: "Read"'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 1
    assert "[WARN ] missing-argument-hint: no `argument-hint` declared" in proc.stdout
    assert "1 files scanned, 0 errors, 1 warnings" in proc.stdout


def test_discovers_the_skill_file_inside_a_directory_argument(tmp_path):
    # Arrange
    fm = (
        "name: x\n"
        'description: "Adequate description with enough characters to pass the length check."'
    )
    sk = make_skill(
        tmp_path,
        "x",
        fm,
        "## Overview\n## When to Use\n## Process\n## Common Rationalizations\n## Red Flags\n## Verification\n",
    )
    skill_dir = sk.parent

    # Act
    proc = run_linter([str(skill_dir)])

    # Assert
    assert f"\n{sk}\n" in proc.stdout
    assert "1 files scanned, 0 errors, 2 warnings" in proc.stdout


def test_json_output(tmp_path):
    # Arrange
    fm = "description: missing name"
    sk = make_skill(tmp_path, "x", fm, "## Overview\n")

    # Act
    proc = run_linter([str(sk), "--json"])

    # Assert
    assert proc.returncode == 1
    parsed = json.loads(proc.stdout)
    codes = [f["code"] for file in parsed["files"] for f in file["findings"]]
    assert codes == [
        "missing-name",
        "short-description",
        "missing-argument-hint",
        "missing-tool-scope",
        "missing-sections",
    ]


def test_fix_hints_emit_extra_lines(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Adequate description with enough characters to pass the length check."'
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--fix-hints"])

    # Assert
    assert proc.returncode == 0
    assert 'Add: argument-hint: "<example invocation>"' in proc.stdout
    assert "1 files scanned, 0 errors, 2 warnings" in proc.stdout


def test_no_files_returns_error(tmp_path):
    # Arrange
    empty = tmp_path / "nothing"
    empty.mkdir()

    # Act
    proc = run_linter([str(empty)])

    # Assert
    assert proc.returncode == 1
    assert "no SKILL.md" in proc.stderr


def test_errors_on_unquoted_colon_space_in_description(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Ship code. Subcommands: commit, pr, release, checks.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "invalid-yaml: line 3" in proc.stdout


def test_errors_on_value_starting_with_reserved_indicator(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: @mention starts this description and breaks strict parsers.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "reserved indicator '@'" in proc.stdout


def test_errors_on_trailing_text_after_quoted_scalar(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "A quoted description" followed by stray trailing text.\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "text after the closing quote" in proc.stdout


def test_errors_on_colon_space_in_plain_continuation_line(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: A long description that wraps onto a second line\n"
        "  where a note: breaks the mapping.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "invalid-yaml: line 4" in proc.stdout


def test_errors_when_hash_after_space_truncates_plain_description(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: Fix a GitHub issue. Use when user says "fix issue #N" or similar.\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "truncated-by-comment: line 3" in proc.stdout


def test_errors_when_hash_after_space_truncates_continuation_line(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: A long description that wraps onto a second line\n"
        "  and then mentions issue #12 in passing.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk)])

    # Assert
    assert proc.returncode == 1
    assert "truncated-by-comment: line 4" in proc.stdout


def test_accepts_hash_inside_quoted_description(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: 'Fix a GitHub issue. Use when user says \"fix issue #N\" or similar.'\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_accepts_hash_without_preceding_space_in_plain_value(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Adequate description naming C# and issue-#7 without a comment marker.\n"
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_accepts_quoted_description_containing_colon_space(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        'description: "Ship code. Subcommands: commit, pr, release, and checks."\n'
        f"{COMPLETE_FIELDS}"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


def test_accepts_block_sequence_tool_list(tmp_path, full_body):
    # Arrange
    fm = (
        "name: example\n"
        "description: Adequate description with enough characters to pass the length check.\n"
        'argument-hint: "/example"\n'
        "allowed-tools:\n"
        "  - Read\n"
        "  - Edit"
    )
    sk = make_skill(tmp_path, "example", fm, full_body)

    # Act
    proc = run_linter([str(sk), "--strict"])

    # Assert
    assert proc.returncode == 0, proc.stdout


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
