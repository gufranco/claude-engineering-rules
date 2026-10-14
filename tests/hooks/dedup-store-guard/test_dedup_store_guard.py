from __future__ import annotations
from _helpers.hook_assertions import assert_allowed, assert_blocked
import json
from datetime import datetime, timedelta, timezone

HOOK = "dedup-store-guard"

IN_MEMORY_SET = (
    "const processedEvents = new Set<string>();\n"
    "\n"
    "export async function handleWebhook(event: StripeEvent) {\n"
    "  if (processedEvents.has(event.id)) {\n"
    "    return;\n"
    "  }\n"
    "  processedEvents.add(event.id);\n"
    "  await applyEffect(event);\n"
    "}\n"
)


def test_blocks_module_level_set_used_for_dedup(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": IN_MEMORY_SET}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "in-memory deduplication store")
    assert "BLOCKED by dedup-store-guard" in stderr
    assert "processedEvents" in stderr


def test_blocks_by_default_without_an_opt_in(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": IN_MEMORY_SET}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_blocked(result, "processedEvents")
    assert "DEDUP_STORE_DISABLE" in stderr


def test_blocks_map_named_for_deduplication(tool_use, run_hook):
    # Arrange
    content = (
        "const seenMessageIds = new Map<string, number>();\n"
        "export function consume(message: Message) {\n"
        "  if (seenMessageIds.has(message.id)) return;\n"
        "  seenMessageIds.set(message.id, Date.now());\n"
        "}\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/consumers/orders.consumer.ts", "content": content},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "in-memory deduplication store")


def test_blocks_python_module_level_set(tool_use, run_hook):
    # Arrange
    content = (
        "PROCESSED_EVENT_IDS: set[str] = set()\n"
        "\n"
        "async def handle_webhook(event):\n"
        "    if event.id in PROCESSED_EVENT_IDS:\n"
        "        return\n"
        "    PROCESSED_EVENT_IDS.add(event.id)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/webhooks/stripe.py", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "in-memory deduplication store")


def test_blocks_array_used_as_a_dedup_log(tool_use, run_hook):
    # Arrange
    content = (
        "const handledDeliveryIds: string[] = [];\n"
        "export function onDelivery(id: string) {\n"
        "  if (handledDeliveryIds.includes(id)) return;\n"
        "  handledDeliveryIds.push(id);\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/delivery.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "in-memory deduplication store")


def test_allows_a_durable_dedup_store(tool_use, run_hook):
    # Arrange
    content = (
        "export async function handleWebhook(event: StripeEvent) {\n"
        "  await db.processedEvent.create({ data: { eventId: event.id } });\n"
        "  await applyEffect(event);\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_allows_a_single_flight_map(tool_use, run_hook):
    # Arrange
    content = (
        "const inFlight = new Map<string, Promise<Config>>();\n"
        "export function loadConfig(key: string): Promise<Config> {\n"
        "  const existing = inFlight.get(key);\n"
        "  if (existing) return existing;\n"
        "  const pending = fetchConfig(key).finally(() => inFlight.delete(key));\n"
        "  inFlight.set(key, pending);\n"
        "  return pending;\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/config/loader.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_a_function_local_set(tool_use, run_hook):
    # Arrange
    content = (
        "export function uniqueIds(records: readonly Record[]): readonly string[] {\n"
        "  const seenIds = new Set(records.map((record) => record.id));\n"
        "  return [...seenIds];\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/utils/unique.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_allows_a_redis_backed_store(tool_use, run_hook):
    # Arrange
    content = (
        "export async function handleWebhook(event: StripeEvent) {\n"
        "  const fresh = await redis.set(`dedup:${event.id}`, '1', 'NX', 'EX', 259200);\n"
        "  if (fresh === null) return;\n"
        "  await applyEffect(event);\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": content}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_flags_edits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/webhooks/stripe.ts",
            "old_string": "noop",
            "new_string": IN_MEMORY_SET,
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "in-memory deduplication store")


def test_flags_multiedit(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/webhooks/stripe.ts",
            "edits": [
                {"old_string": "a", "new_string": "const x = 1;\n"},
                {"old_string": "b", "new_string": IN_MEMORY_SET},
            ],
        },
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "in-memory deduplication store")


def test_skips_test_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/webhooks/stripe.test.ts", "content": IN_MEMORY_SET},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_skips_non_source_files(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/notes.md", "content": IN_MEMORY_SET}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_disable_env_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": IN_MEMORY_SET}
    )

    # Act
    result = run_hook(HOOK, payload, env={"DEDUP_STORE_DISABLE": "1"})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, run_hook):
    # Arrange
    payload = tool_use("Bash", {"command": "true"})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_blocks_a_payload_that_is_not_an_object(run_hook):
    # Arrange
    payload = "not-json"

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(result, "could not read its input")


OFFENDING = IN_MEMORY_SET
OFFENDING_PATH = "/repo/src/webhooks/stripe.ts"


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
    result = run_hook(HOOK, payload)

    # Assert
    assert_allowed(result)


def test_non_string_content_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": 42})

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: dedup-store-guard could not read its input: tool_input.content is not a string.",
    )


def test_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "Edit", {"file_path": OFFENDING_PATH, "old_string": "a", "new_string": 42}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: dedup-store-guard could not read its input: tool_input.new_string is not a",
    )


def test_non_dict_edits_block(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit", {"file_path": OFFENDING_PATH, "edits": ["not-a-dict", None]}
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: dedup-store-guard could not read its input: tool_input.edits is not a list of",
    )


def test_multiedit_non_string_new_string_blocks(tool_use, run_hook):
    # Arrange
    payload = tool_use(
        "MultiEdit",
        {"file_path": OFFENDING_PATH, "edits": [{"old_string": "a", "new_string": 7}]},
    )

    # Act
    result = run_hook(HOOK, payload)

    # Assert
    assert_blocked(
        result,
        "Blocked: dedup-store-guard could not read its input: tool_input.edits is not a list of",
    )


def test_profile_disable_short_circuits(tool_use, run_hook):
    # Arrange
    payload = tool_use("Write", {"file_path": OFFENDING_PATH, "content": OFFENDING})

    # Act
    result = run_hook(HOOK, payload, env={"CLAUDE_DISABLED_HOOKS": HOOK})

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
    result = run_hook(HOOK, payload, env={"CLAUDE_BYPASS_STATE": str(state)})

    # Assert
    _code, stderr = assert_allowed(result)
    assert stderr.strip() == ""
