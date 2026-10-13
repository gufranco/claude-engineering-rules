#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "frontend-render-gate.py"

if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
from _helpers.cov_env import apply_coverage_env  # noqa: E402

sys.path.insert(0, str(ROOT / "hooks"))
from _lib.bypass_writer import set_bypass  # noqa: E402

ALLOW = 0
BLOCK = 2


def run_hook(staged, command="git commit -m 'x'", env_extra=None, diff_exit=0):
    with tempfile.TemporaryDirectory() as tmp:
        stub = Path(tmp) / "git"
        stub.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "diff" ]; then\n'
            f"  printf '%s' \"{chr(10).join(staged)}\"\n"
            '  [ -n "$STAGED_EMPTY" ] || echo\n'
            f"  exit {diff_exit}\n"
            "fi\n"
            "exit 0\n"
        )
        stub.chmod(0o755)

        env = dict(os.environ)
        env["PATH"] = f"{tmp}:{env.get('PATH', '')}"
        env.pop("FRONTEND_RENDER_GATE_DISABLE", None)
        if env_extra:
            env.update(env_extra)

        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            env=apply_coverage_env(env),
            check=False,
        )
        return result


class RenderGateTest(unittest.TestCase):
    def test_blocks_component_change_with_no_render_check(self):
        # Arrange
        staged = ["apps/web/src/components/TopBar.tsx"]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("render-level check", result.stderr)

    def test_blocks_theme_token_change(self):
        # Arrange
        staged = ["apps/web/src/lib/theme.ts"]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, BLOCK)

    def test_blocks_stylesheet_change(self):
        # Arrange
        staged = ["apps/web/src/styles/globals.css"]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, BLOCK)

    def test_allows_when_an_acceptance_spec_is_touched(self):
        # Arrange
        staged = [
            "apps/web/src/components/TopBar.tsx",
            "test/acceptance/src/smoke.test.ts",
        ]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_allows_when_an_axe_helper_is_touched(self):
        # Arrange
        staged = [
            "apps/web/src/lib/theme.ts",
            "test/e2e/lib/accessibility.ts",
        ]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_allows_when_a_flutter_integration_test_is_touched(self):
        # Arrange
        staged = [
            "lib/pages/checkout.dart",
            "integration_test/checkout_test.dart",
        ]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_blocks_dart_change_carrying_only_a_widget_test(self):
        # Arrange
        staged = [
            "lib/pages/checkout.dart",
            "test/widget/checkout_test.dart",
        ]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("simulator", result.stderr)

    def test_allows_backend_only_change(self):
        # Arrange
        staged = ["apps/api/src/resolvers/order.ts"]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_ignores_storybook_and_generated_output(self):
        # Arrange
        staged = [
            "apps/web/src/components/TopBar.stories.tsx",
            "apps/web/dist/bundle.css",
            "apps/web/src/types/generated.d.ts",
        ]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_blocks_commit_behind_dash_c_with_a_spaced_path(self):
        # Arrange
        staged = ["apps/web/src/components/TopBar.tsx"]

        # Act
        result = run_hook(
            staged,
            command="git -C \"/tmp/my repo\" commit -m 'x'",
        )

        # Assert
        self.assertEqual(result.returncode, BLOCK)

    def test_blocks_commit_behind_an_inline_config_option(self):
        # Arrange
        staged = ["apps/web/src/components/TopBar.tsx"]

        # Act
        result = run_hook(
            staged,
            command="git -c core.editor=true commit -m 'x'",
        )

        # Assert
        self.assertEqual(result.returncode, BLOCK)

    def test_ignores_non_commit_commands(self):
        # Arrange
        staged = ["apps/web/src/components/TopBar.tsx"]

        # Act
        result = run_hook(staged, command="git status")

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_ignores_non_bash_tools(self):
        # Arrange
        payload = json.dumps(
            {"tool_name": "Edit", "tool_input": {"file_path": "a.tsx"}}
        )

        # Act
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            env=apply_coverage_env(dict(os.environ)),
            check=False,
        )

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_a_failing_git_diff_reads_as_nothing_staged(self):
        # Arrange
        staged = ["apps/web/src/components/TopBar.tsx"]

        # Act
        result = run_hook(staged, diff_exit=1)

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_a_long_file_list_names_how_many_more(self):
        # Arrange
        staged = [f"apps/web/src/components/Part{index}.tsx" for index in range(12)]

        # Act
        result = run_hook(staged)

        # Assert
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("... and 2 more", result.stderr)

    def test_a_live_bypass_entry_allows(self):
        # Arrange
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = Path(tmp.name) / "bypass.json"
        set_bypass("frontend-render-gate", ttl_seconds=120, state_path=state)

        # Act
        result = run_hook(
            ["apps/web/src/components/TopBar.tsx"],
            env_extra={"CLAUDE_BYPASS_STATE": str(state)},
        )

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_bypass_env_var_allows(self):
        # Arrange
        staged = ["apps/web/src/components/TopBar.tsx"]

        # Act
        result = run_hook(
            staged,
            env_extra={"FRONTEND_RENDER_GATE_DISABLE": "1"},
        )

        # Assert
        self.assertEqual(result.returncode, ALLOW)

    def test_malformed_payload_blocks(self):
        # Arrange
        argv = [sys.executable, str(HOOK)]

        # Act
        result = subprocess.run(
            argv,
            input="not json",
            capture_output=True,
            text=True,
            env=apply_coverage_env(dict(os.environ)),
            check=False,
        )

        # Assert
        self.assertEqual(result.returncode, BLOCK)


if __name__ == "__main__":
    unittest.main()
