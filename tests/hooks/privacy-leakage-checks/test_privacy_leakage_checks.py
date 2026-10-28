from __future__ import annotations

import os
from _helpers.hook_assertions import assert_allowed, assert_blocked
import subprocess as sub
import sys as _sys
from pathlib import Path


HOOK = "privacy-leakage-checks"


def test_blocks_cookie_without_consent(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/track.ts",
            "content": 'document.cookie = "uid=123";',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC001")


def test_allows_cookie_with_consent_context(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_console_log_email(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": f'console.log("user signed in: {email}");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC002")


def test_blocks_console_log_phone(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'console.log("verified: +1 415 555 0100");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC002")


def test_blocks_console_log_ssn(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'console.log("ssn: 123-45-6789");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC002")


def test_blocks_console_log_jwt(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC002")


def test_blocks_localstorage_email_key(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/auth.ts",
            "content": 'localStorage.setItem("userEmail", value);',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC003")


def test_blocks_localstorage_token_key(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/auth.ts",
            "content": 'localStorage.setItem("authToken", value);',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC003")


def test_blocks_ga4_tracker(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": 'gtag("config", "G-ABCDE12345");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC004")


def test_blocks_gtm_tracker(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": 'window.gtag = window.dataLayer; var x = "GTM-ABCDE";',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC004")


def test_blocks_facebook_pixel(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/analytics.ts",
            "content": 'fbq("init", "123456789012345");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC004")


def test_allows_tracker_with_consent(tool_use, run_hook):
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

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_clean_code(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/util.ts",
            "content": "export function add(a: number, b: number): number {\n  return a + b;\n}\n",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_logger_with_identifier(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": 'logger.info({ userId: "abc-123" }, "user logged in");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_test_files(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.test.ts",
            "content": f'console.log("test email: {email}");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_bypass_env_disables(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/login.ts",
            "content": f'console.log("{email}");',
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"PRIVACY_CHECKS_DISABLE": "1"})

    # Assert
    assert_allowed(result)


def test_works_on_edit_payload(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/login.ts",
            "old_string": "old",
            "new_string": f'console.log("{email}");',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC002")


def test_works_on_multiedit_payload(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/login.ts",
            "edits": [
                {"old_string": "a", "new_string": f'console.log("{email}");'},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "PLC002")


def test_ignores_bash_tool(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Bash",
        {"command": f'echo "{email}"'},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_node_modules(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/node_modules/lib/x.ts",
            "content": f'console.log("{email}");',
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
            "file_path": "/repo/src/login.ts",
            "content": "",
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_unknown_tool_allows(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Read",
        {"file_path": "/repo/src/login.ts"},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_invalid_payload_via_subprocess_blocks():
    # Arrange
    hook_path = (
        Path(__file__).resolve().parents[3] / "hooks" / "privacy-leakage-checks.py"
    )

    # Act
    proc = sub.run(
        [_sys.executable, str(hook_path)],
        input="not valid json",
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_HOOK_AUDIT_DISABLE": "1",
            "CLAUDE_BYPASS_STATE": os.devnull,
        },
        timeout=30,
        check=False,
    )

    # Assert
    assert proc.returncode == 2
    assert "could not read its input" in proc.stderr


def test_skips_non_scan_extensions(tool_use, run_hook, faker):
    # Arrange
    email = faker.email()
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/script.py",
            "content": f'print("{email}")',
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_console_output_and_storage_keys_without_personal_data(
    tool_use, run_hook
):
    # Arrange
    content = (
        'console.log("cart total", total);\nlocalStorage.setItem("theme", "dark");\n'
    )
    payload = tool_use("Write", {"file_path": "/repo/src/cart.ts", "content": content})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert result.code == 0
