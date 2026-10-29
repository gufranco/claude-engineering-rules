from __future__ import annotations

from _helpers.hook_assertions import assert_allowed, assert_blocked

HOOK = "package-manager-guard"


def test_npm_install_is_blocked_with_the_pnpm_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "npm install zod"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "npm install zod: use pnpm install")
    assert "PACKAGE_MANAGER_GUARD_DISABLE" in stderr


def test_pip_install_is_blocked_with_the_uv_command(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "pip install requests"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "use uv add, uv sync or uv tool install")


def test_pnpm_and_non_bash_tools_pass_silently(tool_use, run_hook):
    # Arrange
    payloads = [
        tool_use("Bash", {"command": "corepack pnpm install --frozen-lockfile"}),
        tool_use("Write", {"file_path": "/repo/a.md", "content": "npm install"}),
    ]

    # Act
    results = [run_hook(HOOK, payload) for payload in payloads]

    # Assert
    assert [(r.code, r.stdout, r.stderr) for r in results] == [(0, "", "")] * 2


def test_the_disable_variable_lets_npm_through(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "npx tsc"})

    # Act
    result = run_hook(HOOK, payload, env={"PACKAGE_MANAGER_GUARD_DISABLE": "1"})

    # Assert
    assert_allowed(result)
