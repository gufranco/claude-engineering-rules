from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from faker import Faker

from _helpers.cov_env import apply_coverage_env

HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "user-commands-one-line.py"
TIMEOUT_S = 30
TAIL_BYTES = 512 * 1024


def _env(home: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_HOOK_AUDIT_DISABLE": "1",
        "CLAUDE_BYPASS_STATE": os.devnull,
        **(extra or {}),
    }


def _run(payload: dict[str, object], env: dict[str, str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=apply_coverage_env(env),
        timeout=TIMEOUT_S,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _prompt(text: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def _tool_result() -> str:
    content = [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}})


def _reply(text: str) -> str:
    content = [{"type": "text", "text": text}]
    return json.dumps(
        {"type": "assistant", "message": {"role": "assistant", "content": content}}
    )


def _transcript(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines) + "\n")
    return path


def _command(faker: Faker) -> str:
    return f"! rm -rf /tmp/{faker.word()}/{faker.word()}"


def _decision(stdout: str) -> str:
    return str(json.loads(stdout)["decision"]) if stdout else ""


def test_blocks_a_reply_with_two_separate_commands(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    text = f"Run these:\n\n```\n{_command(faker)}\n{_command(faker)}\n```"
    path = _transcript(tmp_path, [_prompt(faker.sentence()), _reply(text)])

    # Act
    code, stdout, _ = _run({"transcript_path": str(path)}, _env(tmp_path))

    # Assert
    assert (code, _decision(stdout)) == (0, "block")
    assert "2 separate commands" in json.loads(stdout)["reason"]


def test_allows_one_line_that_chains_every_command(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    text = f"```\n{_command(faker)} && {_command(faker)[2:]}\n```"
    path = _transcript(tmp_path, [_prompt(faker.sentence()), _reply(text)])

    # Act
    code, stdout, stderr = _run({"transcript_path": str(path)}, _env(tmp_path))

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_counts_commands_across_messages_of_one_turn(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    lines = [
        _prompt(faker.sentence()),
        _reply(_command(faker)),
        _tool_result(),
        _reply(_command(faker)),
    ]
    path = _transcript(tmp_path, lines)

    # Act
    code, stdout, _ = _run({"transcript_path": str(path)}, _env(tmp_path))

    # Assert
    assert (code, _decision(stdout)) == (0, "block")


def test_ignores_commands_from_an_earlier_turn(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    earlier = f"{_command(faker)}\n{_command(faker)}"
    lines = [
        _prompt(faker.sentence()),
        _reply(earlier),
        "not json",
        "[]",
        _prompt(faker.sentence()),
        json.dumps({"type": "assistant", "message": "malformed"}),
        _reply(faker.sentence()),
    ]
    path = _transcript(tmp_path, lines)

    # Act
    code, stdout, stderr = _run({"transcript_path": str(path)}, _env(tmp_path))

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_reads_only_the_tail_of_a_long_transcript(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    filler = _reply("x" * (TAIL_BYTES + 1))
    text = f"{_command(faker)}\n{_command(faker)}"
    path = _transcript(tmp_path, [filler, _prompt(faker.sentence()), _reply(text)])

    # Act
    code, stdout, _ = _run({"transcript_path": str(path)}, _env(tmp_path))

    # Assert
    assert (code, _decision(stdout)) == (0, "block")


def test_prefers_the_last_assistant_message_field(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    payload = {"last_assistant_message": f"{_command(faker)}\n\n{_command(faker)}"}

    # Act
    code, stdout, _ = _run(payload, _env(tmp_path))

    # Assert
    assert (code, _decision(stdout)) == (0, "block")


def test_stays_silent_when_a_stop_hook_already_continued(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    payload = {
        "stop_hook_active": True,
        "last_assistant_message": f"{_command(faker)}\n{_command(faker)}",
    }

    # Act
    code, stdout, stderr = _run(payload, _env(tmp_path))

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_stays_silent_when_disabled(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    payload = {"last_assistant_message": f"{_command(faker)}\n{_command(faker)}"}
    env = _env(tmp_path, {"USER_COMMANDS_ONE_LINE_DISABLE": "1"})

    # Act
    code, stdout, stderr = _run(payload, env)

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def _reason_for(tmp_path: Path, line: str) -> str:
    code, stdout, _ = _run({"last_assistant_message": line}, _env(tmp_path))
    assert code == 0
    return str(json.loads(stdout)["reason"]) if stdout else ""


def test_blocks_steps_joined_with_a_semicolon(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    line = f"! cd /tmp/{faker.word()}; ls /tmp/{faker.word()}"

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert "`;`" in reason


def test_allows_a_semicolon_inside_strict_mode(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    line = f'! (set -euo pipefail; S=/tmp/{faker.word()}; ls "$S")'

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert reason == ""


def test_blocks_a_silenced_failure(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    line = f"! ls /tmp/{faker.word()} || true"

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert "`|| true`" in reason


def test_blocks_a_recursive_delete_of_an_unguarded_variable(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    line = f'! S=/tmp/{faker.word()} && rm -rf "$S/{faker.word()}"'

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert "${VAR:?}" in reason


def test_allows_a_single_file_delete_of_a_variable_path(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    line = f'! S=/tmp/{faker.word()} && rm -f "$S/{faker.word()}.log"'

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert reason == ""


def test_allows_a_recursive_delete_of_a_guarded_variable(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    line = f'! S=/tmp/{faker.word()} && rm -rf "${{S:?}}/{faker.word()}" && ls -la'

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert reason == ""


def test_skips_the_safety_checks_on_unbalanced_quotes(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    line = f"! echo '{faker.word()}; rm -rf $S"

    # Act
    reason = _reason_for(tmp_path, line)

    # Assert
    assert reason == ""


def test_allows_a_reply_without_a_transcript(tmp_path: Path) -> None:
    # Arrange
    payload: dict[str, object] = {"transcript_path": ""}

    # Act
    code, stdout, stderr = _run(payload, _env(tmp_path))

    # Assert
    assert (code, stdout, stderr) == (0, "", "")


def test_reports_an_unreadable_transcript_and_allows(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    payload = {"transcript_path": str(tmp_path / f"{faker.word()}.jsonl")}

    # Act
    code, stdout, stderr = _run(payload, _env(tmp_path))

    # Assert
    assert (code, stdout) == (0, "")
    assert "transcript not read" in stderr
