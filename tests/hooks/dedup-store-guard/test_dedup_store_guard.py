"""Coverage for the dedup-store-guard hook.

Source rule: standards/idempotency.md Storage, rules/architecture-defaults.md
Deduplication Specifics, checklists/checklist.md category 18.
"""

from __future__ import annotations

HOOK = "dedup-store-guard"
ENFORCE = {"DEDUP_STORE_ENFORCE": "1"}

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


def test_blocks_module_level_set_used_for_dedup(tool_use, assert_blocks):
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": IN_MEMORY_SET}
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "in-memory deduplication store", env=ENFORCE
    )

    assert "BLOCKED by dedup-store-guard" in stderr
    assert "processedEvents" in stderr


def test_warns_without_blocking_by_default(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": IN_MEMORY_SET}
    )

    _code, stderr = assert_allows(HOOK, payload)

    assert "INFO from dedup-store-guard" in stderr
    assert "DEDUP_STORE_ENFORCE=1" in stderr


def test_blocks_map_named_for_deduplication(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, "in-memory deduplication store", env=ENFORCE)


def test_blocks_python_module_level_set(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, "in-memory deduplication store", env=ENFORCE)


def test_blocks_array_used_as_a_dedup_log(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, "in-memory deduplication store", env=ENFORCE)


def test_allows_a_durable_dedup_store(tool_use, assert_allows):
    content = (
        "export async function handleWebhook(event: StripeEvent) {\n"
        "  await db.processedEvent.create({ data: { eventId: event.id } });\n"
        "  await applyEffect(event);\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": content}
    )

    _code, stderr = assert_allows(HOOK, payload, env=ENFORCE)

    assert stderr.strip() == ""


def test_allows_a_single_flight_map(tool_use, assert_allows):
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

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_a_function_local_set(tool_use, assert_allows):
    content = (
        "export function uniqueIds(records: readonly Record[]): readonly string[] {\n"
        "  const seenIds = new Set(records.map((record) => record.id));\n"
        "  return [...seenIds];\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/utils/unique.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_a_redis_backed_store(tool_use, assert_allows):
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

    assert_allows(HOOK, payload, env=ENFORCE)


def test_flags_edits(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/webhooks/stripe.ts",
            "old_string": "noop",
            "new_string": IN_MEMORY_SET,
        },
    )

    assert_blocks(HOOK, payload, "in-memory deduplication store", env=ENFORCE)


def test_flags_multiedit(tool_use, assert_blocks):
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

    assert_blocks(HOOK, payload, "in-memory deduplication store", env=ENFORCE)


def test_skips_test_files(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/webhooks/stripe.test.ts", "content": IN_MEMORY_SET},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_non_source_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/notes.md", "content": IN_MEMORY_SET}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_disable_env_short_circuits(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/src/webhooks/stripe.ts", "content": IN_MEMORY_SET}
    )

    _code, stderr = assert_allows(
        HOOK, payload, env={"DEDUP_STORE_DISABLE": "1", **ENFORCE}
    )

    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "true"})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_survives_malformed_payload(run_hook):
    code, _stdout, _stderr = run_hook(HOOK, "not-json")

    assert code == 0


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
