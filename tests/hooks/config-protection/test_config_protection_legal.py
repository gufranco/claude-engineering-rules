from __future__ import annotations

import json
from pathlib import Path

from _helpers.hook_assertions import assert_allowed
from faker import Faker

HOOK = "config-protection"

fake = Faker()
Faker.seed(4205)


def test_asks_before_editing_an_existing_notice(tool_use, run_hook, tmp_path: Path):
    # Arrange
    notice = tmp_path / "NOTICE"
    notice.write_text(fake.sentence(), encoding="utf-8")
    payload = tool_use(
        "Edit",
        {
            "file_path": str(notice),
            "old_string": fake.word(),
            "new_string": fake.word(),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "ask"
    assert output["permissionDecisionReason"].startswith(
        "NOTICE is a legal policy file"
    )


def test_allows_creating_a_new_license(tool_use, run_hook, tmp_path: Path):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": str(tmp_path / "LICENSE"), "content": fake.sentence()}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    assert result.stdout.strip() == ""


def test_allows_source_file_named_like_a_policy(tool_use, run_hook, tmp_path: Path):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": str(tmp_path / "license.ts"),
            "old_string": fake.word(),
            "new_string": fake.word(),
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    assert result.stdout.strip() == ""


def test_bypass_env_skips_the_legal_policy_ask(tool_use, run_hook, tmp_path: Path):
    # Arrange
    policy = tmp_path / "CLEAN_ROOM.md"
    policy.write_text(fake.sentence(), encoding="utf-8")
    payload = tool_use("Write", {"file_path": str(policy), "content": fake.sentence()})

    # Act
    result = run_hook(HOOK, payload, env={"CONFIG_PROTECTION_DISABLE": "1"})

    # Assert
    assert_allowed(result)
    assert result.stdout.strip() == ""
