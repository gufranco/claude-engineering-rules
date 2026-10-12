from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.output import (  # noqa: E402
    DECISION_VERBS,
    block,
    validate_block_message,
    warn,
)


class TestBlock:
    def test_renders_all_required_sections_in_order(self) -> None:
        # Arrange
        hook = "example"

        # Act
        msg = block(
            hook=hook,
            rule_anchor="rules/example.md",
            detected="`as any` cast at file.ts:42",
            why="defeats type narrowing; downstream code crashes at runtime",
            fix="replace with typed assertion or branded type\n  bad: `x as any`\n  good: `x as MyType`",
            bypass_when="generated code where types are intentionally erased",
            decision="STOP-AND-ASK",
            env_var="EXAMPLE_DISABLE",
        )

        # Assert
        assert msg.startswith("BLOCKED by example") is True
        ordered = [
            "What was detected:",
            "Why this rule exists:",
            "How to fix:",
            "If the rule does not apply here:",
            "Decision guidance for Claude:",
        ]
        positions = [msg.index(label) for label in ordered]
        assert positions == sorted(positions)

    def test_includes_rule_anchor(self) -> None:
        # Arrange
        hook = "x"

        # Act
        msg = block(
            hook=hook,
            rule_anchor="rules/x.md",
            detected="a",
            why="b",
            fix="c",
            bypass_when="d",
            decision="FIX-AND-RETRY",
            env_var="X_DISABLE",
        )

        # Assert
        assert "rules/x.md" in msg

    def test_includes_both_bypass_channels(self) -> None:
        # Arrange
        hook = "hook-x"

        # Act
        msg = block(
            hook=hook,
            rule_anchor="rules/x.md",
            detected="a",
            why="b",
            fix="c",
            bypass_when="d",
            decision="BYPASS-WITH-REASON",
            env_var="HOOK_X_DISABLE",
        )

        # Assert
        assert "HOOK_X_DISABLE" in msg
        assert "scripts/bypass.py" in msg

    def test_includes_decision_verb(self) -> None:
        # Arrange
        hook = "x"

        # Act
        msg = block(
            hook=hook,
            rule_anchor="rules/x.md",
            detected="a",
            why="b",
            fix="c",
            bypass_when="d",
            decision="BYPASS-ONCE",
            env_var="X_DISABLE",
        )

        # Assert
        assert "BYPASS-ONCE" in msg

    @pytest.mark.parametrize("verb", sorted(DECISION_VERBS))
    def test_accepts_each_canonical_verb(self, verb: str) -> None:
        # Arrange
        hook = "x"

        # Act
        msg = block(
            hook=hook,
            rule_anchor="rules/x.md",
            detected="a",
            why="b",
            fix="c",
            bypass_when="d",
            decision=verb,
            env_var="X_DISABLE",
        )

        # Assert
        assert verb in msg

    def test_rejects_unknown_verb(self) -> None:
        # Arrange
        hook = "x"

        # Act
        with pytest.raises(ValueError) as raised:
            block(
                hook=hook,
                rule_anchor="rules/x.md",
                detected="a",
                why="b",
                fix="c",
                bypass_when="d",
                decision="PROBABLY-OK",
                env_var="X_DISABLE",
            )

        # Assert
        assert str(raised.value) == (
            "unknown decision verb 'PROBABLY-OK'; expected one of "
            "['BYPASS-ONCE', 'BYPASS-WITH-REASON', 'FIX-AND-RETRY', 'STOP-AND-ASK']"
        )

    def test_truncates_long_detected_line(self) -> None:
        # Arrange
        long_snippet = "X" * 500

        # Act
        msg = block(
            hook="x",
            rule_anchor="rules/x.md",
            detected=long_snippet,
            why="b",
            fix="c",
            bypass_when="d",
            decision="FIX-AND-RETRY",
            env_var="X_DISABLE",
        )

        # Assert
        assert max(len(line) for line in msg.splitlines()) <= 240


