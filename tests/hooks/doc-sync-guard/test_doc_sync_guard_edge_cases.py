from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from doc_sync_guard_test_repo import (
    COMMIT,
    HOOK,
    _commit_all,
    _stage,
)


class TestDegradedEnvironment:
    def test_allows_when_git_is_unavailable(
        self, repo: Path, tool_use, run_hook, tmp_path: Path
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        empty_bin = tmp_path / "empty-bin"
        empty_bin.mkdir()
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload, env={"PATH": str(empty_bin)})

        # Assert
        assert_allowed(result)

    def test_allows_when_cwd_does_not_exist(self, tool_use, run_hook) -> None:
        # Arrange
        payload = tool_use("Bash", {"command": COMMIT}, cwd="/nonexistent/path/xyz")

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_blocks_when_stdin_is_not_json(self, repo: Path) -> None:
        # Arrange
        hook = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"

        # Act
        proc = subprocess.run(
            [sys.executable, str(hook)],
            input="{not json",
            capture_output=True,
            text=True,
            env={**os.environ},
            timeout=30,
            check=False,
        )

        # Assert
        assert proc.returncode == 2
        assert "could not read its input" in proc.stderr

    @pytest.mark.skipif(
        os.geteuid() == 0, reason="root reads files without permission bits"
    )
    def test_allows_when_an_unreadable_doc_blocks_the_scan(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (repo / "README.md").write_text("Call `calculateVig()`.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        (repo / "README.md").chmod(0o000)
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    @pytest.mark.skipif(
        os.geteuid() == 0, reason="root reads files without permission bits"
    )
    def test_allows_when_the_example_file_is_unreadable(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        (repo / ".env.example").chmod(0o000)
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


class TestMalformedProjectFiles:
    def test_ignores_comments_and_blanks_in_the_example(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text(
            "# a comment\n\nexport EXISTING=placeholder\nNO_EQUALS_LINE\n",
            encoding="utf-8",
        )
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.EXISTING;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_when_package_json_is_not_valid_json(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "package.json").write_text(
            '{\n  "scripts": {\n    "lint": "eslint ."\n  }\n}\n', encoding="utf-8"
        )
        (repo / "README.md").write_text("Run `pnpm lint`.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "package.json").write_text("{ not json", encoding="utf-8")
        _stage(repo, "package.json")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_when_scripts_is_not_an_object(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "package.json").write_text(
            '{\n  "scripts": ["lint"]\n}\n', encoding="utf-8"
        )
        (repo / "README.md").write_text("Run `pnpm lint`.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "package.json").write_text('{\n  "scripts": []\n}\n', encoding="utf-8")
        _stage(repo, "package.json")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_a_brand_new_package_json(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "README.md").write_text("Run `pnpm lint`.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "package.json").write_text(
            '{\n  "scripts": {\n    "lint": "eslint ."\n  }\n}\n', encoding="utf-8"
        )
        _stage(repo, "package.json")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_when_only_documentation_is_staged(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "README.md").write_text("Initial.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "README.md").write_text("Updated prose only.\n", encoding="utf-8")
        _stage(repo, "README.md")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


class TestBypass:
    def test_env_var_disables_the_hook(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload, env={"DOC_SYNC_DISABLE": "1"})

        # Assert
        assert_allowed(result)

    def test_profile_disable_makes_the_hook_inert(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

        # Assert
        assert_allowed(result)


class TestCommandScope:
    def test_a_commit_in_another_directory_is_checked_there(
        self, repo: Path, tool_use, run_hook, tmp_path: Path
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_KEY;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        payload = tool_use(
            "Bash", {"command": f"git -C {repo} commit -m 'feat: k'"}, cwd=str(tmp_path)
        )

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "NEW_KEY")

    def test_commit_all_checks_unstaged_tracked_changes(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        (repo / "app.js").write_text("const a = 1;\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_KEY;\n", encoding="utf-8"
        )
        payload = tool_use(
            "Bash", {"command": "git commit -am 'feat: k'"}, cwd=str(repo)
        )

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "NEW_KEY")
