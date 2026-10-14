from __future__ import annotations

from types import ModuleType

import pytest


def test_em_dash_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Plain prose with " + chr(0x2014) + " in it."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["banned-em-dash"]


def test_box_drawing_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "ASCII art line " + chr(0x2500) + chr(0x2500) + " is bad."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["banned-box-drawing"]


def test_emoji_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Decorative emoji " + chr(0x1F300) + " in prose."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["banned-emoji"]


def test_should_bullet_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "- Should validate input."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["should-bullet"]


def test_banned_phrases_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Great question! Here is the answer."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["banned-opener"]


def test_banned_fluff_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "We need a robust solution."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["banned-fluff"]


def test_banned_tactical_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Apply a quick fix and move on."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["banned-tactical"]


def test_vague_quantifier_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "- often the cause of flaky tests is shared state"

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["vague-quantifier"]


def test_vague_quantifier_in_prose_not_flagged(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Tests are often flaky on Mondays."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == []


def test_parens_in_prose_detected(audit_mod: ModuleType) -> None:
    # Arrange
    text = "This is a parenthetical (clause) in prose."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["parens-in-prose"]


def test_code_fence_suppresses_detection(audit_mod: ModuleType) -> None:
    # Arrange
    text = "\n".join(
        [
            "Regular line.",
            "```python",
            "# Should validate input.",
            "x = (1 + 2)",
            "```",
            "Regular line again.",
        ]
    )

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.line for f in findings] == []


def test_inline_code_suppresses_detection(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Use the `should()` helper to assert."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == []


def test_table_row_skips_parens_check(audit_mod: ModuleType) -> None:
    # Arrange
    text = "| col1 (a) | col2 (b) |"

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == []


def test_heading_skips_parens_check(audit_mod: ModuleType) -> None:
    # Arrange
    text = "## Title (subtitle)"

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == []


def test_link_text_with_parens_does_not_trigger(audit_mod: ModuleType) -> None:
    # Arrange
    text = "See [the doc](path/to/doc.md) for details."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == []


def test_empty_parens_skipped(audit_mod: ModuleType) -> None:
    # Arrange
    text = "Function call myFunction() in prose."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == []


@pytest.mark.parametrize(
    "text",
    [
        "Use `GAN_EVAL_MODE` (default `playwright`) for visual checks.",
        "Set the limit (default 50) before deployment.",
        "Pass the header (default: application/json) on every request.",
    ],
)
def test_default_carveout(audit_mod: ModuleType, text: str) -> None:
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert [f.category for f in findings] == []


@pytest.mark.parametrize(
    "text",
    [
        "The full URL (REQUIRED) must include the scheme.",
        "The retry header (OPTIONAL) overrides the default.",
        "Use UUID v7 (RECOMMENDED) for new tables.",
        "Use UUID v7 (RECOMMENDED DEFAULT) for new tables.",
    ],
)
def test_emphasis_label_carveout(audit_mod: ModuleType, text: str) -> None:
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert [f.category for f in findings] == []


@pytest.mark.parametrize(
    "text",
    [
        "Validate at boundaries (e.g., HTTP handlers and queue consumers).",
        "Validate at boundaries (e.g. HTTP handlers).",
        "Choose a parser (i.e., Zod or Valibot) for runtime validation.",
        "Choose a parser (i.e. Zod) for runtime validation.",
    ],
)
def test_eg_ie_carveout(audit_mod: ModuleType, text: str) -> None:
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert [f.category for f in findings] == []


@pytest.mark.parametrize(
    "text",
    [
        "Apply the test rule (see testing.md) for every commit.",
        "Use Zod (per code-style.md) at boundaries.",
    ],
)
def test_see_per_carveout(audit_mod: ModuleType, text: str) -> None:
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert [f.category for f in findings] == []


@pytest.mark.parametrize(
    "text",
    [
        "The handler (which also runs on websockets) validates the input.",
        "the cache (the Redis store) holds the value",
    ],
)
def test_aside_still_flagged(audit_mod: ModuleType, text: str) -> None:
    # Arrange
    rel_path = "doc.md"

    # Act
    findings = audit_mod.scan_text(rel_path, text)

    # Assert
    assert [f.category for f in findings] == ["parens-in-prose"]


def test_lowercase_required_still_flagged(audit_mod: ModuleType) -> None:
    # Arrange
    text = "The full URL (required) must include the scheme."

    # Act
    findings = audit_mod.scan_text("doc.md", text)

    # Assert
    assert [f.category for f in findings] == ["parens-in-prose"]
