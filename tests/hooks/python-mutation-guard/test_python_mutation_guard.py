"""Coverage for the python-mutation-guard hook.

Source rule: standards/immutability.md Per-Language Expression,
rules/lang/python.md, rules/code-style.md Immutability.
"""

from __future__ import annotations

HOOK = "python-mutation-guard"
ENFORCE = {"PYTHON_MUTATION_ENFORCE": "1"}

PARAM_MUTATION = (
    "def add_tag(items: list[str], tag: str) -> list[str]:\n"
    "    items.append(tag)\n"
    "    return items\n"
)


def test_blocks_parameter_mutation(tool_use, assert_blocks):
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": PARAM_MUTATION}
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "parameter `items` is mutated", env=ENFORCE
    )

    assert "BLOCKED by python-mutation-guard" in stderr
    assert "L2" in stderr


def test_warns_without_blocking_by_default(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": PARAM_MUTATION}
    )

    _code, stderr = assert_allows(HOOK, payload)

    assert "INFO from python-mutation-guard" in stderr
    assert "PYTHON_MUTATION_ENFORCE=1" in stderr


def test_blocks_mutable_default_list(tool_use, assert_blocks):
    content = "def collect(items: list[str] = []) -> list[str]:\n    return items\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/collect.py", "content": content}
    )

    assert_blocks(HOOK, payload, "mutable default", env=ENFORCE)


def test_blocks_mutable_default_dict_call(tool_use, assert_blocks):
    content = "def build(options=dict()):\n    return options\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/build.py", "content": content}
    )

    assert_blocks(HOOK, payload, "mutable default", env=ENFORCE)


def test_blocks_item_assignment_on_a_parameter(tool_use, assert_blocks):
    content = (
        "def annotate(payload: dict[str, str], key: str) -> dict[str, str]:\n"
        "    payload[key] = 'seen'\n"
        "    return payload\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/annotate.py", "content": content}
    )

    assert_blocks(HOOK, payload, "parameter `payload` is mutated", env=ENFORCE)


def test_blocks_mutation_of_a_read_only_annotation(tool_use, assert_blocks):
    content = (
        "from collections.abc import Sequence\n"
        "\n"
        "def rotate(values: Sequence[int]) -> None:\n"
        "    values.append(0)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/rotate.py", "content": content}
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "parameter `values` is mutated", env=ENFORCE
    )

    assert "Sequence" in stderr


def test_allows_a_fresh_list(tool_use, assert_allows):
    content = (
        "from collections.abc import Sequence\n"
        "\n"
        "def add_tag(items: Sequence[str], tag: str) -> tuple[str, ...]:\n"
        "    return (*items, tag)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": content}
    )

    _code, stderr = assert_allows(HOOK, payload, env=ENFORCE)

    assert stderr.strip() == ""


def test_allows_mutation_of_a_local_accumulator(tool_use, assert_allows):
    content = (
        "def summarize(rows: tuple[Row, ...]) -> dict[str, int]:\n"
        "    totals: dict[str, int] = {}\n"
        "    for row in rows:\n"
        "        totals[row.key] = totals.get(row.key, 0) + row.value\n"
        "    return totals\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/summary.py", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_none_default(tool_use, assert_allows):
    content = (
        "def collect(items: list[str] | None = None) -> list[str]:\n"
        "    return list(items or [])\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/collect.py", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_allows_self_mutation_in_a_method(tool_use, assert_allows):
    content = (
        "class Counter:\n"
        "    def __init__(self) -> None:\n"
        "        self._values: dict[str, int] = {}\n"
        "\n"
        "    def record(self, key: str) -> None:\n"
        "        self._values[key] = self._values.get(key, 0) + 1\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/counter.py", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_reports_every_offending_parameter(tool_use, assert_blocks):
    content = (
        "def merge(left: list[int], right: list[int]) -> list[int]:\n"
        "    left.extend(right)\n"
        "    right.sort()\n"
        "    return left\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/merge.py", "content": content}
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "parameter `left` is mutated", env=ENFORCE
    )

    assert "parameter `right` is mutated" in stderr


def test_flags_edits_with_a_parsable_fragment(tool_use, assert_blocks):
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/app/services/tags.py",
            "old_string": "noop",
            "new_string": PARAM_MUTATION,
        },
    )

    assert_blocks(HOOK, payload, "parameter `items` is mutated", env=ENFORCE)