class TestWarn:
    def test_warn_renders_minimal_sections(self) -> None:
        # Arrange
        hook = "example"

        # Act
        msg = warn(
            hook=hook,
            purpose="batched edit accumulator",
            saved_to="~/.claude/cache/edit-batch.txt",
            next_action="Stop hook formats and clears the batch",
        )

        # Assert
        assert "INFO from example" in msg
        assert "Purpose:" in msg
        assert "Saved to:" in msg
        assert "Next:" in msg


class TestValidator:
    def test_passes_well_formed_block(self) -> None:
        # Arrange
        msg = block(
            hook="x",
            rule_anchor="rules/x.md",
            detected="a",
            why="b",
            fix="c",
            bypass_when="d",
            decision="STOP-AND-ASK",
            env_var="X_DISABLE",
        )

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert issues == []

    def test_flags_missing_section(self) -> None:
        # Arrange
        msg = "BLOCKED by x (rules/x.md)\n\nWhat was detected:\n  a\n"

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert "missing required section 'Why this rule exists:'" in issues
        assert "missing required section 'Decision guidance for Claude:'" in issues

    def test_flags_wrong_decision_verb(self) -> None:
        # Arrange
        msg = (
            "BLOCKED by x (rules/x.md)\n\n"
            "What was detected:\n  a\n\n"
            "Why this rule exists:\n  b\n\n"
            "How to fix:\n  c\n\n"
            "If the rule does not apply here:\n  d\n"
            "  env: X_DISABLE=1\n"
            "  file: scripts/bypass.py set x\n\n"
            "Decision guidance for Claude:\n  IGNORE\n"
        )

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert issues == [
            "decision verb 'IGNORE' is not one of "
            "['BYPASS-ONCE', 'BYPASS-WITH-REASON', 'FIX-AND-RETRY', 'STOP-AND-ASK']"
        ]

    def test_flags_missing_header(self) -> None:
        # Arrange
        msg = (
            "no header here\n\n"
            "What was detected:\n  a\n\n"
            "Why this rule exists:\n  b\n\n"
            "How to fix:\n  c\n\n"
            "If the rule does not apply here:\n  d\n"
            "  env: X_DISABLE=1\n"
            "  file: scripts/bypass.py set x\n\n"
            "Decision guidance for Claude:\n  STOP-AND-ASK\n"
        )

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert issues == ["missing 'BLOCKED by <hook>' header on first line"]

    def test_flags_missing_env_channel(self) -> None:
        # Arrange
        msg = (
            "BLOCKED by x (rules/x.md)\n\n"
            "What was detected:\n  a\n\n"
            "Why this rule exists:\n  b\n\n"
            "How to fix:\n  c\n\n"
            "If the rule does not apply here:\n  d\n"
            "  file: scripts/bypass.py set x\n\n"
            "Decision guidance for Claude:\n  STOP-AND-ASK\n"
        )

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert issues == ["bypass section is missing the env-var channel reference"]

    def test_flags_missing_file_channel(self) -> None:
        # Arrange
        msg = (
            "BLOCKED by x (rules/x.md)\n\n"
            "What was detected:\n  a\n\n"
            "Why this rule exists:\n  b\n\n"
            "How to fix:\n  c\n\n"
            "If the rule does not apply here:\n  d\n"
            "  env: X_DISABLE=1\n\n"
            "Decision guidance for Claude:\n  STOP-AND-ASK\n"
        )

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert issues == [
            "bypass section is missing the file-registry channel reference"
        ]

    def test_flags_out_of_order_sections(self) -> None:
        # Arrange
        msg = (
            "BLOCKED by x (rules/x.md)\n\n"
            "Why this rule exists:\n  b\n\n"
            "What was detected:\n  a\n\n"
            "How to fix:\n  c\n\n"
            "If the rule does not apply here:\n  d\n"
            "  env: X_DISABLE=1\n"
            "  file: scripts/bypass.py set x\n\n"
            "Decision guidance for Claude:\n  STOP-AND-ASK\n"
        )

        # Act
        issues = validate_block_message(msg)

        # Assert
        assert issues == ["section 'Why this rule exists:' appears out of order"]
