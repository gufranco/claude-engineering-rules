from __future__ import annotations

import json

from _helpers.hook_assertions import assert_allowed, assert_blocked
from check_then_act_test_data import (
    ENFORCE,
    FIND_THEN_CREATE,
    HOOK,
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
