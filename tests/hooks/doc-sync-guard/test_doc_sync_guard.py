from __future__ import annotations

from pathlib import Path

from _helpers.hook_assertions import assert_allowed, assert_blocked
from doc_sync_guard_test_repo import (
    COMMIT,
    HOOK,
    _commit_all,
    _stage,
)


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
