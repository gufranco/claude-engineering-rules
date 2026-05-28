"""Coverage for privacy-leakage-checks hook.

Source rule: `~/.claude/rules/privacy-defaults.md`.
"""

from __future__ import annotations


HOOK = "privacy-leakage-checks"


def test_blocks_cookie_without_consent(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/track.ts",
            "content": 'document.cookie = "uid=123";',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC001")


def test_allows_cookie_with_consent_context(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/track.ts",
            "content": (
                "if (hasConsent('analytics')) {\n  document.cookie = \"uid=123\";\n}\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_blocks_console_log_email(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'console.log("user signed in: alice@example.com");',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC002")


def test_blocks_console_log_phone(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'console.log("verified: +1 415 555 0100");',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC002")


def test_blocks_console_log_ssn(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'console.log("ssn: 123-45-6789");',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC002")


def test_blocks_console_log_jwt(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": (
                "console.log('token: eyJxxxxxxxxxxxx.yyyyyyyyyyyy.zzzzzzzzzzzz');"
            ),
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC002")


def test_blocks_localstorage_email_key(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/auth.ts",
            "content": 'localStorage.setItem("userEmail", value);',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC003")


def test_blocks_localstorage_token_key(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/auth.ts",
            "content": 'localStorage.setItem("authToken", value);',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC003")


def test_blocks_ga4_tracker(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": 'gtag("config", "G-ABCDE12345");',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC004")


def test_blocks_gtm_tracker(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": 'window.gtag = window.dataLayer; var x = "GTM-ABCDE";',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC004")


def test_blocks_facebook_pixel(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": 'fbq("init", "123456789012345");',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC004")


def test_allows_tracker_with_consent(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": (
                "onConsentChange((categories) => {\n"
                '  if (categories.includes("analytics")) {\n'
                '    gtag("config", "G-ABCDE12345");\n'
                "  }\n"
                "});\n"
            ),
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_clean_code(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/util.ts",
            "content": "export function add(a: number, b: number): number {\n  return a + b;\n}\n",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_allows_logger_with_identifier(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'logger.info({ userId: "abc-123" }, "user logged in");',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_test_files(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.test.ts",
            "content": 'console.log("test email: alice@example.com");',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_bypass_env_disables(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'console.log("alice@example.com");',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload, env={"PRIVACY_CHECKS_DISABLE": "1"})


def test_works_on_edit_payload(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/login.ts",
            "old_string": "old",
            "new_string": 'console.log("alice@example.com");',
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC002")


def test_works_on_multiedit_payload(tool_use, assert_blocks):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/login.ts",
            "edits": [
                {"old_string": "a", "new_string": 'console.log("alice@example.com");'},
            ],
        },
    )

    # Act / Assert
    assert_blocks(HOOK, payload, "PLC002")


def test_ignores_bash_tool(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Bash",
        {"command": 'echo "alice@example.com"'},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_skips_node_modules(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/lib/x.ts",
            "content": 'console.log("alice@example.com");',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_empty_content_allows(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": "",
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_unknown_tool_allows(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/login.ts"},
    )

    # Act / Assert
    assert_allows(HOOK, payload)


def test_invalid_payload_via_subprocess():
    # Arrange
    import subprocess as sub
    import sys as _sys
    from pathlib import Path

    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "privacy-leakage-checks.py"
    )

    # Act
    proc = sub.run(
        [_sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    # Assert
    assert proc.returncode == 0


def test_skips_non_scan_extensions(tool_use, assert_allows):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/script.py",
            "content": 'print("alice@example.com")',
        },
    )

    # Act / Assert
    assert_allows(HOOK, payload)
