"""Coverage for the check-then-act-blocker hook.

Source rule: standards/concurrency.md Race Taxonomy, rules/architecture-defaults.md Hard Rules.
"""

from __future__ import annotations

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


def test_blocks_find_then_create_when_enforcing(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "read that decides a write", env=ENFORCE
    )

    assert "BLOCKED by check-then-act-blocker" in stderr
    assert "FIX-AND-RETRY" in stderr


def test_warns_without_blocking_by_default(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    _code, stderr = assert_allows(HOOK, payload)

    assert "INFO from check-then-act-blocker" in stderr
    assert "CHECK_THEN_ACT_ENFORCE=1" in stderr


def test_reports_the_entity_and_both_line_numbers(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    _code, stderr = assert_blocks(HOOK, payload, "entity `seat`", env=ENFORCE)

    assert "L2->L4" in stderr


def test_allows_upsert(tool_use, assert_allows):
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

    _code, stderr = assert_allows(HOOK, payload, env=ENFORCE)

    assert stderr.strip() == ""


def test_allows_when_a_unique_violation_is_handled(tool_use, assert_allows):
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

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_when_a_row_lock_spans_the_pair(tool_use, assert_allows):
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

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_read_and_write_on_different_entities(tool_use, assert_allows):
    content = (
        "const user = await db.user.findUnique({ where: { id } });\n"
        "const order = await db.order.create({ data: { userId: user.id } });\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": content},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_when_the_write_is_far_from_the_read(tool_use, assert_allows):
    filler = "".join(f"  const step{n} = n{n};\n" for n in range(14))
    content = (
        "const existing = await db.seat.findFirst({ where: { showId } });\n"
        + filler
        + "await db.seat.create({ data: { showId } });\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/seat.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_matches_repository_style_receivers(tool_use, assert_blocks):
    content = (
        "const found = await userRepository.findOne({ email });\n"
        "if (!found) {\n"
        "  await userRepository.save({ email });\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/user.service.ts", "content": content}
    )

    assert_blocks(HOOK, payload, "entity `user`", env=ENFORCE)


def test_matches_python_get_or_none_then_create(tool_use, assert_blocks):
    content = (
        "existing = await session.invite.find_by(email=email)\n"
        "if existing is None:\n"
        "    await session.invite.insert(email=email)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/invite.py", "content": content}
    )

    assert_blocks(HOOK, payload, "entity `invite`", env=ENFORCE)


def test_flags_edits_not_only_writes(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "old_string": "noop",
            "new_string": FIND_THEN_CREATE,
        },
    )

    assert_blocks(HOOK, payload, "read that decides a write", env=ENFORCE)


def test_flags_multiedit_payloads(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, "read that decides a write", env=ENFORCE)


def test_skips_test_files(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.test.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_migrations(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/prisma/migrations/001_init/seed.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_non_source_extensions(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/docs/guide.md", "content": FIND_THEN_CREATE}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_disable_env_short_circuits(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/seat.service.ts",
            "content": FIND_THEN_CREATE,
        },
    )

    _code, stderr = assert_allows(
        HOOK, payload, env={"CHECK_THEN_ACT_DISABLE": "1", **ENFORCE}
    )

    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "ls"})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_survives_malformed_payload(run_hook):
    code, _stdout, _stderr = run_hook(HOOK, "not-json")

    assert code == 0


def test_honors_third_party_suppression_directive(tool_use, assert_allows):
    content = (
        "// eslint-disable-next-line no-await-in-loop\n"
        "const existing = await db.seat.findFirst({ where: { showId } });\n"
        "await db.seat.create({ data: { showId } });\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/seat.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


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


def test_raw_invalid_json_is_ignored():
    code, _stderr = _run_raw(HOOK, "{not json at all")

    assert code == 0


def test_empty_file_path_is_ignored(tool_use, assert_allows):
    payload = tool_use("Write", {"file_path": "", "content": OFFENDING})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_non_string_content_is_ignored(tool_use, assert_allows):
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": 42})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_non_string_new_string_is_ignored(tool_use, assert_allows):
    payload = tool_use(
        "Edit", {"file_path": OFFENDING_PATH, "old_string": "a", "new_string": 42}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_non_dict_edits_are_ignored(tool_use, assert_allows):
    payload = tool_use(
        "MultiEdit", {"file_path": OFFENDING_PATH, "edits": ["not-a-dict", None]}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_multiedit_non_string_new_string_is_ignored(tool_use, assert_allows):
    payload = tool_use(
        "MultiEdit",
        {"file_path": OFFENDING_PATH, "edits": [{"old_string": "a", "new_string": 7}]},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_profile_disable_short_circuits(tool_use, assert_allows):
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    _code, stderr = assert_allows(
        HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK, **ENFORCE}
    )

    assert stderr.strip() == ""


def test_live_bypass_entry_short_circuits(tmp_path, tool_use, assert_allows):
    import json
    from datetime import datetime, timedelta, timezone

    state = tmp_path / "bypass.json"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    state.write_text(
        json.dumps(
            {"bypasses": [{"hook": HOOK, "expires_at": expires, "reason": "test"}]}
        )
    )
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    _code, stderr = assert_allows(
        HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state), **ENFORCE}
    )

    assert stderr.strip() == ""
