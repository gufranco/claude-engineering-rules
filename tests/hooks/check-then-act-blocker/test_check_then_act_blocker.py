from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked
import json
from datetime import datetime, timedelta, timezone

HOOK = "check-then-act-blocker"
ENFORCE = {"CHECK_THEN_ACT_ENFORCE": "1"}

FIND_THEN_CREATE = (
    "export async function reserveSeat(showId: string, row: number) {\n"
    "  const existing = await db.seat.findFirst({ where: { showId, row } });\n"
    "  if (!existing) {\n"
    "    await db.seat.create({ data: { showId, row } });\n"
    "  }\n"
    "}\n"
)


def test_blocks_find_then_create_when_enforcing(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_blocked(result, "read that decides a write")
    assert "BLOCKED by check-then-act-blocker" in stderr
    assert "FIX-AND-RETRY" in stderr


def test_warns_without_blocking_by_default(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert (
        "INFO from check-then-act-blocker" in context,
        "CHECK_THEN_ACT_ENFORCE=1" in context,
    ) == (True, True)


def test_reports_the_entity_and_both_line_numbers(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_blocked(result, "entity `seat`")
    assert "L2->L4" in stderr


def test_allows_upsert(tool_use, run_hook):
    # Arrange
    content = (
        "const seat = await db.seat.upsert({\n"
        "  where: { showId_row: { showId, row } },\n"
        "  create: { showId, row },\n"
        "  update: {},\n"
        "});\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/seat.service.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_allows_when_a_unique_violation_is_handled(tool_use, run_hook):
    # Arrange
    content = (
        "const existing = await db.seat.findFirst({ where: { showId } });\n"
        "if (!existing) {\n"
        "  try {\n"
        "    await db.seat.create({ data: { showId } });\n"
        "  } catch (error: unknown) {\n"
        "    if (isUniqueViolation(error, 'P2002')) return err('taken');\n"
        "    throw error;\n"
        "  }\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/seat.service.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_allows_when_a_row_lock_spans_the_pair(tool_use, run_hook):
    # Arrange
    content = (
        "await db.transaction(async (tx) => {\n"
        "  const account = await tx.account.findFirst({ where: { id } , lock: 'FOR UPDATE' });\n"
        "  await tx.account.create({ data: { id } });\n"
        "});\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/account.service.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_allows_read_and_write_on_different_entities(tool_use, run_hook):
    # Arrange
    content = (
        "const user = await db.user.findUnique({ where: { id } });\n"
        "const order = await db.order.create({ data: { userId: user.id } });\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_allows_when_the_write_is_far_from_the_read(tool_use, run_hook):
    # Arrange
    filler = "".join(f"  const step{n} = n{n};\n" for n in range(14))
    content = (
        "const existing = await db.seat.findFirst({ where: { showId } });\n"
        + filler
        + "await db.seat.create({ data: { showId } });\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/seat.service.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_matches_repository_style_receivers(tool_use, run_hook):
    # Arrange
    content = (
        "const found = await userRepository.findOne({ email });\n"
        "if (!found) {\n"
        "  await userRepository.save({ email });\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/user.service.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "entity `user`")


def test_matches_python_get_or_none_then_create(tool_use, run_hook):
    # Arrange
    content = (
        "existing = await session.invite.find_by(email=email)\n"
        "if existing is None:\n"
        "    await session.invite.insert(email=email)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/invite.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "entity `invite`")


def test_flags_edits_not_only_writes(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "old_string": "noop",
            "new_string": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "read that decides a write")


def test_flags_multiedit_payloads(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "edits": [
                {"old_string": "a", "new_string": "const x = 1;\n"},
                {"old_string": "b", "new_string": FIND_THEN_CREATE},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(result, "read that decides a write")


def test_skips_test_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.test.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_skips_migrations(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/migrations/001_init/seed.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_skips_non_source_extensions(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/docs/guide.md", "content": FIND_THEN_CREATE}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_disable_env_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    # Act
    result = run_hook(HOOK, payload, env={"CHECK_THEN_ACT_DISABLE": "1", **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "ls"})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    payload = "not-json"

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "could not read its input")


def test_honors_third_party_suppression_directive(tool_use, run_hook):
    # Arrange
    content = (
        "// eslint-disable-next-line no-restricted-syntax\n"
        "const existing = await db.seat.findFirst({ where: { showId } });\n"
        "await db.seat.create({ data: { showId } });\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/seat.service.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


OFFENDING = FIND_THEN_CREATE
OFFENDING_PATH = "/repo/src/services/seat.service.ts"


def _run_raw(hook_name: str, stdin_text: str, env_extra=None):
    import os
    import subprocess
    import sys
    from pathlib import Path

    hook_path = Path(__file__).resolve().parents[3] / "hooks" / f"{hook_name}.py"
    env = dict(os.environ)
    env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    for key in ("COVERAGE_PROCESS_START", "PYTHONPATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=6.0,
        check=False,
    )
    return proc.returncode, proc.stderr


def test_raw_invalid_json_blocks():
    # Arrange
    stdin_text = "{not json at all"

    # Act
    code, _stderr = _run_raw(HOOK, stdin_text)

    # Assert
    assert code == 2


def test_empty_file_path_is_ignored(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": "", "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_allowed(result)


def test_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": 42})

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.content is not a",
    )


def test_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit", {"file_path": OFFENDING_PATH, "old_string": "a", "new_string": 42}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.new_string is not",
    )


def test_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit", {"file_path": OFFENDING_PATH, "edits": ["not-a-dict", None]}
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.edits is not a",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {"file_path": OFFENDING_PATH, "edits": [{"old_string": "a", "new_string": 7}]},
    )

    # Act
    result = run_hook(HOOK, payload, env=ENFORCE)

    # Assert
    assert_blocked(
        result,
        "Blocked: check-then-act-blocker could not read its input: tool_input.edits is not a",
    )


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK, **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_live_bypass_entry_short_circuits(tmp_path, tool_use, run_hook):
    # Arrange
    state = tmp_path / "bypass.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    state.write_text(
        json.dumps(
            {"bypasses": [{"hook": HOOK, "expires_at": expires, "reason": "test"}]}
        )
    )
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state), **ENFORCE})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""
