from __future__ import annotations

import pytest

from conftest import FINDING_TAG, make_write_payload


AUTOMERGE_DIRECT_MUTATION_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "automerge-init-direct-property-write",
        """import * as Automerge from "@automerge/automerge";
let doc = Automerge.init();
function bump() {
  doc.count = 1;
}
""",
    ),
    (
        "automerge-from-nested-property-write",
        """import * as Automerge from "@automerge/automerge";
let doc = Automerge.from({ count: 0 });
function reset() {
  doc.profile.name = "anon";
}
""",
    ),
    (
        "automerge-load-compound-assign",
        """import * as Automerge from "@automerge/automerge";
let doc = Automerge.load(bytes);
function inc() {
  doc.count += 1;
}
""",
    ),
    (
        "automerge-change-return-then-mutate",
        """import * as Automerge from "@automerge/automerge";
let doc = Automerge.change(initial, d => { d.count = 0 });
function bad() {
  doc.count = 5;
}
""",
    ),
]


@pytest.mark.parametrize(
    "name,snippet",
    AUTOMERGE_DIRECT_MUTATION_BLOCKED_FIXTURES,
    ids=lambda v: v,
)
def test_automerge_direct_mutation_blocks(name, snippet, run_hook):
    # Arrange
    payload = make_write_payload("/repo/src/sync.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "automerge.direct-mutation" in stderr, (
        f"{name}: detector did not fire\n{stderr}"
    )


def test_automerge_change_callback_mutation_allowed(run_hook):
    # Arrange
    snippet = """import * as Automerge from "@automerge/automerge";
let doc = Automerge.init();
function update() {
  doc = Automerge.change(doc, draft => {
    draft.count = 1;
    draft.profile.name = "anon";
  });
}
"""
    payload = make_write_payload("/repo/src/sync.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_automerge_detector_skipped_without_import_leaves_plain_assignment(run_hook):
    # Arrange
    snippet = """const doc = { count: 0 };
function bump() {
  doc.count = 1;
}
"""
    payload = make_write_payload("/repo/src/plain.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert FINDING_TAG.findall(stderr) == ["property.assignment"]


ASYNC_ITERATOR_RETURN_THROW_BLOCKED_FIXTURES: list[tuple[str, str]] = [
    (
        "async-iterator-type-annotation-return",
        """async function cleanup(iter: AsyncIterator<string>) {
  await iter.return("done");
}
""",
    ),
    (
        "async-iterator-type-annotation-throw",
        """async function abort(iter: AsyncIterator<number>) {
  await iter.throw(new Error("boom"));
}
""",
    ),
    (
        "async-iterator-symbol-factory",
        """async function consume(source: { [Symbol.asyncIterator](): AsyncIterator<number> }) {
  const iter = source[Symbol.asyncIterator]();
  await iter.return(0);
}
""",
    ),
]


@pytest.fixture
def _stage3_filter(monkeypatch):
    monkeypatch.setenv("MUTATION_METHOD_TC39_STAGE_FILTER", "3")


@pytest.mark.parametrize(
    "name,snippet",
    ASYNC_ITERATOR_RETURN_THROW_BLOCKED_FIXTURES,
    ids=lambda v: v,
)
def test_async_iterator_return_throw_blocks_under_stage3(
    name, snippet, run_hook, _stage3_filter
):
    # Arrange
    payload = make_write_payload("/repo/src/iter.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 2
    assert "async-iterator.return-throw" in stderr, (
        f"{name}: detector did not fire\n{stderr}"
    )


def test_async_iterator_return_throw_silent_at_stage4_default(run_hook):
    # Arrange
    snippet = """async function cleanup(iter: AsyncIterator<string>) {
  await iter.return("done");
}
"""
    payload = make_write_payload("/repo/src/iter.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""


def test_async_iterator_generator_return_not_flagged(run_hook, _stage3_filter):
    # Arrange
    snippet = """function* gen() { yield 1; }
function caller() {
  const it = gen();
  it.return(0);
}
"""
    payload = make_write_payload("/repo/src/iter.ts", snippet)

    # Act
    code, stderr = run_hook(payload)

    # Assert
    assert code == 0, stderr
    assert stderr == ""