def test_falls_back_to_regex_on_unparsable_fragments(tool_use, assert_blocks):
    fragment = "    def helper(cache={}):\n        return cache\n"
    payload = tool_use(
        "Edit",
        {
            "file_path": "/repo/app/services/helper.py",
            "old_string": "noop",
            "new_string": fragment,
        },
    )

    assert_blocks(HOOK, payload, "mutable default", env=ENFORCE)


def test_skips_non_python_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/src/index.ts", "content": PARAM_MUTATION}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_test_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/tests/test_tags.py", "content": PARAM_MUTATION}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_disable_env_short_circuits(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": PARAM_MUTATION}
    )

    _code, stderr = assert_allows(
        HOOK, payload, env={"PYTHON_MUTATION_DISABLE": "1", **ENFORCE}
    )

    assert stderr.strip() == ""


def test_ignores_unrelated_tools(tool_use, assert_allows):
    payload = tool_use("Bash", {"command": "true"})

    assert_allows(HOOK, payload, env=ENFORCE)


def test_survives_malformed_payload(run_hook):
    code, _stdout, _stderr = run_hook(HOOK, "not-json")

    assert code == 0


OFFENDING = PARAM_MUTATION
OFFENDING_PATH = "/repo/app/services/tags.py"


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


def test_skips_stub_files(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.pyi", "content": PARAM_MUTATION}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_skips_files_named_with_the_test_prefix(tool_use, assert_allows):
    payload = tool_use(
        "Write", {"file_path": "/repo/app/test_helpers.py", "content": PARAM_MUTATION}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_flags_multiedit_fragments(tool_use, assert_blocks):
    payload = tool_use(
        "MultiEdit",
        {
            "file_path": "/repo/app/services/tags.py",
            "edits": [
                {"old_string": "a", "new_string": "X = 1\n"},
                {"old_string": "b", "new_string": PARAM_MUTATION},
            ],
        },
    )

    assert_blocks(HOOK, payload, "parameter `items` is mutated", env=ENFORCE)


def test_reads_dotted_annotations(tool_use, assert_blocks):
    content = (
        "import collections.abc\n"
        "\n"
        "def rotate(values: collections.abc.Sequence[int]) -> None:\n"
        "    values.append(0)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/rotate.py", "content": content}
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "parameter `values` is mutated", env=ENFORCE
    )

    assert "Sequence" in stderr


def test_handles_unnamed_annotation_forms(tool_use, assert_blocks):
    content = (
        "def apply(handlers: list['Handler'], item: object) -> None:\n"
        "    handlers.append(item)\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/apply.py", "content": content}
    )

    assert_blocks(HOOK, payload, "parameter `handlers` is mutated", env=ENFORCE)


def test_flags_mutation_of_varargs_and_kwargs(tool_use, assert_blocks):
    content = (
        "def gather(*rows: dict[str, int], **options: str) -> None:\n"
        "    rows.append({})\n"
        "    options.update({'a': 'b'})\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/gather.py", "content": content}
    )

    _code, stderr = assert_blocks(
        HOOK, payload, "parameter `rows` is mutated", env=ENFORCE
    )

    assert "parameter `options` is mutated" in stderr


def test_flags_del_on_a_parameter_key(tool_use, assert_blocks):
    content = (
        "def strip_secret(payload: dict[str, str]) -> dict[str, str]:\n"
        "    del payload['secret']\n"
        "    return payload\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/strip.py", "content": content}
    )

    assert_blocks(HOOK, payload, "parameter `payload` is mutated", env=ENFORCE)


def test_honors_a_suppression_directive_on_the_mutation(tool_use, assert_allows):
    content = (
        "def add_tag(items: list[str], tag: str) -> list[str]:\n"
        "    # type: ignore[misc]\n"
        "    items.append(tag)\n"
        "    return items\n"
    )
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/tags.py", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)


def test_honors_a_suppression_directive_on_a_mutable_default(tool_use, assert_allows):
    content = "# noqa: B006\ndef collect(items: list[str] = []) -> list[str]:\n    return items\n"
    payload = tool_use(
        "Write", {"file_path": "/repo/app/services/collect.py", "content": content}
    )

    assert_allows(HOOK, payload, env=ENFORCE)
