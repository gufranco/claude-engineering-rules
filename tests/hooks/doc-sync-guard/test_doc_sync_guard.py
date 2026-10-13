from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from faker import Faker
from _helpers.hook_assertions import assert_allowed, assert_blocked
import os
import sys

HOOK = "doc-sync-guard"
COMMIT = "git commit -m 'feat: change'"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path, faker: Faker) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", faker.email())
    _git(root, "config", "user.name", faker.first_name())
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "commit", "--allow-empty", "-qm", "chore: root")
    return root


def _commit_all(repo: Path, message: str = "chore: baseline") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _stage(repo: Path, *paths: str) -> None:
    _git(repo, "add", *paths)


class TestUndocumentedEnvVar:
    def test_blocks_a_new_env_var_missing_from_the_example(
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
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "NEW_SECRET_KEY")

    def test_allows_when_the_example_is_staged_too(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.js").write_text(
            "const k = process.env.NEW_SECRET_KEY;\n", encoding="utf-8"
        )
        (repo / ".env.example").write_text(
            "EXISTING=placeholder\nNEW_SECRET_KEY=placeholder\n", encoding="utf-8"
        )
        _stage(repo, "app.js", ".env.example")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_a_var_already_in_the_example(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
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

    def test_allows_when_the_repo_has_no_example_file(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "app.js").write_text(
            "const k = process.env.ANYTHING;\n", encoding="utf-8"
        )
        _stage(repo, "app.js")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_detects_python_os_environ(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.py").write_text(
            'KEY = os.environ["PY_ONLY_VAR"]\n', encoding="utf-8"
        )
        _stage(repo, "app.py")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "PY_ONLY_VAR")

    def test_detects_python_getenv(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "app.py").write_text(
            'KEY = os.getenv("GETENV_VAR")\n', encoding="utf-8"
        )
        _stage(repo, "app.py")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "GETENV_VAR")

    def test_ignores_env_reads_in_removed_lines(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / ".env.example").write_text("EXISTING=placeholder\n", encoding="utf-8")
        (repo / "app.js").write_text(
            "const k = process.env.GOING_AWAY;\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "app.js").write_text("const k = 1;\n", encoding="utf-8")
        _stage(repo, "app.js")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


class TestRemovedExportStillDocumented:
    def test_blocks_a_removed_export_named_by_markdown(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Call `calculateVig()` to price a bet.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "calculateVig")

    def test_allows_when_the_document_is_staged_too(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Call `calculateVig()` to price a bet.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Call `priceBet()` to price a bet.\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts", "README.md")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_allows_a_removed_export_no_document_names(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (repo / "README.md").write_text("Nothing relevant here.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_detects_an_exported_const(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / "lib.ts").write_text(
            "export const MAX_RETRIES = 3;\n", encoding="utf-8"
        )
        (repo / "README.md").write_text(
            "Tune `MAX_RETRIES` for flaky networks.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export const RETRY_LIMIT = 3;\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "MAX_RETRIES")

    def test_detects_an_exported_class(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / "lib.ts").write_text("export class OrderService {}\n", encoding="utf-8")
        (repo / "docs.md").write_text(
            "`OrderService` owns order writes.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "lib.ts").write_text("export class OrderWriter {}\n", encoding="utf-8")
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_blocked(result, "OrderService")

    def test_ignores_an_export_removed_from_a_markdown_code_sample(
        self, repo: Path, tool_use, run_hook
    ) -> None:
        # Arrange
        (repo / "guide.md").write_text(
            "```typescript\nexport class OrderService {}\n```\n", encoding="utf-8"
        )
        (repo / "docs.md").write_text(
            "`OrderService` owns order writes.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "guide.md").write_text("See the service docs.\n", encoding="utf-8")
        _stage(repo, "guide.md")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_skips_changelog_files(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (repo / "CHANGELOG.md").write_text(
            "Removed `calculateVig` in v2.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_skips_adr_files(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        adr = repo / "docs" / "adr"
        adr.mkdir(parents=True)
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (adr / "001-vig.md").write_text(
            "We introduced `calculateVig` here.\n", encoding="utf-8"
        )
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)

    def test_skips_spec_folders(self, repo: Path, tool_use, run_hook) -> None:
        # Arrange
        spec = repo / "specs" / "2026-01-01-thing"
        spec.mkdir(parents=True)
        (repo / "lib.ts").write_text(
            "export function calculateVig() { return 1; }\n", encoding="utf-8"
        )
        (spec / "plan.md").write_text("Add `calculateVig`.\n", encoding="utf-8")
        _commit_all(repo)
        (repo / "lib.ts").write_text(
            "export function priceBet() { return 1; }\n", encoding="utf-8"
        )
        _stage(repo, "lib.ts")
        payload = tool_use("Bash", {"command": COMMIT}, cwd=str(repo))

        # Act
        result = run_hook(HOOK, payload)

        # Assert
        assert_allowed(result)


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
