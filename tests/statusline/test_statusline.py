from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from faker import Faker
from _helpers.cov_env import apply_coverage_env

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "statusline.py"
OPUS = "claude-opus-4-7"
SONNET = "claude-sonnet-4-6"
SCRIPT_TIMEOUT_S = 6

Usage = dict[str, int]
Payload = dict[str, object]


def run(stdin_text: str, cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_S,
        env=apply_coverage_env(dict(os.environ)),
        cwd=cwd,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def usage(
    input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0
) -> Usage:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
    }


def make_transcript(tmp_path: Path, faker: Faker, usages: list[Usage]) -> Path:
    path = tmp_path / "transcript.jsonl"
    lines = [
        json.dumps(
            {
                "type": "assistant",
                "uuid": faker.uuid4(),
                "message": {"id": faker.uuid4(), "model": OPUS, "usage": entry},
            }
        )
        for entry in usages
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_project(tmp_path: Path, faker: Faker) -> Path:
    project = tmp_path / faker.slug()
    project.mkdir()
    return project


def payload_for(project: Path, model: str, transcript: Path) -> str:
    body: Payload = {
        "cwd": str(project),
        "model": model,
        "transcript_path": str(transcript),
    }
    return json.dumps(body)


def test_outputs_one_line_without_a_trailing_newline(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(100, 50, cache_write=1000)])

    # Act
    result = run(payload_for(project, OPUS, transcript))

    # Assert
    assert result == (0, f"[{project.name}] | opus | cache 0% | ctx 0% | $0.02", "")


def test_reports_the_model_short_name_for_a_sonnet_id(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(10, 10)])

    # Act
    _, stdout, _ = run(payload_for(project, SONNET, transcript))

    # Assert
    assert stdout == f"[{project.name}] | sonnet | cache 0% | ctx 0% | $0.00"


def test_cache_hit_ratio_counts_reads_over_all_input(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(
        tmp_path, faker, [usage(100, 10, cache_read=9000, cache_write=900)]
    )

    # Act
    _, stdout, _ = run(payload_for(project, OPUS, transcript))

    # Assert
    assert stdout == f"[{project.name}] | opus | cache 90% | ctx 1% | $0.03"


def test_cache_hit_ratio_is_zero_without_cache_reads(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(1000, 10)])

    # Act
    _, stdout, _ = run(payload_for(project, OPUS, transcript))

    # Assert
    assert stdout == f"[{project.name}] | opus | cache 0% | ctx 0% | $0.02"


def test_cost_estimation_opus(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(1_000_000, 100_000)])

    # Act
    _, stdout, _ = run(payload_for(project, OPUS, transcript))

    # Assert
    assert stdout == f"[{project.name}] | opus | cache 0% | ctx 100% | $22.5"


def test_cost_estimation_sonnet_clamps_context_at_full(
    tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(1_000_000, 100_000)])

    # Act
    _, stdout, _ = run(payload_for(project, SONNET, transcript))

    # Assert
    assert stdout == f"[{project.name}] | sonnet | cache 0% | ctx 100% | $4.50"


def test_cost_aggregates_across_multiple_turns(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(1000, 400)] * 10)

    # Act
    _, stdout, _ = run(payload_for(project, OPUS, transcript))

    # Assert
    assert stdout == f"[{project.name}] | opus | cache 0% | ctx 0% | $0.45"


def test_context_percentage_uses_the_latest_turn(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(tmp_path, faker, [usage(100, 50, cache_write=100_000)])

    # Act
    _, stdout, _ = run(payload_for(project, OPUS, transcript))

    # Assert
    assert stdout == f"[{project.name}] | opus | cache 0% | ctx 10% | $1.88"


def test_handles_missing_transcript(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    missing = tmp_path / f"{faker.word()}.jsonl"

    # Act
    result = run(payload_for(project, OPUS, missing))

    # Assert
    assert result == (0, f"[{project.name}] | opus | cache 0% | ctx 0% | $0.00", "")


def test_handles_malformed_jsonl(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = tmp_path / "bad.jsonl"
    transcript.write_text(
        f"{faker.sentence()}\n{{{faker.word()}}}\n{faker.word()}:{{}}\n",
        encoding="utf-8",
    )

    # Act
    result = run(payload_for(project, OPUS, transcript))

    # Assert
    assert result == (0, f"[{project.name}] | opus | cache 0% | ctx 0% | $0.00", "")


def test_handles_empty_stdin(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)

    # Act
    result = run("", cwd=project)

    # Assert
    assert result == (
        0,
        f"[{project.name}] | unknown | cache 0% | ctx 0% | $0.00",
        "",
    )


def test_handles_missing_fields(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)

    # Act
    result = run(json.dumps({"cwd": str(project)}))

    # Assert
    assert result == (
        0,
        f"[{project.name}] | unknown | cache 0% | ctx 0% | $0.00",
        "",
    )


def test_aggregates_a_thousand_turn_transcript(tmp_path: Path, faker: Faker) -> None:
    # Arrange
    project = make_project(tmp_path, faker)
    transcript = make_transcript(
        tmp_path, faker, [usage(100, 50, cache_read=1000)] * 1000
    )

    # Act
    result = run(payload_for(project, OPUS, transcript))

    # Assert
    assert result == (0, f"[{project.name}] | opus | cache 91% | ctx 0% | $6.75", "")
