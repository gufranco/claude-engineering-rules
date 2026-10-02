"""Coverage for the interactive-cmd-blocker hook."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOK = "interactive-cmd-blocker"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / f"{HOOK}.py"
KCOV_MAKEFILE = "coverage:\n\tkcov --include-path=src coverage bats test/\n"
PLAIN_MAKEFILE = "coverage:\n\tpytest --cov\n"
on_darwin = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


def load_hook():
    spec = importlib.util.spec_from_file_location("interactive_cmd_blocker", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook():
    return load_hook()


def write_makefile(directory: Path, text: str, name: str = "Makefile") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text)
    return directory


@pytest.mark.parametrize(
    "cmd",
    [
        "rm file.txt",
        "rm -r mydir",
        "rm -v file.txt",
        "/bin/rm file.txt",
        "cp src.txt dst.txt",
        "cp -r srcdir/ dstdir/",
        "mv old.txt new.txt",
        "mv -v old.txt new.txt",
    ],
)
def test_blocks_command_without_force(tool_use, assert_blocks, cmd):
    payload = tool_use("Bash", {"command": cmd})

    assert_blocks(HOOK, payload, "without `-f`")


def test_blocks_in_compound_command(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "echo hi && rm foo.txt"})

    assert_blocks(HOOK, payload)


def test_blocks_after_or(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "test -f x.txt || rm x.txt"})

    assert_blocks(HOOK, payload)


def test_blocks_via_command_builtin(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "command rm file.txt"})

    assert_blocks(HOOK, payload)


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -f file.txt",
        "rm -rf mydir",
        "rm -fr mydir",
        "rm -rfv mydir",
        "rm --force file.txt",
        "cp -f src dst",
        "cp -rf srcdir dstdir",
        "mv -f old new",
        "mv --force old new",
        "/bin/rm -f file.txt",
    ],
)
def test_allows_command_with_force(tool_use, assert_allows, cmd):
    payload = tool_use("Bash", {"command": cmd})

    assert_allows(HOOK, payload)


def test_allows_safe_compound(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls && rm -f foo && echo done"})

    assert_allows(HOOK, payload)


@pytest.mark.parametrize(
    "cmd",
    [
        "ls -la",
        "git status",
        "echo rm",
        "python3 script.py",
        "grep -r 'rm' .",
        "remote=$(git remote)",
        "trim_whitespace",
    ],
)
def test_allows_unrelated_commands(tool_use, assert_allows, cmd):
    payload = tool_use("Bash", {"command": cmd})

    assert_allows(HOOK, payload)


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "Read", "Grep"])
def test_allows_unrelated_tools(tool_use, assert_allows, tool_name):
    payload = tool_use(tool_name, {"file_path": "/tmp/x"})

    assert_allows(HOOK, payload)


def test_bypass_env_var_disables_check(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "rm file.txt"})

    assert_allows(HOOK, payload, env={"INTERACTIVE_CMD_DISABLE": "1"})


def test_handles_empty_command(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": ""})

    assert_allows(HOOK, payload)


def test_handles_malformed_shell(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "echo 'unterminated"})

    assert_allows(HOOK, payload)


def test_handles_env_var_prefix(tool_use, assert_blocks):
    payload = tool_use("Bash", {"command": "FOO=bar rm file.txt"})

    assert_blocks(HOOK, payload)


@pytest.mark.parametrize(
    "cmd",
    [
        "kcov out bats test/",
        "/opt/homebrew/bin/kcov --include-path=src out bats test/",
        "command kcov out ./run.sh",
        "FOO=1 kcov out ./run.sh",
        "echo start && kcov out ./run.sh",
        "echo start\nkcov out ./run.sh",
    ],
)
def test_kcov_is_blocked_on_darwin(hook, tmp_path, cmd):
    blocked = hook.kcov_blocked(cmd, str(tmp_path), "darwin")

    assert blocked is True


def test_kcov_is_allowed_off_darwin(hook, tmp_path):
    blocked = hook.kcov_blocked("kcov out bats test/", str(tmp_path), "linux")

    assert blocked is False


@pytest.mark.parametrize(
    "cmd",
    [
        "echo 'kcov out bats test/'",
        'grep -rn "x && kcov out" .',
        "python3 - <<'EOF'\nkcov out bats test/\nEOF",
        "cat <<-EOF\nmake coverage\nEOF",
        "echo 'unterminated && kcov out",
    ],
)
def test_kcov_in_quotes_or_heredoc_is_allowed(hook, tmp_path, cmd):
    write_makefile(tmp_path, KCOV_MAKEFILE)

    blocked = hook.kcov_blocked(cmd, str(tmp_path), "darwin")

    assert blocked is False


def test_command_after_heredoc_is_checked(hook, tmp_path):
    blocked = hook.kcov_blocked(
        "cat <<'EOF'\ndata\nEOF\nkcov out ./run.sh", str(tmp_path), "darwin"
    )

    assert blocked is True


def test_here_string_does_not_hide_later_lines(hook, tmp_path):
    blocked = hook.kcov_blocked(
        "read -r x <<<word\nkcov out ./run.sh", str(tmp_path), "darwin"
    )

    assert blocked is True


def test_make_coverage_with_kcov_makefile_is_blocked(hook, tmp_path):
    write_makefile(tmp_path, KCOV_MAKEFILE)

    blocked = hook.kcov_blocked("make coverage", str(tmp_path), "darwin")

    assert blocked is True


def test_make_coverage_without_kcov_is_allowed(hook, tmp_path):
    write_makefile(tmp_path, PLAIN_MAKEFILE)

    blocked = hook.kcov_blocked("make coverage", str(tmp_path), "darwin")

    assert blocked is False


def test_make_other_target_is_allowed(hook, tmp_path):
    write_makefile(tmp_path, KCOV_MAKEFILE)

    blocked = hook.kcov_blocked("make test lint", str(tmp_path), "darwin")

    assert blocked is False


def test_make_without_makefile_is_allowed(hook, tmp_path):
    blocked = hook.kcov_blocked("make coverage", str(tmp_path), "darwin")

    assert blocked is False


def test_make_dash_c_reads_that_directory(hook, tmp_path):
    write_makefile(tmp_path / "plugin", KCOV_MAKEFILE)

    blocked = hook.kcov_blocked("make -C plugin coverage", str(tmp_path), "darwin")

    assert blocked is True


def test_make_dash_f_reads_that_file(hook, tmp_path):
    write_makefile(tmp_path, KCOV_MAKEFILE, name="cov.mk")

    blocked = hook.kcov_blocked("gmake -f cov.mk coverage", str(tmp_path), "darwin")

    assert blocked is True


def test_cd_before_make_is_followed(hook, tmp_path):
    write_makefile(tmp_path / "plugin", KCOV_MAKEFILE)

    blocked = hook.kcov_blocked("cd plugin && make coverage", str(tmp_path), "darwin")

    assert blocked is True


def test_kcov_inside_container_command_is_allowed(hook, tmp_path):
    write_makefile(tmp_path, KCOV_MAKEFILE)

    blocked = hook.kcov_blocked(
        "git archive HEAD | docker run --rm -i ubuntu:26.04 bash -c "
        "'tar -x -C /w && make -C /w coverage'",
        str(tmp_path),
        "darwin",
    )

    assert blocked is False


def test_lone_cd_does_not_block(hook, tmp_path):
    blocked = hook.kcov_blocked("cd", str(tmp_path), "darwin")

    assert blocked is False


@on_darwin
def test_hook_blocks_kcov_end_to_end(tool_use, assert_blocks, tmp_path):
    payload = tool_use("Bash", {"command": "kcov out bats test/"}, cwd=str(tmp_path))

    assert_blocks(HOOK, payload, "kcov on macOS")


@on_darwin
def test_hook_blocks_make_coverage_end_to_end(tool_use, assert_blocks, tmp_path):
    write_makefile(tmp_path, KCOV_MAKEFILE)
    payload = tool_use("Bash", {"command": "make coverage"}, cwd=str(tmp_path))

    assert_blocks(HOOK, payload, "docker run")


@on_darwin
def test_bypass_env_var_allows_kcov(tool_use, assert_allows, tmp_path):
    payload = tool_use("Bash", {"command": "kcov out bats test/"}, cwd=str(tmp_path))

    assert_allows(HOOK, payload, env={"INTERACTIVE_CMD_DISABLE": "1"})
