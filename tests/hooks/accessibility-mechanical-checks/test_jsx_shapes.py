from __future__ import annotations

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "accessibility-mechanical-checks"


def _write(tool_use, content: str):
    return tool_use("Write", {"file_path": "/repo/src/Panel.tsx", "content": content})


@pytest.mark.parametrize(
    "content",
    [
        '<div role="button" tabIndex={0} onKeyDown={onKey} onClick={() => go()}>Go</div>\n',
        '<img src={pick(() => url)} alt="Logo" />\n',
        '<Input name="email" />\n',
        '<button aria-label="Close"><svg /></button>\n',
        "<button><svg /> Save</button>\n",
        "// eslint-disable-next-line jsx-a11y/alt-text\n<img src={url} />\n",
    ],
    ids=[
        "keyboard-handler-after-arrow",
        "alt-after-arrow",
        "component-input",
        "labelled-icon-button",
        "icon-with-text",
        "eslint-directive",
    ],
)
def test_accessible_jsx_is_allowed(tool_use, run_hook, content):
    # Arrange
    payload = _write(tool_use, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ('<div role="button" onClick={() => go()}>Go</div>\n', "AMC003"),
        ("<button><svg /></button>\n", "AMC009"),
        ("<button>\n  <CloseIcon />\n</button>\n", "AMC009"),
        ("// eslint-disable-next-line no-console\n<img src={url} />\n", "AMC001"),
    ],
    ids=[
        "role-without-keys",
        "icon-only-svg",
        "icon-only-component",
        "other-rule-directive",
    ],
)
def test_inaccessible_jsx_is_blocked(tool_use, run_hook, content, code):
    # Arrange
    payload = _write(tool_use, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, code)


DEEP = "<div data-x={" + "{" * 11 + "1" + "}" * 11 + "} />\n"


@pytest.mark.parametrize(
    "content",
    ["<button\n", DEEP, "<button>\n  <svg />\n"],
    ids=["unclosed-tag", "deeply-nested-expression", "unclosed-button"],
)
def test_shapes_the_scanner_cannot_finish_are_allowed(tool_use, run_hook, content):
    # Arrange
    payload = _write(tool_use, content)

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
