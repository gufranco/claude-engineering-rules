"""Coverage for the concurrent-fanout-guard hook.

Source rule: standards/concurrency.md Bounded fan-out,
rules/architecture-defaults.md Hard Rules.
"""

from __future__ import annotations

HOOK = "concurrent-fanout-guard"
ENFORCE = {"CONCURRENT_FANOUT_ENFORCE": "1"}

UNBOUNDED = (
    "export async function syncAll(records: readonly Record[]) {\n"
    "  const results = await Promise.all(\n"
    "    records.map((record) => pushToVendor(record)),\n"
    "  );\n"
    "  return results;\n"
    "}\n"
)


def test_blocks_unbounded_promise_all_over_a_variable(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/sync.service.ts", "content": UNBOUNDED},
    )

    _code, stderr = assert_blocks(HOOK, payload, "unbounded fan-out", env=ENFORCE)

    assert "BLOCKED by concurrent-fanout-guard" in stderr
    assert "records" in stderr


def test_warns_without_blocking_by_default(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/sync.service.ts", "content": UNBOUNDED},
    )

    _code, stderr = assert_allows(HOOK, payload)

    assert "INFO from concurrent-fanout-guard" in stderr
    assert "CONCURRENT_FANOUT_ENFORCE=1" in stderr


def test_blocks_all_settled_too(tool_use, assert_blocks):
    content = (
        "const outcomes = await Promise.allSettled(\n"
        "  userIds.map(async (id) => sendEmail(id)),\n"
        ");\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/notify.service.ts", "content": content},
    )

    assert_blocks(HOOK, payload, "unbounded fan-out", env=ENFORCE)


def test_allows_a_bounded_fanout_with_p_limit(tool_use, assert_allows):
    content = (
        "import pLimit from 'p-limit';\n"
        "const limit = pLimit(10);\n"
        "const results = await Promise.allSettled(\n"
        "  records.map((record) => limit(() => pushToVendor(record))),\n"
        ");\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/sync.service.ts", "content": content}
    )

    _code, stderr = assert_allows(HOOK, payload, env=ENFORCE)

    assert stderr.strip() == ""


def test_allows_p_map_with_a_concurrency_option(tool_use, assert_allows):
    content = (
        "import pMap from 'p-map';\n"
        "const results = await pMap(records, (record) => pushToVendor(record), {\n"
        "  concurrency: 5,\n"
        "});\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/sync.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_promise_all_over_a_fixed_tuple(tool_use, assert_allows):
    content = (
        "const [user, orders, invoices] = await Promise.all([\n"
        "  getUser(id),\n"
        "  listOrders(id),\n"
        "  listInvoices(id),\n"
        "]);\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/profile.service.ts", "content": content},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_a_pure_synchronous_map(tool_use, assert_allows):
    content = (
        "const normalized = await Promise.all(\n"
        "  rows.map((row) => Promise.resolve(normalize(row))),\n"
        ");\n"
    )
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/normalize.service.ts", "content": content},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_a_chunked_loop(tool_use, assert_allows):
    content = (
        "for (const batch of chunk(records, 50)) {\n"
        "  await Promise.all(batch.map((record) => pushToVendor(record)));\n"
        "}\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/sync.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_reports_the_line_of_the_fanout(tool_use, assert_blocks):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/sync.service.ts", "content": UNBOUNDED},
    )

    assert_blocks(HOOK, payload, "L2", env=ENFORCE)


def test_flags_edits(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/src/services/sync.service.ts",
            "old_string": "noop",
            "new_string": UNBOUNDED,
        },
    )

    assert_blocks(HOOK, payload, "unbounded fan-out", env=ENFORCE)


def test_flags_multiedit(tool_use, assert_blocks):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/src/services/sync.service.ts",
            "edits": [
                {"old_string": "a", "new_string": "const n = 1;\n"},
                {"old_string": "b", "new_string": UNBOUNDED},
            ],
        },
    )

    assert_blocks(HOOK, payload, "unbounded fan-out", env=ENFORCE)


def test_skips_test_files(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/sync.service.test.ts", "content": UNBOUNDED},
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_non_source_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/docs/sync.md", "content": UNBOUNDED}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_disable_env_short_circuits(tool_use, assert_allows):
    payload = tool_use(
        "Write",
        {"file_path": "/repo/src/services/sync.service.ts", "content": UNBOUNDED},
    )

    _code, stderr = assert_allows(
        HOOK, payload, env={"CONCURRENT_FANOUT_DISABLE": "1", **ENFORCE}
    )

    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "true"})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_survives_malformed_payload(run_hook):
    code, _stdout, _stderr = run_hook(HOOK, "not-json")

    assert code == 0


OFFENDING = UNBOUNDED
OFFENDING_PATH = "/repo/src/services/sync.service.ts"


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


def test_skips_declaration_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/src/types/api.d.ts", "content": UNBOUNDED}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_handles_an_unterminated_fanout_call(tool_use, assert_allows):
    content = (
        "const results = await Promise.all(\n  records.map((record) => push(record)),\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/sync.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_a_map_that_calls_nothing(tool_use, assert_allows):
    content = "const ids = await Promise.all(records.map((record) => record.id));\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/sync.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_honors_a_third_party_suppression_directive(tool_use, assert_allows):
    content = (
        "// eslint-disable-next-line no-restricted-syntax\n"
        "const results = await Promise.all(records.map((record) => pushToVendor(record)));\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/src/services/sync.service.ts", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)
