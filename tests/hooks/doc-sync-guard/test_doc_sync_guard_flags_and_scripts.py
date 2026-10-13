from __future__ import annotations

from pathlib import Path

import pytest
from _helpers.hook_assertions import assert_allowed, assert_blocked
from doc_sync_guard_test_repo import (
    COMMIT,
    HOOK,
    _commit_all,
    _stage,
)


class TestRemovedFlagStillDocumented:
    def test_blocks_a_removed_argparse_flag(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "cli.py").write_text(
            'parser.add_argument("--dry-run")\n', encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Pass `--dry-run` to preview.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "cli.py").write_text(
            'parser.add_argument("--preview")\n', encoding="utf-8"
        )
        _stage(repo, "cli.py")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "--dry-run")

    def test_blocks_a_removed_commander_option(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "cli.js").write_text(
            "program.option('--verbose', 'be loud')\n", encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Use `--verbose` for detail.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "cli.js").write_text(
            "program.option('--loud', 'be loud')\n", encoding="utf-8"
        )
        _stage(repo, "cli.js")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "--verbose")

    def test_allows_a_removed_flag_no_document_names(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "cli.py").write_text(
            'parser.add_argument("--dry-run")\n', encoding="utf-8"
        )
        (repo / "README.md").write_text("No flags documented.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "cli.py").write_text(
            'parser.add_argument("--preview")\n', encoding="utf-8"
        )
        _stage(repo, "cli.py")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_an_added_flag(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / "cli.py").write_text(
            'parser.add_argument("--dry-run")\n', encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Pass `--dry-run` to preview.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "cli.py").write_text(
            'parser.add_argument("--dry-run")\nparser.add_argument("--json")\n',
            encoding="utf-8",
        )
        _stage(repo, "cli.py")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


class TestRemovedScriptStillDocumented:
    def test_blocks_a_removed_package_script(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "package.json").write_text(
            '{\n  "scripts": {\n    "build": "tsc",\n    "lint": "eslint ."\n  }\n}\n',
            encoding="utf-8",
        )
        (repo / "README.md").write_text(
            "Run `pnpm lint` before pushing.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "package.json").write_text(
            '{\n  "scripts": {\n    "build": "tsc"\n  }\n}\n', encoding="utf-8"
        )
        _stage(repo, "package.json")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "lint")

    def test_allows_a_removed_script_no_document_names(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "package.json").write_text(
            '{\n  "scripts": {\n    "build": "tsc",\n    "lint": "eslint ."\n  }\n}\n',
            encoding="utf-8",
        )
        (repo / "README.md").write_text("Nothing about scripts.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "package.json").write_text(
            '{\n  "scripts": {\n    "build": "tsc"\n  }\n}\n', encoding="utf-8"
        )
        _stage(repo, "package.json")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


class TestNonCommitCommands:
    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git add -A",
            "git push origin main",
            "git log --oneline",
            "echo 'git commit is not run here'",
            "git commit --help",
        ],
    )
    def test_ignores_commands_that_are_not_a_commit(
        self, command: str, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        payload = tool_use("Bash", {"command": command}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_a_non_bash_tool(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        payload = tool_use("Read", {"file_path": "/tmp/x"}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_an_empty_command(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        payload = tool_use("Bash", {"command": ""}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


class TestOutsideARepository:
    def test_allows_when_cwd_is_not_a_git_repository(
        self, tmp_path: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(tmp_path))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_when_nothing_is_staged(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)
