from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked


HOOK = "accessibility-mechanical-checks"


def test_blocks_img_without_alt(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Page.tsx",
            "content": '<img src="/logo.png" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC001")


def test_blocks_input_without_label(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Form.tsx",
            "content": '<input type="text" name="email" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC002")


def test_blocks_role_button_on_div(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/X.tsx",
            "content": '<div role="button" onClick={handle}>Click</div>',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC003")


def test_blocks_positive_tabindex(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Form.tsx",
            "content": "<button tabIndex={3}>Submit</button>",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC004")


def test_blocks_html_without_lang(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/public/index.html",
            "content": "<html><head></head><body></body></html>",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC005")


def test_blocks_anchor_without_href(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Nav.tsx",
            "content": "<a onClick={go}>Profile</a>",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC006")


def test_blocks_click_on_div(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Card.tsx",
            "content": "<div onClick={handle}>Card</div>",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC007")


def test_blocks_password_without_autocomplete(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Login.tsx",
            "content": '<input type="password" name="pw" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC008")


def test_allows_img_with_alt(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Page.tsx",
            "content": '<img src="/logo.png" alt="Company logo" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_decorative_image_with_empty_alt(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Page.tsx",
            "content": '<img src="/decoration.png" alt="" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_input_with_aria_label(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Form.tsx",
            "content": '<input type="text" name="email" aria-label="Email address" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_password_with_autocomplete(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Login.tsx",
            "content": '<input type="password" name="pw" id="pw" autocomplete="current-password" aria-label="Password" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_html_with_lang(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/public/index.html",
            "content": '<html lang="en"><head></head><body></body></html>',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_test_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Page.test.tsx",
            "content": '<img src="/x.png" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_non_ui_extensions(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/util.ts",
            "content": '<img src="/x.png" />  // would have triggered in tsx but this is ts',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_disables(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Page.tsx",
            "content": '<img src="/x.png" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"ACCESSIBILITY_CHECKS_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_works_on_edit_payload(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/Page.tsx",
            "old_string": "old",
            "new_string": '<img src="/x.png" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC001")


def test_works_on_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/Page.tsx",
            "edits": [
                {"old_string": "a", "new_string": '<img src="/x.png" />'},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "AMC001")


def test_ignores_bash_tool(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": "echo '<img src=x>'"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_node_modules(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/lib/Page.tsx",
            "content": '<img src="/logo.png" />',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_empty_content_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/Empty.tsx",
            "content": "",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
