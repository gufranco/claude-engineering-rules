"""Coverage for the transaction-scope-guard hook.

Source rule: standards/concurrency.md, standards/database.md Transactions,
checklists/checklist.md category 19.
"""

from __future__ import annotations

HOOK = "transaction-scope-guard"
ENFORCE = {"TRANSACTION_SCOPE_ENFORCE": "1"}

FETCH_IN_TX = (
    "export async function settle(orderId: string) {\n"
    "  await db.$transaction(async (tx) => {\n"
    "    const order = await tx.order.update({ where: { id: orderId }, data: { paid: true } });\n"
    "    await fetch('https://api.example.com/notify', { method: 'POST' });\n"
    "    await tx.receipt.create({ data: { orderId } });\n"
    "  });\n"
    "}\n"
)


def test_blocks_fetch_inside_a_transaction(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": FETCH_IN_TX},
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "I/O inside a transaction", env=ENFORCE
    )

    assert "BLOCKED by transaction-scope-guard" in stderr
    assert "L4" in stderr


def test_warns_without_blocking_by_default(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": FETCH_IN_TX},
    )

    _code, stderr = assert_allows(HOOK, payload)

    assert "INFO from transaction-scope-guard" in stderr
    assert "TRANSACTION_SCOPE_ENFORCE=1" in stderr


def test_blocks_sdk_client_calls_inside_a_transaction(tool_use, assert_blocks):
    content = (
        "await db.$transaction(async (tx) => {\n"
        "  await tx.payment.create({ data });\n"
        "  await stripe.charges.create({ amount });\n"
        "});\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/payment.service.ts", "content": content},
    )

    assert_blocks(HOOK, payload, "I/O inside a transaction", env=ENFORCE)


def test_blocks_email_send_inside_a_transaction(tool_use, assert_blocks):
    content = (
        "await prisma.$transaction(async (tx) => {\n"
        "  await tx.invite.create({ data });\n"
        "  await sendEmail(invite.email);\n"
        "});\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/invite.service.ts", "content": content},
    )

    assert_blocks(HOOK, payload, "I/O inside a transaction", env=ENFORCE)


def test_blocks_sleep_inside_a_transaction(tool_use, assert_blocks):
    content = (
        "await db.transaction(async (tx) => {\n"
        "  await tx.job.update({ where: { id }, data: { state: 'running' } });\n"
        "  await sleep(5000);\n"
        "});\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/job.service.ts", "content": content}
    )

    assert_blocks(HOOK, payload, "holds the transaction open", env=ENFORCE)


def test_allows_io_outside_the_transaction(tool_use, assert_allows):
    content = (
        "const charge = await stripe.charges.create({ amount });\n"
        "await db.$transaction(async (tx) => {\n"
        "  await tx.payment.create({ data: { chargeId: charge.id } });\n"
        "  await tx.order.update({ where: { id }, data: { paid: true } });\n"
        "});\n"
        "await sendEmail(user.email);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/payment.service.ts", "content": content},
    )

    _code, stderr = assert_allows(HOOK, payload, env=ENFORCE)

    assert stderr.strip() == ""


def test_allows_a_transaction_that_only_touches_the_database(tool_use, assert_allows):
    content = (
        "await db.$transaction(async (tx) => {\n"
        "  await tx.account.update({ where: { id: from }, data: { balance: { decrement: amount } } });\n"
        "  await tx.account.update({ where: { id: to }, data: { balance: { increment: amount } } });\n"
        "  await tx.transfer.create({ data: { from, to, amount } });\n"
        "});\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/transfer.service.ts", "content": content},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_flags_array_mode_transaction_spanning_two_models(tool_use, assert_blocks):
    content = (
        "await db.$transaction([\n"
        "  db.token.update({ where: { id }, data: { userId: null } }),\n"
        "  db.bonus.delete({ where: { id: bonusId } }),\n"
        "]);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/bonus.service.ts", "content": content},
    )

    _code, stderr = assert_blocks(HOOK, payload, "array-mode transaction", env=ENFORCE)

    assert "interactive" in stderr


def test_allows_array_mode_on_a_single_model(tool_use, assert_allows):
    content = (
        "await db.$transaction([\n"
        "  db.audit.create({ data: first }),\n"
        "  db.audit.create({ data: second }),\n"
        "]);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/audit.service.ts", "content": content},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_reports_the_offending_call(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": FETCH_IN_TX},
    )

    assert_blocks(HOOK, payload, "fetch(", env=ENFORCE)


def test_flags_edits(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "old_string": "noop",
            "new_string": FETCH_IN_TX,
        },
    )

    assert_blocks(HOOK, payload, "I/O inside a transaction", env=ENFORCE)


def test_flags_multiedit(tool_use, assert_blocks):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/order.service.ts",
            "edits": [
                {"old_string": "a", "new_string": "const x = 1;\n"},
                {"old_string": "b", "new_string": FETCH_IN_TX},
            ],
        },
    )

    assert_blocks(HOOK, payload, "I/O inside a transaction", env=ENFORCE)


def test_skips_test_files(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {
            "file_path": "/repo/src/services/order.service.spec.ts",
            "content": FETCH_IN_TX,
        },
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_non_source_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/README.md", "content": FETCH_IN_TX}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_disable_env_short_circuits(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": FETCH_IN_TX},
    )

    _code, stderr = assert_allows(
        HOOK, payload, env={"TRANSACTION_SCOPE_DISABLE": "1", **ENFORCE}
    )

    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "echo hi"})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_survives_malformed_payload(run_hook):
    code, _stdout, _stderr = run_hook(HOOK, "not-json")

    assert code == 0


def test_handles_unterminated_transaction_callback(tool_use, assert_allows):
    content = (
        "await db.$transaction(async (tx) => {\n  await tx.order.create({ data });\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/order.service.ts", "content": content},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


OFFENDING = FETCH_IN_TX
OFFENDING_PATH = "/repo/src/services/order.service.ts"


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
