"""Suppression coverage.

Validates that third-party tool directives suppress a finding
(eslint-disable-next-line, eslint-disable-line, eslint-disable block,
@ts-expect-error, @ts-ignore), and that allow markers of our own
invention do not, in either the per-line or top-of-file form.
"""

from __future__ import annotations

import pytest

from conftest import make_write_payload


def test_eslint_disable_next_line_suppresses(run_hook):
    snippet = """// eslint-disable-next-line
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 0, stderr


def test_eslint_disable_line_suppresses(run_hook):
    snippet = "items.push(value) // eslint-disable-line\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 0, stderr


def test_eslint_disable_block_suppresses(run_hook):
    snippet = """/* eslint-disable */
items.push(value)
items.sort()
items.reverse()
/* eslint-enable */
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 0, stderr


def test_ts_expect_error_preceding_line_suppresses(run_hook):
    snippet = """// @ts-expect-error -- pre-existing legacy
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 0, stderr


def test_ts_ignore_same_line_suppresses(run_hook):
    snippet = "items.push(value) // @ts-ignore\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 0, stderr


def test_claude_allow_mutation_per_line_does_not_suppress(run_hook):
    snippet = "items.push(value) // allow-mutation -- legacy callback API\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, _stderr = run_hook(payload)

    assert code == 2


def test_claude_allow_mutation_preceding_line_does_not_suppress(run_hook):
    snippet = """// allow-mutation -- legacy callback
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, _stderr = run_hook(payload)

    assert code == 2


def test_claude_allow_mutation_without_trailer_does_not_suppress(run_hook):
    snippet = "items.push(value) // allow-mutation\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 2, "no form of our own allow marker may suppress"
    assert "array.push" in stderr


def test_claude_allow_file_marker_does_not_suppress(run_hook):
    snippet = """// @allow-mutation -- legacy migration shim
items.push(value)
items.sort()
arr.splice(0, 1)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, _stderr = run_hook(payload)

    assert code == 2


def test_claude_allow_file_marker_without_trailer_does_not_suppress(run_hook):
    snippet = """// @allow-mutation
items.push(value)
"""
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr


def test_claude_allow_file_marker_too_far_from_top_does_not_suppress(run_hook):
    snippet = (
        "\n".join(["// padding"] * 12)
        + "\n// @allow-mutation -- too late\nitems.push(value)\n"
    )
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr


def test_claude_allow_marker_inside_string_literal_does_not_suppress(run_hook):
    snippet = "log('allow-mutation -- not a real marker')\nitems.push(value)\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 2
    assert "array.push" in stderr


@pytest.mark.parametrize(
    "marker",
    ["// eslint-disable-line", "// @ts-expect-error", "// @ts-ignore"],
)
def test_standard_markers_each_suppress_independently(run_hook, marker):
    snippet = f"items.push(value) {marker}\n"
    payload = make_write_payload("/repo/src/app.ts", snippet)

    code, stderr = run_hook(payload)

    assert code == 0, f"{marker}: unexpected block\n{stderr}"
